from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_LAST_ERROR, ATTR_LAST_SUCCESS, ATTR_STALE, CONF_ENABLE_FROST_SENSORS, CONF_ENABLE_SLIPPERY_SENSORS, DOMAIN
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
    _attr_has_entity_name = False
    _attr_name = "SMHI API problem"
    _attr_translation_key = "api_problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    
    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_api_problem"
    
    @property
    def is_on(self) -> bool:
        return not self.coordinator.last_update_success
    
    @property
    def extra_state_attributes(self):
        return {ATTR_LAST_SUCCESS: self.coordinator.last_success, ATTR_LAST_ERROR: self.coordinator.last_error}


class SmhiFrostPossibleBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for frost possibility."""
    _attr_has_entity_name = False
    _attr_name = "SMHI Frost Possible"
    _attr_device_class = BinarySensorDeviceClass.COLD
    _attr_icon = "mdi:snowflake"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_frost_possible"

    @property
    def is_on(self) -> bool:
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        if temp is None:
            return False
        
        if temp <= 2:
            return True
        
        if temp <= 4 and humidity is not None:
            dew_point = calculate_dew_point(temp, humidity)
            return dew_point <= 0
        
        return False

    @property
    def extra_state_attributes(self):
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        humidity = clean_value(data.get("relative_humidity"), parameter="relative_humidity")
        
        attrs = {
            ATTR_STALE: not self.coordinator.last_update_success,
            ATTR_LAST_SUCCESS: self.coordinator.last_success,
            ATTR_LAST_ERROR: self.coordinator.last_error,
            "temperature": temp,
        }
        
        if temp is not None and humidity is not None:
            attrs["dew_point"] = round(calculate_dew_point(temp, humidity), 1)
            attrs["humidity"] = humidity
        
        return attrs


class SmhiSlipperyConditionsBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for slippery conditions."""
    _attr_has_entity_name = False
    _attr_name = "SMHI Slippery Conditions"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:car-brake-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.entry.entry_id}_slippery_conditions"

    @property
    def is_on(self) -> bool:
        """Return true if slippery conditions detected."""
        data = _data(self.coordinator)
        temp = clean_value(data.get("air_temperature"), parameter="air_temperature")
        frozen = clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part")
        precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
        
        if temp is None:
            return False
        
        if not (-5 <= temp <= 3):
            return False
        
        if frozen is not None and frozen > 0.3 and precip is not None and precip > 0.1:
            return True
        
        if -2 <= temp <= 1 and precip is not None and precip > 0.5:
            return True
        
        return False

    @property
    def extra_state_attributes(self):
        data = _data(self.coordinator)
        return {
            ATTR_STALE: not self.coordinator.last_update_success,
            ATTR_LAST_SUCCESS: self.coordinator.last_success,
            ATTR_LAST_ERROR: self.coordinator.last_error,
            "temperature": clean_value(data.get("air_temperature"), parameter="air_temperature"),
            "precipitation_frozen_part": clean_value(data.get("precipitation_frozen_part"), parameter="precipitation_frozen_part"),
            "precipitation_amount": clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean"),
        }
