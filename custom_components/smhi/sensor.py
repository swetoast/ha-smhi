from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTemperature
try:
    from homeassistant.const import UnitOfPrecipitationDepth
except ImportError:
    class UnitOfPrecipitationDepth:  # type: ignore[no-redef]
        MILLIMETERS = "mm"
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_APPROVED_TIME,
    ATTR_CREATED_TIME,
    ATTR_GRID_POINT,
    ATTR_LAST_ERROR,
    ATTR_LAST_SUCCESS,
    ATTR_REFERENCE_TIME,
    ATTR_STALE,
    CONF_ENABLE_COMFORT_SENSORS,
    CONF_ENABLE_FROST_SENSORS,
    CONF_ENABLE_IMPACT_SENSOR,
    CONF_ENABLE_PRACTICAL_SENSORS,
    CONF_ENABLE_SLIPPERY_SENSORS,
    CONF_ENABLE_THERMAL_SENSORS,
    CONF_NAME,
    DOMAIN,
)
from .helpers import clean_value, condition_from_symbol, current_data_from_payload, octas_to_percent, ptype_description, symbol_description


def _payload(coordinator) -> dict[str, Any]:
    return coordinator.current_payload()


def _data(coordinator) -> dict[str, Any]:
    return current_data_from_payload(_payload(coordinator))


def calculate_dew_point(temp_c: float, humidity: float) -> float:
    """Calculate dew point using Magnus formula."""
    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + (humidity / 100.0)
    return (b * alpha) / (a - alpha)


def calculate_wind_chill(temp_c: float, wind_kmh: float) -> float | None:
    """Calculate wind chill (Environment Canada formula)."""
    if temp_c > 10 or wind_kmh < 4.8:
        return None
    return 13.12 + 0.6215 * temp_c - 11.37 * (wind_kmh ** 0.16) + 0.3965 * temp_c * (wind_kmh ** 0.16)


def calculate_heat_index(temp_c: float, humidity: float) -> float | None:
    """Calculate heat index (Steadman formula)."""
    if temp_c < 27:
        return None
    T = temp_c
    RH = humidity
    HI = (-8.78469475556 + 1.61139411 * T + 2.33854883889 * RH 
          - 0.14611605 * T * RH - 0.012308094 * T ** 2 
          - 0.0164248277778 * RH ** 2 + 0.002211732 * T ** 2 * RH 
          + 0.00072546 * T * RH ** 2 - 0.000003582 * T ** 2 * RH ** 2)
    return HI


def calculate_feels_like(temp_c: float, wind_ms: float, humidity: float) -> float:
    """Calculate feels-like temperature combining wind chill and heat index."""
    wind_kmh = wind_ms * 3.6
    wind_chill = calculate_wind_chill(temp_c, wind_kmh)
    if wind_chill is not None:
        return wind_chill
    heat_index = calculate_heat_index(temp_c, humidity)
    if heat_index is not None:
        return heat_index
    return temp_c


def calculate_frost_risk(temp_c: float, humidity: float, dew_point: float) -> int:
    """Calculate frost risk (0-100%)."""
    if temp_c > 5:
        return 0
    if temp_c <= 0:
        return 100
    
    risk = 0
    risk += max(0, (5 - temp_c) / 5 * 50)
    
    if dew_point <= 0:
        risk += 30
    elif dew_point <= 2:
        risk += 20
    
    if humidity > 80:
        risk += 20
    elif humidity > 60:
        risk += 10
    
    return min(100, int(risk))


def calculate_slippery_risk(temp_c: float, precip_frozen: float | None, precip_amount: float | None) -> int:
    """Calculate slippery conditions risk (0-100%)."""
    if temp_c < -10 or temp_c > 5:
        return 0
    
    risk = 0
    
    if -3 <= temp_c <= 2:
        risk += 40
    elif -5 <= temp_c <= 3:
        risk += 25
    
    if precip_frozen is not None and precip_frozen > 0.3:
        risk += 30
    elif precip_frozen is not None and precip_frozen > 0.1:
        risk += 15
    
    if precip_amount is not None and precip_amount > 0.1:
        risk += 30
    elif precip_amount is not None and precip_amount > 0:
        risk += 15
    
    return min(100, int(risk))


