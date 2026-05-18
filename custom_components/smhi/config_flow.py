from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientConnectorError, ClientResponseError, ServerTimeoutError
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmhiApi
from .const import (
    CONF_ENABLE_COMFORT_SENSORS,
    CONF_ENABLE_FROST_SENSORS,
    CONF_ENABLE_SLIPPERY_SENSORS,
    CONF_ENABLE_IMPACT_SENSOR,
    CONF_ENABLE_PRACTICAL_SENSORS,
    CONF_ENABLE_THERMAL_SENSORS,
    CONF_FORECAST_TIMESERIES,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_USE_HOME_LOCATION,
    DEFAULT_FORECAST_TIMESERIES,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_COORDINATES,
    ERROR_OUT_OF_BOUNDS,
    ERROR_UNKNOWN,
    SETUP_VALIDATION_TIMEOUT,
)


async def _validate_input(hass, latitude: float, longitude: float) -> dict[str, Any]:
    """Validate coordinates and fetch SMHI data."""
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError(ERROR_INVALID_COORDINATES)
    
    api = SmhiApi(async_get_clientsession(hass))
    
    try:
        async with async_timeout.timeout(SETUP_VALIDATION_TIMEOUT):
            payload = await api.validate_point(latitude, longitude)
    except ClientResponseError as err:
        # SMHI API returned an HTTP error
        if err.status == 400:
            # Bad request - coordinates out of bounds
            raise ValueError(ERROR_OUT_OF_BOUNDS) from err
        # Other HTTP errors
        raise ConnectionError(ERROR_CANNOT_CONNECT) from err
    except (TimeoutError, asyncio.TimeoutError, ServerTimeoutError) as err:
        # Timeout errors
        raise ConnectionError(ERROR_CANNOT_CONNECT) from err
    except (ClientConnectorError, OSError) as err:
        # Connection errors
        raise ConnectionError(ERROR_CANNOT_CONNECT) from err
    except Exception as err:
        # Unexpected errors
        raise ConnectionError(ERROR_UNKNOWN) from err
    
    # Extract grid point information
    geometry = payload.get("geometry") or {}
    coordinates = geometry.get("coordinates")
    grid_point = "unknown"
    if isinstance(coordinates, list) and len(coordinates) >= 2:
        grid_point = f"{coordinates[1]:.6f}, {coordinates[0]:.6f}"
    
    return {
        "created_time": payload.get("createdTime"),
        "reference_time": payload.get("referenceTime"),
        "grid_point": grid_point
    }


