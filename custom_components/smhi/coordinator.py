"""Data update coordinator for the SMHI integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SmhiApi
from .const import (
    CONF_FORECAST_TIMESERIES,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SCAN_INTERVAL,
    DEFAULT_FORECAST_TIMESERIES,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SmhiCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch the point forecast from SMHI on a schedule."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.api = SmhiApi(async_get_clientsession(hass))
        self.available_steps = 0
        self.last_success: str | None = None
        self.last_error: str | None = None
        self.last_good_data: dict[str, Any] | None = None
        scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )

    @property
    def latitude(self) -> float:
        return float(self.entry.data[CONF_LATITUDE])

    @property
    def longitude(self) -> float:
        return float(self.entry.data[CONF_LONGITUDE])

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the forecast, capping the series to the configured step count."""
        try:
            data = await self.api.get_point_forecast(self.latitude, self.longitude)

            # The API's own "timeseries=N" truncation is unreliable above the available
            # count (e.g. requesting 200 returns fewer than requesting 70), so we always
            # fetch the full series and cap it client-side. This makes the option a clean
            # upper bound: higher = more, limited by what SMHI actually provides.
            limit = int(
                self.entry.options.get(CONF_FORECAST_TIMESERIES, DEFAULT_FORECAST_TIMESERIES)
            )
            series = data.get("timeSeries")
            self.available_steps = len(series) if isinstance(series, list) else 0
            if isinstance(series, list) and 0 < limit < len(series):
                data = {**data, "timeSeries": series[:limit]}

            self.last_good_data = data
            self.last_success = dt_util.utcnow().isoformat()
            self.last_error = None
            return data
        except Exception as err:
            self.last_error = str(err)
            if self.last_good_data is not None:
                raise UpdateFailed(f"Using stale SMHI data: {err}") from err
            raise UpdateFailed(f"Failed fetching SMHI data: {err}") from err

    def current_payload(self) -> dict[str, Any]:
        """Return the freshest payload available (live or last-good)."""
        return self.data or self.last_good_data or {}