def calculate_weather_impact(temp_c: float, wind_ms: float, precip: float | None, 
                            visibility: float | None, thunder_prob: float | None) -> int:
    """Calculate overall weather impact score (0-100)."""
    impact = 0
    
    if temp_c < -15:
        impact += 30
    elif temp_c < -5:
        impact += 15
    elif temp_c > 30:
        impact += 20
    elif temp_c > 35:
        impact += 30
    
    wind_kmh = wind_ms * 3.6
    if wind_kmh > 50:
        impact += 25
    elif wind_kmh > 30:
        impact += 15
    
    if precip is not None and precip > 10:
        impact += 20
    elif precip is not None and precip > 5:
        impact += 10
    
    if visibility is not None and visibility < 1:
        impact += 15
    elif visibility is not None and visibility < 5:
        impact += 5
    
    if thunder_prob is not None and thunder_prob > 0.5:
        impact += 20
    elif thunder_prob is not None and thunder_prob > 0.3:
        impact += 10
    
    return min(100, int(impact))


def calculate_clo_value(temp_c: float, wind_ms: float) -> float:
    """Calculate clothing insulation needed in CLO units."""
    wind_kmh = wind_ms * 3.6
    wind_chill = calculate_wind_chill(temp_c, wind_kmh)
    effective_temp = wind_chill if wind_chill is not None else temp_c
    
    if effective_temp >= 26:
        return 0.4
    elif effective_temp >= 23:
        return 0.5
    elif effective_temp >= 21:
        return 0.6
    elif effective_temp >= 18:
        return 0.8
    elif effective_temp >= 15:
        return 1.0
    elif effective_temp >= 10:
        return 1.2
    elif effective_temp >= 5:
        return 1.5
    elif effective_temp >= 0:
        return 1.8
    elif effective_temp >= -5:
        return 2.0
    elif effective_temp >= -10:
        return 2.3
    elif effective_temp >= -15:
        return 2.6
    else:
        return 3.0


def calculate_sleep_comfort(temp_c: float, humidity: float) -> int:
    """Calculate sleep comfort score (0-100)."""
    ideal_temp = 17.5
    temp_range = 1.5
    
    temp_score = 100
    temp_diff = abs(temp_c - ideal_temp)
    
    if temp_diff <= temp_range:
        temp_score = 100
    elif temp_diff <= 3:
        temp_score = 100 - ((temp_diff - temp_range) / 1.5) * 30
    elif temp_diff <= 5:
        temp_score = 70 - ((temp_diff - 3) / 2) * 30
    elif temp_diff <= 8:
        temp_score = 40 - ((temp_diff - 5) / 3) * 30
    else:
        temp_score = 10 - min(10, (temp_diff - 8) * 2)
    
    humidity_score = 100
    if humidity > 70:
        humidity_score = 100 - (humidity - 70)
    elif humidity < 30:
        humidity_score = 100 - (30 - humidity)
    
    final_score = (temp_score * 0.8 + humidity_score * 0.2)
    return max(0, min(100, int(final_score)))


def calculate_exercise_safety(temp_c: float, wind_ms: float, humidity: float) -> tuple[int, str]:
    """Calculate exercise safety index (0-100) and category."""
    feels_like = calculate_feels_like(temp_c, wind_ms, humidity)
    
    score = 100
    category = "Safe"
    
    if feels_like >= 40:
        score = 0
        category = "Extreme Risk"
    elif feels_like >= 35:
        score = 20
        category = "High Risk"
    elif feels_like >= 30:
        score = 50
        category = "Caution"
    elif feels_like >= 27:
        score = 70
        category = "Caution"
    elif feels_like <= -25:
        score = 0
        category = "Extreme Risk"
    elif feels_like <= -20:
        score = 20
        category = "High Risk"
    elif feels_like <= -15:
        score = 50
        category = "Caution"
    elif feels_like <= -10:
        score = 70
        category = "Caution"
    elif feels_like < 5 or feels_like > 25:
        score = 85
        category = "Safe"
    else:
        score = 100
        category = "Safe"
    
    if humidity > 85 and temp_c > 20:
        score = max(0, score - 15)
        if category == "Safe":
            category = "Caution"
    
    return score, category


def calculate_absolute_humidity(temp_c: float, humidity: float) -> float:
    """Calculate absolute humidity in g/m³."""
    import math
    es = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    e = es * (humidity / 100.0)
    ah = (e * 2.1674) / (273.15 + temp_c)
    return ah


def calculate_frost_point(temp_c: float, humidity: float) -> float | None:
    """Calculate frost point temperature."""
    if temp_c >= 0:
        return None
    dew_point = calculate_dew_point(temp_c, humidity)
    return dew_point


