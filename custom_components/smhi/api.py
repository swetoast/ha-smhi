from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from aiohttp import ClientResponseError, ClientSession
from yarl import URL
from .const import API_BASE

@dataclass(slots=True)
class SmhiApi:
    session: ClientSession
    async def _get_json(self, path: str, query: dict[str, str] | None = None) -> dict[str, Any]:
        url = URL(f"{API_BASE}/{path.lstrip('/')}")
        if query:
            url = url.update_query(query)
        async with self.session.get(url, headers={"Accept": "application/json", "Accept-Encoding": "gzip"}) as response:
            response.raise_for_status()
            return await response.json(content_type=None)
    async def get_point_forecast(self, latitude: float, longitude: float, timeseries: int | None = None) -> dict[str, Any]:
        query = {"timeseries": str(timeseries)} if timeseries is not None else None
        return await self._get_json(f"geotype/point/lon/{longitude:.6f}/lat/{latitude:.6f}/data.json", query)
    
    async def validate_point(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Validate coordinates by fetching forecast data."""
        return await self.get_point_forecast(latitude, longitude)
    
    async def get_parameters(self) -> dict[str, Any]:
        return await self._get_json("parameter.json")
    async def get_times(self) -> dict[str, Any]:
        return await self._get_json("times.json")
    async def get_approved_time(self) -> dict[str, Any]:
        try:
            return await self._get_json("approvedtime.json")
        except ClientResponseError as err:
            if err.status == 404:
                return await self._get_json("createdtime.json")
            raise
