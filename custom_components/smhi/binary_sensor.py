from __future__ import annotations
from datetime import datetime

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_LAST_ERROR, ATTR_LAST_SUCCESS, ATTR_STALE, CONF_ENABLE_FROST_SENSORS, CONF_ENABLE_SLIPPERY_SENSORS, CONF_NAME, DOMAIN
from .helpers import clean_value, current_data_from_payload


def _data(coordinator):
    return current_data_from_payload(coordinator.current_payload())


def calculate_dew_point(temp_c: float, humidity: float) -> float:
    """Calculate dew point using Magnus formula."""
    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + (humidity / 100.0)
    return (b * alpha) / (a - alpha)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [SmhiApiProblemBinarySensor(coordinator)]
    
    if entry.options.get(CONF_ENABLE_FROST_SENSORS, True):
        sensors.append(SmhiFrostPossibleBinarySensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_SLIPPERY_SENSORS, True):
        sensors.append(SmhiSlipperyConditionsBinarySensor(coordinator))
    
    async_add_entities(sensors)


class SmhiApiProblemBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "API problem"
    _attr_translation_key = "api_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_api_problem"
    
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
    def is_on(self) -> bool:
        return not self.coordinator.last_update_success
    
    @property
    def extra_state_attributes(self):
        return {ATTR_LAST_SUCCESS: self.coordinator.last_success, ATTR_LAST_ERROR: self.coordinator.last_error}


class SmhiFrostPossibleBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for frost possibility with hysteresis and time-of-day awareness.
    
    Uses smart thresholds to prevent flapping:
    - Night (22:00-08:00): More sensitive (frost more common)
      Turn ON at 55%, turn OFF at 45%
    - Day (08:00-22:00): Less sensitive (sun reduces frost)
      Turn ON at 65%, turn OFF at 55%
    
    Hysteresis prevents rapid on/off cycling when hovering near threshold.
    """
    _attr_has_entity_name = True
    _attr_name = "Frost: Possible"
    _attr_device_class = BinarySensorDeviceClass.COLD
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_frost_possible"
        self._previous_state = None  # Track state for hysteresis

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": self.coordinator.entry.data.get(CONF_NAME, "SMHI"),
            "manufacturer": "SMHI",
            "model": "Open Data forecast",
            "configuration_url": "https://opendata.smhi.se/metfcst/snow1gv1/",
        }
    
    def _calculate_frost_risk(self) -> float | None:
        """Calculate frost risk percentage (0-100).
        
        Returns None if data unavailable, otherwise risk percentage.
        """
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return None
        
        # No risk above 5°C
        if temp > 5:
            return 0.0
        
        import math
        
        # Base risk from temperature using sigmoid curve
        temp_risk = 100 / (1 + math.exp((temp - 2) * 1.5))
        
        # Dew point spread factor
        dew_point = calculate_dew_point(temp, humidity)
        spread = temp - dew_point
        
        if spread < 1:
            spread_multiplier = 1.3
        elif spread < 2:
            spread_multiplier = 1.15
        elif spread < 3:
            spread_multiplier = 1.05
        else:
            spread_multiplier = 1.0
        
        # Humidity bonus
        if humidity > 80:
            humidity_bonus = 15
        elif humidity > 70:
            humidity_bonus = 10
        elif humidity > 60:
            humidity_bonus = 5
        else:
            humidity_bonus = 0
        
        # Calculate final risk
        risk = (temp_risk * spread_multiplier) + humidity_bonus
        return min(100.0, risk)  # Cap at 100%

    @property
    def is_on(self) -> bool:
        """Return True if frost risk exceeds threshold with hysteresis and time-of-day awareness."""
        risk = self._calculate_frost_risk()
        
        if risk is None:
            # Data unavailable, keep previous state or default to False
            return self._previous_state if self._previous_state is not None else False
        
        # Time-of-day thresholds
        current_hour = datetime.now().hour
        is_night = current_hour >= 22 or current_hour < 8
        
        if is_night:
            # Night: More sensitive (frost more common during coldest hours)
            threshold_on = 55.0
            threshold_off = 45.0
        else:
            # Day: Less sensitive (sun reduces frost even at higher calculated risk)
            threshold_on = 65.0
            threshold_off = 55.0
        
        # Hysteresis logic: different thresholds for turning on vs off
        if self._previous_state is None or not self._previous_state:
            # Currently OFF: use ON threshold
            new_state = risk >= threshold_on
        else:
            # Currently ON: use OFF threshold (lower to prevent flapping)
            new_state = risk >= threshold_off
        
        # Update state tracker
        self._previous_state = new_state
        return new_state

    @property
    def extra_state_attributes(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {"temperature": temp}
        
        if temp is not None and humidity is not None:
            attrs["dew_point"] = round(calculate_dew_point(temp, humidity), 1)
            attrs["humidity"] = humidity
        
        # Add frost risk for debugging
        risk = self._calculate_frost_risk()
        if risk is not None:
            attrs["frost_risk"] = round(risk, 1)
        
        # Add current thresholds for transparency
        current_hour = datetime.now().hour
        is_night = current_hour >= 22 or current_hour < 8
        attrs["time_period"] = "night" if is_night else "day"
        attrs["threshold_on"] = 55.0 if is_night else 65.0
        attrs["threshold_off"] = 45.0 if is_night else 55.0
        
        return attrs


class SmhiSlipperyConditionsBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for slippery conditions with hysteresis.
    
    Uses smart thresholds to prevent flapping:
    - Turn ON at 50% risk
    - Turn OFF at 40% risk (10% hysteresis gap)
    
    Special case: Heavy precipitation + frozen conditions lowers threshold to 40% ON / 35% OFF
    """
    _attr_has_entity_name = True
    _attr_name = "Slippery: Conditions"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:car-brake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_slippery_conditions"
        self._previous_state = None  # Track state for hysteresis

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": self.coordinator.entry.data.get(CONF_NAME, "SMHI"),
            "manufacturer": "SMHI",
            "model": "Open Data forecast",
            "configuration_url": "https://opendata.smhi.se/metfcst/snow1gv1/",
        }
    
    def _calculate_slippery_risk(self) -> tuple[float | None, bool]:
        """Calculate slippery risk percentage (0-100) and heavy precipitation flag.
        
        Returns (risk, is_heavy_frozen_precipitation) tuple.
        risk is None if data unavailable.
        """
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        frozen = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        if temp is None:
            return None, False
        
        # No risk outside dangerous temperature range
        if temp < -10 or temp > 5:
            return 0.0, False
        
        # Base risk from distance to 0°C (most dangerous point)
        distance_from_zero = abs(temp)
        
        if distance_from_zero <= 1:
            temp_risk = 50
        elif distance_from_zero <= 2:
            temp_risk = 40
        elif distance_from_zero <= 3:
            temp_risk = 30
        elif distance_from_zero <= 5:
            temp_risk = 20
        else:
            temp_risk = 10
        
        # Frozen precipitation factor
        frozen_risk = 0
        if frozen is not None:
            if frozen > 0.7:
                frozen_risk = 30
            elif frozen > 0.5:
                frozen_risk = 25
            elif frozen > 0.3:
                frozen_risk = 20
            elif frozen > 0.1:
                frozen_risk = 10
        
        # Precipitation intensity factor
        precip_risk = 0
        if precip is not None:
            if precip > 2:
                precip_risk = 20
            elif precip > 1:
                precip_risk = 15
            elif precip > 0.5:
                precip_risk = 10
            elif precip > 0.1:
                precip_risk = 5
        
        total_risk = temp_risk + frozen_risk + precip_risk
        
        # Check for heavy frozen precipitation (very dangerous)
        is_heavy = (precip is not None and precip > 2.0 and 
                   frozen is not None and frozen > 0.5)
        
        return min(100.0, total_risk), is_heavy

    @property
    def is_on(self) -> bool:
        """Return True if slippery risk exceeds threshold with hysteresis."""
        risk, is_heavy_frozen = self._calculate_slippery_risk()
        
        if risk is None:
            # Data unavailable, keep previous state or default to False
            return self._previous_state if self._previous_state is not None else False
        
        # Adjust thresholds for heavy frozen precipitation
        if is_heavy_frozen:
            # Very dangerous conditions: lower threshold
            threshold_on = 40.0
            threshold_off = 35.0
        else:
            # Normal conditions
            threshold_on = 50.0
            threshold_off = 40.0
        
        # Hysteresis logic: different thresholds for turning on vs off
        if self._previous_state is None or not self._previous_state:
            # Currently OFF: use ON threshold
            new_state = risk >= threshold_on
        else:
            # Currently ON: use OFF threshold (lower to prevent flapping)
            new_state = risk >= threshold_off
        
        # Update state tracker
        self._previous_state = new_state
        return new_state

    @property
    def extra_state_attributes(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        frozen = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        attrs = {
            "temperature": temp,
            "precipitation_frozen_part": frozen,
            "precipitation_amount": precip,
        }
        
        # Add slippery risk for debugging
        risk, is_heavy = self._calculate_slippery_risk()
        if risk is not None:
            attrs["slippery_risk"] = round(risk, 1)
        
        # Add current thresholds for transparency
        if is_heavy:
            attrs["condition"] = "heavy_frozen_precipitation"
            attrs["threshold_on"] = 40.0
            attrs["threshold_off"] = 35.0
        else:
            attrs["condition"] = "normal"
            attrs["threshold_on"] = 50.0
            attrs["threshold_off"] = 40.0
        
        return attrs