def get_dew_point_perception(dew_point: float) -> str:
    """Get perception category for dew point."""
    if dew_point >= 26:
        return "Severely High"
    elif dew_point >= 24:
        return "Extremely Uncomfortable"
    elif dew_point >= 21:
        return "Very Humid"
    elif dew_point >= 18:
        return "Somewhat Uncomfortable"
    elif dew_point >= 16:
        return "Comfortable"
    elif dew_point >= 13:
        return "Pleasant"
    elif dew_point >= 10:
        return "Dry"
    else:
        return "Very Dry"


def calculate_humidex(temp_c: float, humidity: float) -> float:
    """Calculate humidex."""
    dew_point = calculate_dew_point(temp_c, humidity)
    import math
    e = 6.11 * math.exp(5417.7530 * ((1 / 273.16) - (1 / (dew_point + 273.15))))
    h = 0.5555 * (e - 10.0)
    return temp_c + h


def get_humidex_perception(humidex: float) -> str:
    """Get perception category for humidex."""
    if humidex >= 54:
        return "Heat Stroke Imminent"
    elif humidex >= 46:
        return "Dangerous"
    elif humidex >= 40:
        return "Great Discomfort"
    elif humidex >= 30:
        return "Some Discomfort"
    elif humidex >= 20:
        return "Comfortable"
    else:
        return "Cool"


def calculate_relative_strain_index(temp_c: float, humidity: float) -> float | None:
    """Calculate relative strain perception (26-35°C range)."""
    if not 26 <= temp_c <= 35:
        return None
    
    import math
    dew_point = calculate_dew_point(temp_c, humidity)
    e = 6.112 * math.exp((17.67 * dew_point) / (dew_point + 243.5))
    
    rsi = (temp_c - 21) / (58 - e)
    return rsi


def get_relative_strain_perception(rsi: float | None) -> str:
    """Get perception for relative strain index."""
    if rsi is None:
        return "N/A"
    if rsi < 0.15:
        return "Comfortable"
    elif rsi < 0.25:
        return "Slight Discomfort"
    elif rsi < 0.35:
        return "Discomfort"
    elif rsi < 0.45:
        return "Great Discomfort"
    else:
        return "Extreme Discomfort"


def calculate_summer_simmer_index(temp_c: float, humidity: float) -> float:
    """Calculate summer simmer index."""
    ssi = 1.98 * (temp_c - (0.55 - 0.0055 * humidity) * (temp_c - 14.5)) - 56.83
    return ssi


def get_summer_simmer_perception(ssi: float) -> str:
    """Get perception for summer simmer index."""
    if ssi >= 65:
        return "Extreme Danger"
    elif ssi >= 55:
        return "Danger of Heat Stroke"
    elif ssi >= 50:
        return "Extreme Caution"
    elif ssi >= 40:
        return "Caution"
    elif ssi >= 25:
        return "Comfortable"
    else:
        return "Cool"


def calculate_moist_air_enthalpy(temp_c: float, humidity: float) -> float:
    """Calculate moist air enthalpy in kJ/kg."""
    dew_point = calculate_dew_point(temp_c, humidity)
    import math
    
    pws = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    pw = pws * (humidity / 100.0)
    
    w = 0.622 * pw / (1013.25 - pw)
    
    h = 1.006 * temp_c + w * (2501 + 1.86 * temp_c)
    return h


def calculate_summer_scharlau(temp_c: float, humidity: float) -> float | None:
    """Calculate summer Scharlau index (17-39°C, humidity >= 30%)."""
    if not (17 <= temp_c <= 39 and humidity >= 30):
        return None
    
    s = 0.17 * (temp_c ** 2 - 0.4 * temp_c * (100 - humidity) + 10 * (temp_c - 25))
    return s


def get_summer_scharlau_perception(s: float | None) -> str:
    """Get perception for summer Scharlau index."""
    if s is None:
        return "N/A"
    if s < 0:
        return "Cold"
    elif s < 1:
        return "Cool"
    elif s < 2:
        return "Slightly Cool"
    elif s < 3:
        return "Comfortable"
    elif s < 4:
        return "Slightly Warm"
    elif s < 5:
        return "Warm"
    else:
        return "Hot"


def calculate_winter_scharlau(temp_c: float, humidity: float, wind_ms: float) -> float | None:
    """Calculate winter Scharlau index (-5 to 6°C, humidity >= 40%)."""
    if not (-5 <= temp_c <= 6 and humidity >= 40):
        return None
    
    wind_kmh = wind_ms * 3.6
    s = (0.13 * temp_c + 0.47) * (1 - 0.04 * wind_kmh) - 0.03 * (humidity - 100)
    return s


