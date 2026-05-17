from __future__ import annotations
from datetime import timedelta
import logging
from typing import Any
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from .api import SmhiApi
from .const import CONF_FORECAST_TIMESERIES, CONF_LATITUDE, CONF_LONGITUDE, CONF_SCAN_INTERVAL, DEFAULT_FORECAST_TIMESERIES, DEFAULT_SCAN_INTERVAL_MIN, DOMAIN, PARAMETER_FALLBACK

_LOGGER = logging.getLogger(__name__)

class SmhiCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.api = SmhiApi(async_get_clientsession(hass))
        self.parameters: list[dict[str, Any]] = list(PARAMETER_FALLBACK)
        self.times: list[str] = []
        self.approved_time: str | None = None
        self.approved_reference_time: str | None = None
        self.last_success: str | None = None
        self.last_error: str | None = None
        self.last_good_data: dict[str, Any] | None = None
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN))))
    @property
    def latitude(self) -> float: return float(self.entry.data[CONF_LATITUDE])
    @property
    def longitude(self) -> float: return float(self.entry.data[CONF_LONGITUDE])
    async def _refresh_metadata(self) -> None:
        try:
            payload = await self.api.get_parameters(); params = payload.get("parameter")
            if isinstance(params, list) and params: self.parameters = params
        except Exception as err: _LOGGER.debug("Failed updating SMHI parameter metadata: %s", err)
        try:
            payload = await self.api.get_times(); times = payload.get("time")
            if isinstance(times, list): self.times = times
        except Exception as err: _LOGGER.debug("Failed updating SMHI times metadata: %s", err)
        try:
            payload = await self.api.get_approved_time(); self.approved_time = payload.get("approvedTime") or payload.get("createdTime"); self.approved_reference_time = payload.get("referenceTime")
        except Exception as err: _LOGGER.debug("Failed updating SMHI approved time metadata: %s", err)
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            await self._refresh_metadata()
            data = await self.api.get_point_forecast(self.latitude, self.longitude, int(self.entry.options.get(CONF_FORECAST_TIMESERIES, DEFAULT_FORECAST_TIMESERIES)))
            self.last_good_data = data; self.last_success = dt_util.utcnow().isoformat(); self.last_error = None
            return data
        except Exception as err:
            self.last_error = str(err)
            if self.last_good_data is not None: raise UpdateFailed(f"Using stale SMHI data: {err}") from err
            raise UpdateFailed(f"Failed fetching SMHI data: {err}") from err
    def current_payload(self) -> dict[str, Any]: return self.data or self.last_good_data or {}
