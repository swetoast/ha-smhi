from __future__ import annotations
from typing import Any
from homeassistant.components.weather import Forecast, WeatherEntity, WeatherEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfPressure, UnitOfSpeed, UnitOfTemperature
try:
    from homeassistant.const import UnitOfPrecipitationDepth
except ImportError:
    class UnitOfPrecipitationDepth:
        MILLIMETERS = "mm"
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from .const import ATTR_RAW_CURRENT, ATTR_RAW_FORECAST, CONF_NAME, DOMAIN
from .helpers import clean_value, condition_from_symbol, current_item_from_series, octas_to_percent, ptype_description, symbol_description

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    async_add_entities([SmhiWeather(entry, hass.data[DOMAIN][entry.entry_id])])

class SmhiWeather(CoordinatorEntity, WeatherEntity):
    _attr_has_entity_name = False
    _attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_wind_gust_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    def __init__(self, entry: ConfigEntry, coordinator) -> None:
        super().__init__(coordinator); self._attr_unique_id = f"{DOMAIN}_weather_{entry.entry_id}"; self._attr_name = entry.data.get(CONF_NAME, "SMHI")
    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self.coordinator.entry.entry_id)}, "name": self.coordinator.entry.data.get(CONF_NAME, "SMHI"), "manufacturer": "SMHI", "model": "Open Data forecast", "configuration_url": "https://opendata.smhi.se/metfcst/snow1gv1/"}
    @property
    def available(self) -> bool: return bool(self.coordinator.current_payload())
    def _series(self) -> list[dict[str, Any]]:
        series = self.coordinator.current_payload().get("timeSeries") or []
        return series if isinstance(series, list) else []
    def _current_item(self) -> dict[str, Any] | None: return current_item_from_series(self._series())
    def _current_data(self) -> dict[str, Any]:
        data = (self._current_item() or {}).get("data") or {}
        return data if isinstance(data, dict) else {}
    @property
    def condition(self): return condition_from_symbol(self._current_data())
    @property
    def native_temperature(self): return clean_value(self._current_data().get("air_temperature"), parameter="air_temperature")
    @property
    def native_pressure(self): return clean_value(self._current_data().get("air_pressure_at_mean_sea_level"), parameter="air_pressure_at_mean_sea_level")
    @property
    def humidity(self):
        v = clean_value(self._current_data().get("relative_humidity"), parameter="relative_humidity")
        return int(v) if v is not None else None
    @property
    def wind_bearing(self): return clean_value(self._current_data().get("wind_from_direction"), parameter="wind_from_direction")
    @property
    def native_wind_speed(self): return clean_value(self._current_data().get("wind_speed"), parameter="wind_speed")
    @property
    def native_wind_gust_speed(self): return clean_value(self._current_data().get("wind_speed_of_gust"), parameter="wind_speed_of_gust")
    @property
    def cloud_coverage(self): return octas_to_percent(self._current_data().get("cloud_area_fraction"))
    @property
    def native_visibility(self): return clean_value(self._current_data().get("visibility_in_air"), parameter="visibility_in_air")
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._current_data(); return {"symbol_description": symbol_description(data.get("symbol_code")), "precipitation_type_description": ptype_description(data.get("predominant_precipitation_type_at_surface")), ATTR_RAW_CURRENT: data, ATTR_RAW_FORECAST: self._series()}
    async def async_forecast_hourly(self) -> list[Forecast]:
        out: list[Forecast] = []
        for item in self._series():
            data = item.get("data") or {}; parsed = dt_util.parse_datetime(item.get("time")) if item.get("time") else None
            if parsed is None or not isinstance(data, dict): continue
            precip = clean_value(data.get("precipitation_amount_mean_deterministic"), parameter="precipitation_amount_mean_deterministic")
            if precip is None: precip = clean_value(data.get("precipitation_amount_mean"), parameter="precipitation_amount_mean")
            row: Forecast = {"datetime": dt_util.as_utc(parsed).isoformat(), "condition": condition_from_symbol(data), "native_temperature": clean_value(data.get("air_temperature"), parameter="air_temperature"), "native_pressure": clean_value(data.get("air_pressure_at_mean_sea_level"), parameter="air_pressure_at_mean_sea_level"), "humidity": clean_value(data.get("relative_humidity"), parameter="relative_humidity"), "native_wind_speed": clean_value(data.get("wind_speed"), parameter="wind_speed"), "native_wind_gust_speed": clean_value(data.get("wind_speed_of_gust"), parameter="wind_speed_of_gust"), "wind_bearing": clean_value(data.get("wind_from_direction"), parameter="wind_from_direction"), "cloud_coverage": octas_to_percent(data.get("cloud_area_fraction")), "native_precipitation": precip, "precipitation_probability": clean_value(data.get("probability_of_precipitation"), parameter="probability_of_precipitation")}
            out.append({k:v for k,v in row.items() if v is not None})
        return out