def get_winter_scharlau_perception(s: float | None) -> str:
    """Get perception for winter Scharlau index."""
    if s is None:
        return "N/A"
    if s < -3:
        return "Very Cold"
    elif s < -2:
        return "Cold"
    elif s < -1:
        return "Cool"
    elif s < 0:
        return "Slightly Cool"
    elif s < 1:
        return "Comfortable"
    else:
        return "Warm"


def calculate_spring_scharlau(temp_c: float, humidity: float) -> float | None:
    """Calculate spring Scharlau index (6-17°C, humidity >= 30%)."""
    if not (6 <= temp_c <= 17 and humidity >= 30):
        return None
    
    s = 0.12 * (temp_c - 11.5) ** 2 - 0.02 * (humidity - 65) + (temp_c - 11.5) * 0.4
    return s


def get_spring_scharlau_perception(s: float | None) -> str:
    """Get perception for spring Scharlau index."""
    if s is None:
        return "N/A"
    if s < -2:
        return "Too Cold"
    elif s < -1:
        return "Cool"
    elif s < 0:
        return "Slightly Cool"
    elif s < 1:
        return "Comfortable"
    elif s < 2:
        return "Slightly Warm"
    else:
        return "Too Warm"


def calculate_autumn_scharlau(temp_c: float, humidity: float, wind_ms: float) -> float | None:
    """Calculate autumn Scharlau index (5-16°C, humidity >= 35%)."""
    if not (5 <= temp_c <= 16 and humidity >= 35):
        return None
    
    wind_kmh = wind_ms * 3.6
    s = 0.15 * (temp_c - 10.5) + 0.35 * (1 - wind_kmh / 20) - 0.015 * (humidity - 70)
    return s


def get_autumn_scharlau_perception(s: float | None) -> str:
    """Get perception for autumn Scharlau index."""
    if s is None:
        return "N/A"
    if s < -1.5:
        return "Cold"
    elif s < -0.5:
        return "Cool"
    elif s < 0.5:
        return "Comfortable"
    elif s < 1.5:
        return "Mild"
    else:
        return "Warm"


def get_seasonal_scharlau(temp_c: float, humidity: float, wind_ms: float, month: int) -> tuple[float | None, str, str]:
    """Get appropriate Scharlau index based on season."""
    # Determine season based on month (Northern Hemisphere)
    if month in [12, 1, 2]:
        season = "Winter"
        value = calculate_winter_scharlau(temp_c, humidity, wind_ms)
        perception = get_winter_scharlau_perception(value)
    elif month in [3, 4, 5]:
        season = "Spring"
        value = calculate_spring_scharlau(temp_c, humidity)
        perception = get_spring_scharlau_perception(value)
    elif month in [6, 7, 8]:
        season = "Summer"
        value = calculate_summer_scharlau(temp_c, humidity)
        perception = get_summer_scharlau_perception(value)
    else:  # 9, 10, 11
        season = "Autumn"
        value = calculate_autumn_scharlau(temp_c, humidity, wind_ms)
        perception = get_autumn_scharlau_perception(value)
    
    return value, perception, season


def calculate_thoms_discomfort_index(temp_c: float, humidity: float) -> float:
    """Calculate Thom's discomfort index."""
    di = temp_c - 0.55 * (1 - 0.01 * humidity) * (temp_c - 14.5)
    return di


def get_thoms_discomfort_perception(di: float) -> str:
    """Get perception for Thom's discomfort index."""
    if di < 15:
        return "Comfortable"
    elif di < 18:
        return "Slightly Uncomfortable"
    elif di < 21:
        return "Uncomfortable"
    elif di < 24:
        return "Very Uncomfortable"
    elif di < 27:
        return "Extremely Uncomfortable"
    else:
        return "Emergency"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [
        SmhiPrecipitationSensor(coordinator),
        SmhiCloudsSensor(coordinator),
        SmhiThunderstormProbabilitySensor(coordinator),
        SmhiSymbolCodeSensor(coordinator),
        SmhiMetadataSensor(coordinator),
    ]
    
    # Optional calculated sensors
    if entry.options.get(CONF_ENABLE_COMFORT_SENSORS, True):
        sensors.append(SmhiFeelsLikeSensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_FROST_SENSORS, True):
        sensors.append(SmhiFrostRiskSensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_SLIPPERY_SENSORS, True):
        sensors.append(SmhiSlipperyRiskSensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_IMPACT_SENSOR, True):
        sensors.append(SmhiWeatherImpactSensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_PRACTICAL_SENSORS, True):
        sensors.extend([
            SmhiClothingInsulationSensor(coordinator),
            SmhiSleepComfortSensor(coordinator),
            SmhiExerciseSafetySensor(coordinator),
        ])
    
    if entry.options.get(CONF_ENABLE_THERMAL_SENSORS, True):
        sensors.extend([
            SmhiThermalComfortIndexSensor(coordinator),
            SmhiHumidityAnalysisSensor(coordinator),
            SmhiHeatStressLevelSensor(coordinator),
        ])
    
    async_add_entities(sensors)


class SmhiBaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": self.coordinator.entry.data.get(CONF_NAME, "SMHI"),
            "manufacturer": "SMHI",
            "model": "Open Data forecast",
            "configuration_url": "https://opendata.smhi.se/metfcst/snow1gv1/",
        }

    @property
    def available(self) -> bool:
        return bool(self.coordinator.current_payload())


class SmhiPrecipitationSensor(SmhiBaseSensor):
    _attr_name = "Precipitation"
    _attr_native_unit_of_measurement = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_device_class = SensorDeviceClass.PRECIPITATION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_precipitation"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        value = clean_value(data.get("precipitation_amount_mean_deterministic"), parameter="precipitation_amount_mean_deterministic")
        if value is None:
            value = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        attrs = {}
        for key in (
            "precipitation_amount_mean_deterministic",
            "precipitation_amount_mean",
            "precipitation_amount_min",
            "precipitation_amount_max",
            "precipitation_amount_median",
            "probability_of_precipitation",
        ):
            attrs[key] = clean_value(data.get(key), parameter=key)
        
        frozen_prob = clean_value(data.get("probability_of_frozen_precipitation"), parameter="probability_of_frozen_precipitation")
        attrs["probability_of_frozen_precipitation"] = frozen_prob * 100 if frozen_prob is not None else None
        attrs["probability_of_frozen_precipitation_unit"] = "%"
        
        frozen_part = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        attrs["precipitation_frozen_part"] = frozen_part * 100 if frozen_part is not None else None
        attrs["precipitation_frozen_part_unit"] = "%"
        
        attrs["predominant_precipitation_type_at_surface"] = clean_value(data.get("predominant_precipitation_type_at_surface"), parameter="predominant_precipitation_type_at_surface")
        attrs["precipitation_type_description"] = ptype_description(data.get("predominant_precipitation_type_at_surface"))
        return attrs


class SmhiCloudsSensor(SmhiBaseSensor):
    _attr_name = "Clouds"
    _attr_native_unit_of_measurement = "octas"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clouds"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_clouds"

    @property
    def native_value(self):
        return clean_value(_data(self.coordinator).get("cloud_area_fraction"), parameter="cloud_area_fraction")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        attrs = {}
        for key in (
            "cloud_area_fraction",
            "low_type_cloud_area_fraction",
            "medium_type_cloud_area_fraction",
            "high_type_cloud_area_fraction",
            "cloud_base_altitude",
            "cloud_top_altitude",
        ):
            attrs[key] = clean_value(data.get(key), parameter=key)
        attrs["cloud_area_fraction_percent"] = octas_to_percent(data.get("cloud_area_fraction"))
        attrs["cloud_base_altitude_unit"] = UnitOfLength.METERS
        attrs["cloud_top_altitude_unit"] = UnitOfLength.METERS
        return attrs


class SmhiThunderstormProbabilitySensor(SmhiBaseSensor):
    _attr_name = "Thunderstorm Probability"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_thunderstorm_probability"

    @property
    def native_value(self):
        value = clean_value(_data(self.coordinator).get("thunderstorm_probability"), parameter="thunderstorm_probability")
        return value * 100 if value is not None else None


class SmhiSymbolCodeSensor(SmhiBaseSensor):
    _attr_name = "Symbol Code"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_symbol_code"

    @property
    def native_value(self):
        return clean_value(_data(self.coordinator).get("symbol_code"), parameter="symbol_code")

    @property
    def icon(self) -> str:
        """Return dynamic icon based on weather condition."""
        condition = condition_from_symbol(_data(self.coordinator))
        
        # Map conditions to MDI icons
        icon_map = {
            "sunny": "mdi:weather-sunny",
            "partlycloudy": "mdi:weather-partly-cloudy",
            "cloudy": "mdi:weather-cloudy",
            "fog": "mdi:weather-fog",
            "rainy": "mdi:weather-rainy",
            "pouring": "mdi:weather-pouring",
            "lightning": "mdi:weather-lightning",
            "lightning-rainy": "mdi:weather-lightning-rainy",
            "snowy": "mdi:weather-snowy",
            "snowy-rainy": "mdi:weather-snowy-rainy",
        }
        
        return icon_map.get(condition, "mdi:weather-cloudy")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        attrs = {}
        attrs["symbol_code"] = self.native_value
        attrs["symbol_description"] = symbol_description(data.get("symbol_code"))
        attrs["home_assistant_condition"] = condition_from_symbol(data)
        return attrs


