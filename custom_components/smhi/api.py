"""Async client for the SMHI snow1g point forecast."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from yarl import URL

from .const import API_BASE

REQUEST_TIMEOUT = ClientTimeout(total=30)


@dataclass(slots=True)
class SmhiApi:
    """Minimal client for the SMHI Open Data meteorological forecast API."""

    session: ClientSession

    async def _get_json(self, path: str) -> dict[str, Any]:
        url = URL(f"{API_BASE}/{path.lstrip('/')}")
        headers = {"Accept": "application/json", "Accept-Encoding": "gzip"}
        async with self.session.get(url, headers=headers, timeout=REQUEST_TIMEOUT) as response:
            response.raise_for_status()
            return await response.json(content_type=None)

    async def get_point_forecast(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Fetch the full point forecast for a coordinate.

        The response carries createdTime, referenceTime, the grid point and every
        forecast step, so no other endpoint is needed.
        """
        return await self._get_json(
            f"geotype/point/lon/{longitude:.6f}/lat/{latitude:.6f}/data.json"
        )

    async def validate_point(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Validate coordinates by fetching forecast data."""
        return await self.get_point_forecast(latitude, longitude)
