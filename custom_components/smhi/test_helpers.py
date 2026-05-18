from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util


def generate_mock_time_series(
    start_time: datetime | None = None,
    hours: int = 48,
    interval_hours: int = 1,
) -> list[dict[str, Any]]:
    """Generate mock time series data for testing.
    
    Args:
        start_time: Start time for the series (defaults to now)
        hours: Number of hours to generate
        interval_hours: Interval between data points in hours
        
    Returns:
        List of mock time series items
    """
    if start_time is None:
        start_time = dt_util.utcnow()
    
    series = []
    for i in range(0, hours, interval_hours):
        time = start_time + timedelta(hours=i)
        series.append({
            "time": time.isoformat(),
            "data": generate_mock_data_point(i),
        })
    
    return series


def generate_mock_data_point(hour_offset: int = 0) -> dict[str, Any]:
    """Generate a mock data point with realistic values.
    
    Args:
        hour_offset: Hour offset for variation in values
        
    Returns:
        Dictionary with mock weather data
    """
    # Create some variation based on hour offset
    temp_variation = (hour_offset % 24 - 12) * 0.5
    
    return {
        "air_temperature": 15.0 + temp_variation,
        "wind_from_direction": 180 + (hour_offset % 8) * 45,
        "wind_speed": 5.0 + (hour_offset % 5),
        "wind_speed_of_gust": 8.0 + (hour_offset % 5),
        "relative_humidity": 70 + (hour_offset % 20),
        "air_pressure_at_mean_sea_level": 1013.0 + (hour_offset % 10) - 5,
        "visibility_in_air": 10.0 + (hour_offset % 30),
        "thunderstorm_probability": min(0.1 * (hour_offset % 10), 1.0),
        "probability_of_frozen_precipitation": 0.0,
        "cloud_area_fraction": min(hour_offset % 9, 8),
        "low_type_cloud_area_fraction": min((hour_offset % 9) - 2, 8),
        "medium_type_cloud_area_fraction": min((hour_offset % 9) - 4, 8),
        "high_type_cloud_area_fraction": min((hour_offset % 9) - 6, 8),
        "cloud_base_altitude": 1000.0,
        "cloud_top_altitude": 3000.0,
        "precipitation_amount_mean_deterministic": 0.1 * (hour_offset % 5),
        "precipitation_amount_mean": 0.1 * (hour_offset % 5),
        "precipitation_amount_min": 0.0,
        "precipitation_amount_max": 0.2 * (hour_offset % 5),
        "precipitation_amount_median": 0.1 * (hour_offset % 5),
        "probability_of_precipitation": min(10 * (hour_offset % 10), 100),
        "precipitation_frozen_part": 0.0,
        "predominant_precipitation_type_at_surface": 0,
        "symbol_code": 1 + (hour_offset % 27),
    }


def generate_mock_payload(
    latitude: float = 59.3293,
    longitude: float = 18.0686,
    hours: int = 48,
) -> dict[str, Any]:
    """Generate a complete mock API payload.
    
    Args:
        latitude: Latitude for grid point
        longitude: Longitude for grid point
        hours: Number of hours to generate
        
    Returns:
        Complete mock payload dictionary
    """
    now = dt_util.utcnow()
    
    return {
        "approvedTime": (now - timedelta(hours=1)).isoformat(),
        "referenceTime": now.isoformat(),
        "createdTime": (now - timedelta(hours=1)).isoformat(),
        "geometry": {
            "type": "Point",
            "coordinates": [longitude, latitude],
        },
        "timeSeries": generate_mock_time_series(now, hours),
    }


def generate_mock_parameters() -> list[dict[str, Any]]:
    """Generate mock parameter metadata.
    
    Returns:
        List of parameter definitions
    """
    return [
        {
            "name": "air_temperature",
            "shortName": "2t",
            "description": "Air temperature at 2 metres height.",
            "levelType": "hl",
            "level": 2,
            "unit": "Cel",
            "missingValue": 9999,
        },
        {
            "name": "wind_speed",
            "shortName": "ws",
            "description": "Wind speed at 10 metre.",
            "levelType": "hl",
            "level": 10,
            "unit": "m/s",
            "missingValue": 9999,
        },
        {
            "name": "precipitation_amount_mean",
            "shortName": "tpratemean",
            "description": "Mean total precipitation amount",
            "levelType": "hl",
            "level": 0,
            "unit": "kg/m2",
            "missingValue": 9999,
        },
    ]


