"""Weather entity for the SMHI integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ATTR_RAW_CURRENT, ATTR_RAW_FORECAST, CONF_NAME, DEFAULT_NAME, DOMAIN
from .coordinator import SmhiCoordinator
from .entity import smhi_device_info
from .forecast_builder import ForecastBuilder
from .helpers import (
    clean_value,
    condition_from_symbol,
    current_item_from_series,
    octas_to_percent,
    ptype_description,
    sun_is_up,
    symbol_description,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the SMHI weather entity."""
    async_add_entities([SmhiWeather(entry, hass.data[DOMAIN][entry.entry_id])])


class SmhiWeather(SingleCoordinatorWeatherEntity[SmhiCoordinator]):
    """Current conditions plus hourly, twice-daily and daily forecasts.

    SingleCoordinatorWeatherEntity pushes a fresh forecast to subscribed dashboard
    cards on every coordinator update.
    """

    _attr_has_entity_name = False
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
        | WeatherEntityFeature.FORECAST_DAILY
    )
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_wind_gust_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    # The raw series is far larger than the recorder's 16 kB attribute limit. Left
    # recorded, the recorder would drop every attribute of this entity and log a
    # warning on each update.
    _unrecorded_attributes = frozenset({ATTR_RAW_CURRENT, ATTR_RAW_FORECAST})

    def __init__(self, entry: ConfigEntry, coordinator: SmhiCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_weather_{entry.entry_id}"
        self._attr_name = entry.data.get(CONF_NAME, DEFAULT_NAME)
        self._attr_device_info = smhi_device_info(entry)

    @property
    def available(self) -> bool:
        return bool(self.coordinator.current_payload())

    def _series(self) -> list[dict[str, Any]]:
        series = self.coordinator.current_payload().get("timeSeries") or []
        return series if isinstance(series, list) else []

    def _current_data(self) -> dict[str, Any]:
        data = (current_item_from_series(self._series()) or {}).get("data") or {}
        return data if isinstance(data, dict) else {}

    def _daylight(self, moment) -> bool:
        """Whether the sun is up at this entry's location (not the Home location)."""
        return sun_is_up(self.coordinator.latitude, self.coordinator.longitude, moment)

    @property
    def condition(self):
        return condition_from_symbol(self._current_data(), daylight=self._daylight(dt_util.utcnow()))

    @property
    def native_temperature(self):
        return clean_value(self._current_data().get("air_temperature"), parameter="air_temperature")

    @property
    def native_pressure(self):
        return clean_value(
            self._current_data().get("air_pressure_at_mean_sea_level"),
            parameter="air_pressure_at_mean_sea_level",
        )

    @property
    def humidity(self):
        value = clean_value(self._current_data().get("relative_humidity"), parameter="relative_humidity")
        return int(value) if value is not None else None

    @property
    def wind_bearing(self):
        return clean_value(self._current_data().get("wind_from_direction"), parameter="wind_from_direction")

    @property
    def native_wind_speed(self):
        return clean_value(self._current_data().get("wind_speed"), parameter="wind_speed")

    @property
    def native_wind_gust_speed(self):
        return clean_value(self._current_data().get("wind_speed_of_gust"), parameter="wind_speed_of_gust")

    @property
    def cloud_coverage(self):
        return octas_to_percent(self._current_data().get("cloud_area_fraction"))

    @property
    def native_visibility(self):
        return clean_value(self._current_data().get("visibility_in_air"), parameter="visibility_in_air")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._current_data()
        return {
            "symbol_description": symbol_description(data.get("symbol_code")),
            "precipitation_type_description": ptype_description(
                data.get("predominant_precipitation_type_at_surface")
            ),
            ATTR_RAW_CURRENT: data,
            ATTR_RAW_FORECAST: self._series(),
        }

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        return ForecastBuilder(self._series(), self._daylight).build_hourly()

    @callback
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        return ForecastBuilder(self._series(), self._daylight).build_twice_daily()

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        return ForecastBuilder(self._series(), self._daylight).build_daily()