def _schema(hass, defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema({
        vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
        vol.Optional(CONF_USE_HOME_LOCATION, default=defaults.get(CONF_USE_HOME_LOCATION, True)): bool,
        vol.Optional(CONF_LATITUDE, default=defaults.get(CONF_LATITUDE, hass.config.latitude)): vol.All(vol.Coerce(float), vol.Range(min=-90, max=90)),
        vol.Optional(CONF_LONGITUDE, default=defaults.get(CONF_LONGITUDE, hass.config.longitude)): vol.All(vol.Coerce(float), vol.Range(min=-180, max=180)),
    })


class SmhiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._validated_data: dict[str, Any] | None = None
        self._setup_info: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Process form submission
            name = user_input.get(CONF_NAME, DEFAULT_NAME).strip() or DEFAULT_NAME
            use_home = bool(user_input.get(CONF_USE_HOME_LOCATION, True))
            latitude = self.hass.config.latitude if use_home else user_input.get(CONF_LATITUDE)
            longitude = self.hass.config.longitude if use_home else user_input.get(CONF_LONGITUDE)
            
            try:
                latitude = float(latitude)
                longitude = float(longitude)
                self._setup_info = await _validate_input(self.hass, latitude, longitude)
            except ValueError as err:
                # Validation errors (invalid coordinates, out of bounds)
                error_str = str(err)
                if error_str in (ERROR_INVALID_COORDINATES, ERROR_OUT_OF_BOUNDS):
                    errors["base"] = error_str
                else:
                    errors["base"] = ERROR_UNKNOWN
            except ConnectionError as err:
                # Connection errors
                error_str = str(err)
                if error_str in (ERROR_CANNOT_CONNECT, ERROR_UNKNOWN):
                    errors["base"] = error_str
                else:
                    errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:
                # Catch-all for unexpected errors
                errors["base"] = ERROR_UNKNOWN
            else:
                # Validation successful
                await self.async_set_unique_id(f"{DOMAIN}_{latitude:.6f}_{longitude:.6f}")
                self._abort_if_unique_id_configured()
                self._validated_data = {
                    CONF_NAME: name,
                    CONF_USE_HOME_LOCATION: use_home,
                    CONF_LATITUDE: latitude,
                    CONF_LONGITUDE: longitude
                }
                return await self.async_step_confirm()
        
        # Show the form (initial load or after error)
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self.hass, user_input),
            errors=errors,
            description_placeholders={
                "home_latitude": f"{self.hass.config.latitude:.6f}",
                "home_longitude": f"{self.hass.config.longitude:.6f}"
            },
        )

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None):
        if self._validated_data is None:
            return await self.async_step_user()
        if user_input is not None:
            return await self.async_step_sensors()
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": self._validated_data[CONF_NAME],
                "latitude": f"{self._validated_data[CONF_LATITUDE]:.6f}",
                "longitude": f"{self._validated_data[CONF_LONGITUDE]:.6f}",
                "grid_point": str(self._setup_info.get("grid_point", "unknown")),
                "reference_time": str(self._setup_info.get("reference_time") or "unknown"),
                "created_time": str(self._setup_info.get("created_time") or "unknown"),
            },
        )

    async def async_step_sensors(self, user_input: dict[str, Any] | None = None):
        """Configure optional sensor groups."""
        if self._validated_data is None:
            return await self.async_step_user()
        
        if user_input is not None:
            # Create entry with both data and options
            return self.async_create_entry(
                title=self._validated_data[CONF_NAME],
                data=self._validated_data,
                options={
                    CONF_FORECAST_TIMESERIES: DEFAULT_FORECAST_TIMESERIES,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_MIN,
                    CONF_ENABLE_COMFORT_SENSORS: user_input.get(CONF_ENABLE_COMFORT_SENSORS, True),
                    CONF_ENABLE_FROST_SENSORS: user_input.get(CONF_ENABLE_FROST_SENSORS, True),
                    CONF_ENABLE_SLIPPERY_SENSORS: user_input.get(CONF_ENABLE_SLIPPERY_SENSORS, True),
                    CONF_ENABLE_IMPACT_SENSOR: user_input.get(CONF_ENABLE_IMPACT_SENSOR, True),
                    CONF_ENABLE_PRACTICAL_SENSORS: user_input.get(CONF_ENABLE_PRACTICAL_SENSORS, True),
                    CONF_ENABLE_THERMAL_SENSORS: user_input.get(CONF_ENABLE_THERMAL_SENSORS, True),
                }
            )
        
        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema({
                vol.Optional(CONF_ENABLE_COMFORT_SENSORS, default=True): bool,
                vol.Optional(CONF_ENABLE_FROST_SENSORS, default=True): bool,
                vol.Optional(CONF_ENABLE_SLIPPERY_SENSORS, default=True): bool,
                vol.Optional(CONF_ENABLE_IMPACT_SENSOR, default=True): bool,
                vol.Optional(CONF_ENABLE_PRACTICAL_SENSORS, default=True): bool,
                vol.Optional(CONF_ENABLE_THERMAL_SENSORS, default=True): bool,
            }),
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reconfigure_entry()
        defaults = dict(entry.data)
        errors: dict[str, str] = {}
        if user_input:
            defaults.update(user_input)
            name = defaults.get(CONF_NAME, DEFAULT_NAME).strip() or DEFAULT_NAME
            use_home = bool(defaults.get(CONF_USE_HOME_LOCATION, True))
            latitude = self.hass.config.latitude if use_home else defaults.get(CONF_LATITUDE)
            longitude = self.hass.config.longitude if use_home else defaults.get(CONF_LONGITUDE)
            try:
                latitude = float(latitude)
                longitude = float(longitude)
                await _validate_input(self.hass, latitude, longitude)
            except ValueError as err:
                errors["base"] = str(err) if str(err) in {ERROR_INVALID_COORDINATES, ERROR_OUT_OF_BOUNDS} else ERROR_UNKNOWN
            except ConnectionError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:
                errors["base"] = ERROR_UNKNOWN
            else:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_NAME: name, CONF_USE_HOME_LOCATION: use_home, CONF_LATITUDE: latitude, CONF_LONGITUDE: longitude})
        return self.async_show_form(step_id="reconfigure", data_schema=_schema(self.hass, defaults), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SmhiOptionsFlow(config_entry)


class SmhiOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Optional(CONF_FORECAST_TIMESERIES, default=self.entry.options.get(CONF_FORECAST_TIMESERIES, DEFAULT_FORECAST_TIMESERIES)): vol.All(vol.Coerce(int), vol.Range(min=1, max=200)),
            vol.Optional(CONF_SCAN_INTERVAL, default=self.entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN)): vol.All(vol.Coerce(int), vol.Range(min=5, max=180)),
            vol.Optional(CONF_ENABLE_COMFORT_SENSORS, default=self.entry.options.get(CONF_ENABLE_COMFORT_SENSORS, True)): bool,
            vol.Optional(CONF_ENABLE_FROST_SENSORS, default=self.entry.options.get(CONF_ENABLE_FROST_SENSORS, True)): bool,
            vol.Optional(CONF_ENABLE_SLIPPERY_SENSORS, default=self.entry.options.get(CONF_ENABLE_SLIPPERY_SENSORS, True)): bool,
            vol.Optional(CONF_ENABLE_IMPACT_SENSOR, default=self.entry.options.get(CONF_ENABLE_IMPACT_SENSOR, True)): bool,
            vol.Optional(CONF_ENABLE_PRACTICAL_SENSORS, default=self.entry.options.get(CONF_ENABLE_PRACTICAL_SENSORS, True)): bool,
            vol.Optional(CONF_ENABLE_THERMAL_SENSORS, default=self.entry.options.get(CONF_ENABLE_THERMAL_SENSORS, True)): bool,
        }))