class SmhiMetadataSensor(SmhiBaseSensor):
    _attr_name = "Metadata"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:information"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_metadata"

    @property
    def native_value(self):
        return self.coordinator.current_payload().get("referenceTime") or self.coordinator.approved_reference_time

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        payload = self.coordinator.current_payload()
        coords = (payload.get("geometry") or {}).get("coordinates")
        grid = {"lon": coords[0], "lat": coords[1]} if isinstance(coords, list) and len(coords) >= 2 else None
        attrs = {}
        attrs.update({
            ATTR_APPROVED_TIME: self.coordinator.approved_time,
            ATTR_CREATED_TIME: payload.get("createdTime"),
            ATTR_REFERENCE_TIME: payload.get("referenceTime") or self.coordinator.approved_reference_time,
            ATTR_GRID_POINT: grid,
            "available_times_count": len(self.coordinator.times),
        })
        return attrs


class SmhiFeelsLikeSensor(SmhiBaseSensor):
    """Sensor for feels-like temperature."""
    _attr_name = "Comfort: Feels Like"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_feels_like"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or wind is None or humidity is None:
            return None
        
        return round(calculate_feels_like(temp, wind, humidity), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and wind is not None and humidity is not None:
            wind_kmh = wind * 3.6
            wind_chill = calculate_wind_chill(temp, wind_kmh)
            heat_index = calculate_heat_index(temp, humidity)
            attrs["wind_chill"] = round(wind_chill, 1) if wind_chill is not None else None
            attrs["heat_index"] = round(heat_index, 1) if heat_index is not None else None
        return attrs


class SmhiFrostRiskSensor(SmhiBaseSensor):
    """Sensor for frost risk percentage."""
    _attr_name = "Frost: Risk"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:snowflake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_frost_risk"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        dew_point = calculate_dew_point(temp, humidity)
        return calculate_frost_risk(temp, humidity, dew_point)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and humidity is not None:
            dew_point = calculate_dew_point(temp, humidity)
            attrs["current_temperature"] = temp
            attrs["current_dew_point"] = round(dew_point, 1)
        return attrs


class SmhiSlipperyRiskSensor(SmhiBaseSensor):
    """Sensor for slippery conditions risk."""
    _attr_name = "Slippery: Risk"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:car-brake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_slippery_risk"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        frozen = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        if temp is None:
            return None
        
        return calculate_slippery_risk(temp, frozen, precip)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        frozen = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        attrs = {}
        attrs["current_temperature"] = temp
        
        is_slippery = False
        if temp is not None and -5 <= temp <= 3:
            if frozen is not None and frozen > 0.3 and precip is not None and precip > 0.1:
                is_slippery = True
            elif -2 <= temp <= 1 and precip is not None and precip > 0.5:
                is_slippery = True
        attrs["conditions_detected"] = is_slippery
        
        return attrs


class SmhiWeatherImpactSensor(SmhiBaseSensor):
    """Sensor for overall weather impact score."""
    _attr_name = "Impact: Severity"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_weather_impact"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        visibility = clean_value(data.get("visibility_in_air"), parameter="visibility_in_air")
        thunder = clean_value(data.get("thunderstorm_probability"), parameter="thunderstorm_probability")
        
        if temp is None or wind is None:
            return None
        
        return calculate_weather_impact(temp, wind, precip, visibility, thunder)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        attrs = {}
        attrs["current_temperature"] = clean_value(data.get("air_temperature"), parameter="air_temperature")
        attrs["current_wind_speed"] = clean_value(data.get("wind_speed"), parameter="wind_speed")
        attrs["current_precipitation"] = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        attrs["current_visibility"] = clean_value(data.get("visibility_in_air"), parameter="visibility_in_air")
        attrs["current_thunderstorm_probability"] = clean_value(data.get("thunderstorm_probability"), parameter="thunderstorm_probability")
        return attrs


class SmhiClothingInsulationSensor(SmhiBaseSensor):
    """Sensor for recommended clothing insulation in CLO units."""
    _attr_name = "Practical: Clothing"
    _attr_native_unit_of_measurement = "CLO"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:hanger"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_clothing_insulation"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        
        if temp is None or wind is None:
            return None
        
        return round(calculate_clo_value(temp, wind), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        
        attrs = {}
        if temp is not None and wind is not None:
            clo = calculate_clo_value(temp, wind)
            
            if clo < 0.5:
                attrs["clothing_description"] = "Shorts and t-shirt"
            elif clo < 0.7:
                attrs["clothing_description"] = "Light summer clothes"
            elif clo < 1.0:
                attrs["clothing_description"] = "Light pants and long sleeves"
            elif clo < 1.5:
                attrs["clothing_description"] = "Sweater or light jacket"
            elif clo < 2.0:
                attrs["clothing_description"] = "Winter jacket"
            elif clo < 2.5:
                attrs["clothing_description"] = "Heavy winter coat"
            else:
                attrs["clothing_description"] = "Arctic gear"
        
        return attrs


class SmhiSleepComfortSensor(SmhiBaseSensor):
    """Sensor for sleep comfort score."""
    _attr_name = "Practical: Sleep"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:bed"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_sleep_comfort"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        return calculate_sleep_comfort(temp, humidity)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and humidity is not None:
            score = calculate_sleep_comfort(temp, humidity)
            attrs["ideal_range"] = "16-19°C"
            
            if score >= 80:
                attrs["comfort_level"] = "Excellent"
            elif score >= 60:
                attrs["comfort_level"] = "Good"
            elif score >= 40:
                attrs["comfort_level"] = "Fair"
            elif score >= 20:
                attrs["comfort_level"] = "Poor"
            else:
                attrs["comfort_level"] = "Very Poor"
        
        return attrs


class SmhiExerciseSafetySensor(SmhiBaseSensor):
    """Sensor for outdoor exercise safety index."""
    _attr_name = "Practical: Exercise"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:run"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_exercise_safety"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or wind is None or humidity is None:
            return None
        
        score, _ = calculate_exercise_safety(temp, wind, humidity)
        return score

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is not None and wind is not None and humidity is not None:
            score, category = calculate_exercise_safety(temp, wind, humidity)
            feels_like = calculate_feels_like(temp, wind, humidity)
            
            attrs["safety_category"] = category
            attrs["feels_like_temperature"] = round(feels_like, 1)
        
        return attrs


class SmhiThermalComfortIndexSensor(SmhiBaseSensor):
    """Comprehensive thermal comfort sensor - auto-selects most relevant index."""
    _attr_name = "Thermal: Comfort"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer-lines"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_thermal_comfort"

    @property
    def native_value(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        
        if temp is None or humidity is None:
            return None
        
        # Auto-select most relevant index based on conditions
        if temp >= 27:
            # Hot weather - use heat index
            hi = calculate_heat_index(temp, humidity)
            return round(hi, 1) if hi is not None else round(temp, 1)
        elif temp >= 17:
            # Warm weather - use summer comfort
            return round(calculate_humidex(temp, humidity), 1)
        elif temp >= 10:
            # Mild weather - use Thom's
            return round(calculate_thoms_discomfort_index(temp, humidity), 1)
        elif wind is not None and temp <= 16:
            # Cooler weather - use seasonal Scharlau
            from datetime import datetime
            current_month = datetime.now().month
            scharlau_value, _, _ = get_seasonal_scharlau(temp, humidity, wind, current_month)
            if scharlau_value is not None:
                return round(temp + scharlau_value, 1)
            return round(calculate_feels_like(temp, wind, humidity), 1)
        else:
            return round(temp, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        wind = clean_value(data.get("wind_speed"), parameter="wind_speed")
        
        attrs = {}
        if temp is None or humidity is None:
            return attrs
        
        # Always calculate all indices for reference
        attrs["heat_index"] = round(hi, 1) if (hi := calculate_heat_index(temp, humidity)) is not None else None
        attrs["humidex"] = round(calculate_humidex(temp, humidity), 1)
        attrs["thoms_discomfort"] = round(calculate_thoms_discomfort_index(temp, humidity), 1)
        
        # Seasonal Scharlau
        if wind is not None:
            from datetime import datetime
            current_month = datetime.now().month
            scharlau_value, scharlau_perception, season = get_seasonal_scharlau(temp, humidity, wind, current_month)
            
            attrs["seasonal_scharlau"] = round(scharlau_value, 2) if scharlau_value is not None else None
            attrs["seasonal_scharlau_perception"] = scharlau_perception
            attrs["current_season"] = season
        
        ssi = calculate_summer_simmer_index(temp, humidity)
        attrs["summer_simmer"] = round(ssi, 1)
        attrs["summer_simmer_perception"] = get_summer_simmer_perception(ssi)
        
        rsi = calculate_relative_strain_index(temp, humidity)
        if rsi is not None:
            attrs["relative_strain"] = round(rsi, 3)
            attrs["relative_strain_perception"] = get_relative_strain_perception(rsi)
        
        attrs["thoms_perception"] = get_thoms_discomfort_perception(attrs["thoms_discomfort"])
        
        # Determine active index
        if temp >= 27:
            attrs["active_index"] = "Heat Index"
        elif temp >= 17:
            attrs["active_index"] = "Summer Comfort"
        elif temp >= 10:
            attrs["active_index"] = "Thoms Discomfort"
        elif wind is not None and temp <= 16:
            attrs["active_index"] = f"{season} Scharlau"
        else:
            attrs["active_index"] = "Actual Temperature"
        
        return attrs


class SmhiHumidityAnalysisSensor(SmhiBaseSensor):
    """Comprehensive humidity analysis sensor."""
    _attr_name = "Thermal: Humidity"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-percent"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_humidity_analysis"

    @property
    def native_value(self):
        """Return dew point as primary value."""
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        return round(calculate_dew_point(temp, humidity), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is None or humidity is None:
            return attrs
        
        dew_point = calculate_dew_point(temp, humidity)
        abs_humidity = calculate_absolute_humidity(temp, humidity)
        
        attrs["dew_point"] = round(dew_point, 1)
        attrs["dew_point_perception"] = get_dew_point_perception(dew_point)
        attrs["absolute_humidity"] = round(abs_humidity, 2)
        attrs["absolute_humidity_unit"] = "g/m³"
        attrs["spread"] = round(temp - dew_point, 1)
        
        frost_point = calculate_frost_point(temp, humidity)
        if frost_point is not None:
            attrs["frost_point"] = round(frost_point, 1)
        
        # Moist air enthalpy
        attrs["moist_air_enthalpy"] = round(calculate_moist_air_enthalpy(temp, humidity), 2)
        attrs["enthalpy_unit"] = "kJ/kg"
        
        # Humidity comfort assessment
        if dew_point >= 24:
            attrs["humidity_comfort"] = "Oppressive"
        elif dew_point >= 21:
            attrs["humidity_comfort"] = "Very Humid"
        elif dew_point >= 18:
            attrs["humidity_comfort"] = "Humid"
        elif dew_point >= 13:
            attrs["humidity_comfort"] = "Comfortable"
        elif dew_point >= 10:
            attrs["humidity_comfort"] = "Pleasant"
        else:
            attrs["humidity_comfort"] = "Dry"
        
        return attrs


class SmhiHeatStressLevelSensor(SmhiBaseSensor):
    """Comprehensive heat stress assessment sensor."""
    _attr_name = "Thermal: Heat Stress"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-wave"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_heat_stress"

    @property
    def native_value(self):
        """Return heat stress percentage (0-100, higher = more stress)."""
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return 0
        
        # Calculate combined heat stress score
        stress = 0
        
        # Base temperature stress
        if temp >= 40:
            stress += 100
        elif temp >= 35:
            stress += 60 + (temp - 35) * 8
        elif temp >= 30:
            stress += 30 + (temp - 30) * 6
        elif temp >= 25:
            stress += 10 + (temp - 25) * 4
        elif temp >= 20:
            stress += (temp - 20) * 2
        
        # Humidity multiplier
        if humidity >= 85:
            stress *= 1.3
        elif humidity >= 70:
            stress *= 1.2
        elif humidity >= 50:
            stress *= 1.1
        
        return min(100, int(stress))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {}
        if temp is None or humidity is None:
            return attrs
        
        # Overall risk level
        stress_pct = self.native_value
        if stress_pct >= 80:
            attrs["risk_level"] = "Extreme Danger"
        elif stress_pct >= 60:
            attrs["risk_level"] = "Danger"
        elif stress_pct >= 40:
            attrs["risk_level"] = "Extreme Caution"
        elif stress_pct >= 20:
            attrs["risk_level"] = "Caution"
        else:
            attrs["risk_level"] = "Safe"
        
        # Recommendations
        if stress_pct >= 60:
            attrs["recommendation"] = "Avoid outdoor activity"
        elif stress_pct >= 40:
            attrs["recommendation"] = "Limit outdoor activity, stay hydrated"
        elif stress_pct >= 20:
            attrs["recommendation"] = "Take breaks, drink water"
        else:
            attrs["recommendation"] = "Normal activity safe"
        
        return attrs

