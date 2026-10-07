"""Test data shaped like the live snow1g response, and helpers to load the integration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "smhi"
BASE = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1"
LAT, LON = 57.721, 12.94
# Live step layout: 58 hourly steps, then 14 six-hour and 9 twelve-hour steps.
GAPS = [1] * 57 + [6] * 14 + [12] * 9

FIRST_STEP = {
    "air_temperature": 8.0, "wind_from_direction": 200, "wind_speed": 2.0, "wind_speed_of_gust": 6.0,
    "relative_humidity": 70, "air_pressure_at_mean_sea_level": 1003.3, "visibility_in_air": 23.0,
    "thunderstorm_probability": 0, "probability_of_frozen_precipitation": 0.0,
    "cloud_area_fraction": 4, "low_type_cloud_area_fraction": 4, "medium_type_cloud_area_fraction": 0,
    "high_type_cloud_area_fraction": 0, "cloud_base_altitude": 800, "cloud_top_altitude": 2500,
    "precipitation_amount_mean_deterministic": 0.0, "precipitation_amount_mean": 0.0,
    "precipitation_amount_min": 0.0, "precipitation_amount_max": 0.0, "precipitation_amount_median": 0.0,
    "probability_of_precipitation": 0, "precipitation_frozen_part": -9,
    "predominant_precipitation_type_at_surface": 0, "symbol_code": 3,
}


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def point_payload(first: dict | None = None, every: dict | None = None) -> dict:
    """Build a forecast. `first` overrides the current step, `every` overrides all steps."""
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    moments = [start]
    for gap in GAPS:
        moments.append(moments[-1] + timedelta(hours=gap))
    series = []
    for index, moment in enumerate(moments):
        data = dict(
            FIRST_STEP,
            air_temperature=round(8.0 - (index % 10) * 0.6, 1),
            wind_from_direction=(200 + index * 7) % 360,
            relative_humidity=70 + (index % 30),
            cloud_area_fraction=index % 9,
            precipitation_amount_mean=round(0.2 * (index % 4), 1),
            precipitation_amount_mean_deterministic=round(0.2 * (index % 4), 1),
            probability_of_precipitation=min(100, (index * 10) % 110),
            symbol_code=1 + (index % 27),
        )
        data.update(every or {})
        if index == 0:
            data.update(first or {})
        previous = moments[index - 1] if index else moment - timedelta(hours=1)
        series.append({"time": stamp(moment), "intervalParametersStartTime": stamp(previous), "data": data})
    return {
        "createdTime": stamp(start - timedelta(minutes=75)),
        "referenceTime": stamp(start - timedelta(minutes=90)),
        "geometry": {"type": "Point", "coordinates": [12.94439, 57.714622]},
        "timeSeries": series,
    }


def point_url(lat: float = LAT, lon: float = LON) -> str:
    return f"{BASE}/geotype/point/lon/{lon:.6f}/lat/{lat:.6f}/data.json"


def mock_point(aioclient_mock, lat: float = LAT, lon: float = LON, payload: dict | None = None) -> dict:
    payload = payload or point_payload()
    aioclient_mock.get(point_url(lat, lon), json=payload)
    return payload


async def setup_integration(hass, aioclient_mock, *, options: dict | None = None,
                            payload: dict | None = None) -> MockConfigEntry:
    """Create a config entry for the default location and set it up."""
    mock_point(aioclient_mock, payload=payload)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SMHI",
        unique_id=f"{DOMAIN}_{LAT:.6f}_{LON:.6f}",
        data={"name": "SMHI", "use_home_location": False, "latitude": LAT, "longitude": LON},
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