def generate_error_scenarios() -> dict[str, dict[str, Any]]:
    """Generate various error scenarios for testing.
    
    Returns:
        Dictionary of error scenario names to payloads
    """
    return {
        "empty_payload": {},
        "missing_timeseries": {
            "approvedTime": dt_util.utcnow().isoformat(),
            "geometry": {"coordinates": [18.0, 59.3]},
        },
        "empty_timeseries": {
            "timeSeries": [],
            "geometry": {"coordinates": [18.0, 59.3]},
        },
        "invalid_timeseries": {
            "timeSeries": "not a list",
        },
        "malformed_item": {
            "timeSeries": [
                {"invalid": "data"},
                {"time": "not-a-datetime"},
            ],
        },
        "missing_values": {
            "timeSeries": [
                {
                    "time": dt_util.utcnow().isoformat(),
                    "data": {
                        "air_temperature": 9999,  # MISSING_VALUE
                        "wind_speed": 9999,
                    },
                }
            ],
        },
    }


def generate_edge_cases() -> dict[str, dict[str, Any]]:
    """Generate edge case scenarios for testing.
    
    Returns:
        Dictionary of edge case names to payloads
    """
    now = dt_util.utcnow()
    
    return {
        "polar_winter": {
            "timeSeries": [
                {
                    "time": now.isoformat(),
                    "data": {
                        "air_temperature": -40.0,
                        "wind_speed": 20.0,
                        "symbol_code": 15,  # Snow
                    },
                }
            ],
        },
        "extreme_heat": {
            "timeSeries": [
                {
                    "time": now.isoformat(),
                    "data": {
                        "air_temperature": 40.0,
                        "relative_humidity": 80,
                        "symbol_code": 1,  # Sunny
                    },
                }
            ],
        },
        "zero_visibility": {
            "timeSeries": [
                {
                    "time": now.isoformat(),
                    "data": {
                        "visibility_in_air": 0.0,
                        "symbol_code": 7,  # Fog
                    },
                }
            ],
        },
        "all_clouds": {
            "timeSeries": [
                {
                    "time": now.isoformat(),
                    "data": {
                        "cloud_area_fraction": 8,  # 8 octas = 100%
                        "symbol_code": 6,  # Overcast
                    },
                }
            ],
        },
    }


class MockCoordinator:
    """Mock coordinator for testing."""
    
    def __init__(
        self,
        data: dict[str, Any] | None = None,
        last_update_success: bool = True,
    ) -> None:
        """Initialize mock coordinator.
        
        Args:
            data: Mock data to return
            last_update_success: Whether last update was successful
        """
        self.data = data or generate_mock_payload()
        self.last_update_success = last_update_success
        self.last_good_data = self.data if last_update_success else None
        self.last_success = dt_util.utcnow().isoformat() if last_update_success else None
        self.last_error = None if last_update_success else "Mock error"
        self.entry = MockConfigEntry()
        self.times = ["2024-01-01T00:00:00Z"]
        self.approved_time = dt_util.utcnow().isoformat()
        self.approved_reference_time = dt_util.utcnow().isoformat()
        self.update_interval = timedelta(minutes=30)
    
    def current_payload(self) -> dict[str, Any]:
        """Return current payload."""
        return self.data or self.last_good_data or {}


class MockConfigEntry:
    """Mock config entry for testing."""
    
    def __init__(self) -> None:
        """Initialize mock config entry."""
        self.entry_id = "test_entry_id"
        self.data = {
            "name": "Test SMHI",
            "latitude": 59.3293,
            "longitude": 18.0686,
        }
        self.options = {
            "forecast_timeseries": 70,
            "scan_interval": 30,
        }
