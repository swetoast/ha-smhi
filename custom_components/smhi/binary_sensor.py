from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_LAST_ERROR, ATTR_LAST_SUCCESS, CONF_ENABLE_FROST_SENSORS, CONF_ENABLE_SLIPPERY_SENSORS, DOMAIN
from .entity import async_remove_stale_entities, smhi_device_info
from .helpers import clean_value, current_data_from_payload, frozen_part_fraction, frozen_part_percent


def _data(coordinator):
    return current_data_from_payload(coordinator.current_payload())


def calculate_dew_point(temp_c: float, humidity: float) -> float:
    """Calculate dew point using Magnus formula."""
    import math
    a = 17.27
    b = 237.7
    # Guard against log(0); SMHI relative humidity is a 0-100 percentage.
    rh_fraction = max(humidity, 1e-3) / 100.0
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh_fraction)
    return (b * alpha) / (a - alpha)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [SmhiApiProblemBinarySensor(coordinator)]
    
    if entry.options.get(CONF_ENABLE_FROST_SENSORS, True):
        sensors.append(SmhiFrostPossibleBinarySensor(coordinator))
    
    if entry.options.get(CONF_ENABLE_SLIPPERY_SENSORS, True):
        sensors.append(SmhiSlipperyConditionsBinarySensor(coordinator))
    
    async_remove_stale_entities(hass, entry, "binary_sensor", {sensor.unique_id for sensor in sensors})
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
        return smhi_device_info(self.coordinator.entry)

    @property
    def available(self) -> bool:
        """Stay available when an update fails, since that is when this sensor turns on."""
        return True
    
    @property
    def is_on(self) -> bool:
        return not self.coordinator.last_update_success
    
    @property
    def extra_state_attributes(self):
        return {ATTR_LAST_SUCCESS: self.coordinator.last_success, ATTR_LAST_ERROR: self.coordinator.last_error}


class SmhiFrostPossibleBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for frost possibility."""
    _attr_has_entity_name = True
    _attr_name = "Frost: Possible"
    _attr_device_class = BinarySensorDeviceClass.COLD
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_frost_possible"

    @property
    def device_info(self):
        return smhi_device_info(self.coordinator.entry)

    @property
    def available(self) -> bool:
        """Keep reporting from the last good forecast while SMHI is unreachable."""
        return bool(self.coordinator.current_payload())

    @property
    def is_on(self) -> bool:
        """Return True if frost risk exceeds 60%."""
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None or humidity is None:
            return False
        
        # Calculate frost risk using same formula as Frost: Risk sensor
        import math
        
        # No risk above 5°C
        if temp > 5:
            return False
        
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
        
        # Calculate risk
        risk = (temp_risk * spread_multiplier) + humidity_bonus
        
        # Trigger when risk exceeds 60%
        return risk > 60

    @property
    def extra_state_attributes(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {"temperature": temp}
        
        if temp is not None and humidity is not None:
            attrs["dew_point"] = round(calculate_dew_point(temp, humidity), 1)
            attrs["humidity"] = humidity
        
        return attrs


class SmhiSlipperyConditionsBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for slippery conditions."""
    _attr_has_entity_name = True
    _attr_name = "Slippery: Conditions"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:car-brake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_slippery_conditions"

    @property
    def device_info(self):
        return smhi_device_info(self.coordinator.entry)

    @property
    def available(self) -> bool:
        """Keep reporting from the last good forecast while SMHI is unreachable."""
        return bool(self.coordinator.current_payload())

    @property
    def is_on(self) -> bool:
        """Return True if slippery risk exceeds 50%."""
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        frozen = frozen_part_fraction(data)
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        if temp is None:
            return False
        
        # Calculate slippery risk using same formula as Slippery: Risk sensor
        # No risk outside dangerous temperature range
        if temp < -10 or temp > 5:
            return False
        
        # Base risk from distance to 0°C
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
        
        # Trigger when risk exceeds 50%
        return total_risk > 50

    @property
    def extra_state_attributes(self):
        data = _data(self.coordinator)
        return {
            "temperature": clean_value(data.get("air_temperature"), parameter="air_temperature"),
            "precipitation_frozen_part": frozen_part_percent(data),
            "precipitation_amount": clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean"),
        }
