from __future__ import annotations

from collections import defaultdict
from typing import Any

from homeassistant.components.weather import Forecast
from homeassistant.util import dt as dt_util

from .const import DAYTIME_END_HOUR, DAYTIME_START_HOUR
from .helpers import (
    avg,
    clean_value,
    condition_from_symbol,
    max_value,
    min_value,
    most_common,
    octas_to_percent,
    parse_time,
    sum_value,
)


class ForecastBuilder:
    """Builder class for creating weather forecasts from time series data."""

    def __init__(self, series: list[dict[str, Any]]) -> None:
        """Initialize forecast builder with time series data.
        
        Args:
            series: List of time series items from API
        """
        self.series = series if isinstance(series, list) else []

    def build_hourly(self, max_hours: int | None = None) -> list[Forecast]:
        """Build hourly forecast.
        
        Args:
            max_hours: Maximum number of hours to include (None for all)
            
        Returns:
            List of hourly forecast items
        """
        forecast = []
        for i, item in enumerate(self.series):
            if max_hours is not None and i >= max_hours:
                break
            
            row = self._build_hourly_row(item)
            if row:
                forecast.append(row)
        
        return forecast

    def build_daily(self, max_days: int | None = None) -> list[Forecast]:
        """Build daily forecast with aggregated data.
        
        Args:
            max_days: Maximum number of days to include (None for all)
            
        Returns:
            List of daily forecast items
        """
        grouped = self._group_by_date()
        
        forecast = []
        for i, date_key in enumerate(sorted(grouped.keys())):
            if max_days is not None and i >= max_days:
                break
            
            row = self._aggregate_items(grouped[date_key])
            if row:
                forecast.append(row)
        
        return forecast

    def build_twice_daily(self, max_periods: int | None = None) -> list[Forecast]:
        """Build twice-daily forecast (day and night periods).
        
        Args:
            max_periods: Maximum number of periods to include (None for all)
            
        Returns:
            List of twice-daily forecast items
        """
        grouped = self._group_by_day_night()
        
        # Sort by date, then night before day
        sorted_keys = sorted(grouped.keys(), key=lambda k: (k[0], not k[1]))
        
        forecast = []
        for i, key in enumerate(sorted_keys):
            if max_periods is not None and i >= max_periods:
                break
            
            date_key, is_daytime = key
            row = self._aggregate_items(grouped[key], is_daytime=is_daytime)
            if row:
                forecast.append(row)
        
        return forecast

    def _build_hourly_row(self, item: dict[str, Any]) -> Forecast | None:
        """Build a single hourly forecast row.
        
        Args:
            item: Time series item
            
        Returns:
            Forecast dictionary or None if invalid
        """
        if not isinstance(item, dict):
            return None
        
        parsed = parse_time(item.get("time"))
        data = item.get("data")
        
        if parsed is None or not isinstance(data, dict):
            return None

        precipitation = self._get_precipitation_value(data)

        row: Forecast = {
            "datetime": parsed.isoformat(),
            "condition": condition_from_symbol(data),
            "native_temperature": clean_value(data.get("air_temperature"), parameter="air_temperature"),
            "native_pressure": clean_value(
                data.get("air_pressure_at_mean_sea_level"),
                parameter="air_pressure_at_mean_sea_level",
            ),
            "humidity": clean_value(data.get("relative_humidity"), parameter="relative_humidity"),
            "native_wind_speed": clean_value(data.get("wind_speed"), parameter="wind_speed"),
            "native_wind_gust_speed": clean_value(data.get("wind_speed_of_gust"), parameter="wind_speed_of_gust"),
            "wind_bearing": clean_value(data.get("wind_from_direction"), parameter="wind_from_direction"),
            "cloud_coverage": octas_to_percent(data.get("cloud_area_fraction")),
            "native_precipitation": precipitation,
            "precipitation_probability": clean_value(
                data.get("probability_of_precipitation"),
                parameter="probability_of_precipitation",
            ),
        }
        
        # Filter out None values
        return {key: value for key, value in row.items() if value is not None}

    def _aggregate_items(
        self, 
        items: list[dict[str, Any]], 
        *, 
        is_daytime: bool | None = None
    ) -> Forecast | None:
        """Aggregate multiple time series items into a single forecast period.
        
        Args:
            items: List of time series items to aggregate
            is_daytime: Optional flag for day/night period
            
        Returns:
            Aggregated forecast dictionary or None
        """
        if not items:
            return None
        
        # Parse and validate all items
        parsed_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            parsed_time = parse_time(item.get("time"))
            data = item.get("data")
            if parsed_time is not None and isinstance(data, dict):
                parsed_items.append((parsed_time, data))
        
        if not parsed_items:
            return None
        
        times = [item[0] for item in parsed_items]
        datas = [item[1] for item in parsed_items]
        
        # Aggregate precipitation values
        precipitation_values = [
            self._get_precipitation_value(data) for data in datas
        ]
        
        row: Forecast = {
            "datetime": min(times).isoformat(),
            "condition": most_common(condition_from_symbol(data) for data in datas),
            "native_temperature": max_value(
                (data.get("air_temperature") for data in datas), 
                parameter="air_temperature"
            ),
            "native_templow": min_value(
                (data.get("air_temperature") for data in datas), 
                parameter="air_temperature"
            ),
            "native_pressure": avg(
                (data.get("air_pressure_at_mean_sea_level") for data in datas),
                parameter="air_pressure_at_mean_sea_level",
            ),
            "humidity": avg(
                (data.get("relative_humidity") for data in datas), 
                parameter="relative_humidity"
            ),
            "native_wind_speed": max_value(
                (data.get("wind_speed") for data in datas), 
                parameter="wind_speed"
            ),
            "native_wind_gust_speed": max_value(
                (data.get("wind_speed_of_gust") for data in datas),
                parameter="wind_speed_of_gust",
            ),
            "wind_bearing": avg(
                (data.get("wind_from_direction") for data in datas), 
                parameter="wind_from_direction"
            ),
            "cloud_coverage": avg(
                (octas_to_percent(data.get("cloud_area_fraction")) for data in datas)
            ),
            "native_precipitation": sum_value(precipitation_values),
            "precipitation_probability": max_value(
                (data.get("probability_of_precipitation") for data in datas),
                parameter="probability_of_precipitation",
            ),
        }
        
        if is_daytime is not None:
            row["is_daytime"] = is_daytime
        
        # Filter out None values
        return {key: value for key, value in row.items() if value is not None}

    def _get_precipitation_value(self, data: dict[str, Any]) -> float | None:
        """Get precipitation value, preferring deterministic over mean.
        
        Args:
            data: Data dictionary
            
        Returns:
            Precipitation value or None
        """
        precipitation = clean_value(
            data.get("precipitation_amount_mean_deterministic"),
            parameter="precipitation_amount_mean_deterministic",
        )
        if precipitation is None:
            precipitation = clean_value(
                data.get("precipitation_amount_mean"), 
                parameter="precipitation_amount_mean"
            )
        return precipitation

    def _group_by_date(self) -> dict[Any, list[dict[str, Any]]]:
        """Group time series items by date.
        
        Returns:
            Dictionary mapping date to list of items
        """
        grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        
        for item in self.series:
            if not isinstance(item, dict):
                continue
            parsed = parse_time(item.get("time"))
            if parsed is None:
                continue
            date = dt_util.as_local(parsed).date()
            grouped[date].append(item)
        
        return grouped

    def _group_by_day_night(self) -> dict[tuple[Any, bool], list[dict[str, Any]]]:
        """Group time series items by date and day/night period.
        
        Returns:
            Dictionary mapping (date, is_daytime) tuple to list of items
        """
        grouped: dict[tuple[Any, bool], list[dict[str, Any]]] = defaultdict(list)
        
        for item in self.series:
            if not isinstance(item, dict):
                continue
            parsed = parse_time(item.get("time"))
            if parsed is None:
                continue
            
            local = dt_util.as_local(parsed)
            is_daytime = DAYTIME_START_HOUR <= local.hour < DAYTIME_END_HOUR
            key = (local.date(), is_daytime)
            grouped[key].append(item)
        
        return grouped
