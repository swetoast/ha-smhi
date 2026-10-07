"""Calculation checks: published reference values, continuity, and the alert logic."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from custom_components.smhi import sensor
from custom_components.smhi.helpers import sun_is_up

from .common import LAT, LON, point_payload, setup_integration


@pytest.mark.parametrize(
    ("value", "reference", "tolerance"),
    [
        (sensor.calculate_wind_chill(-10, 20), -17.9, 0.1),      # Environment Canada table
        (sensor.calculate_wind_chill(-20, 40), -34.1, 0.1),
        (sensor.calculate_heat_index(32.2, 70), 41.0, 0.2),      # NWS regression, 90 F / 70 % = 105.9 F
        (sensor.calculate_dew_point(20, 50), 9.3, 0.1),          # psychrometric tables
        (sensor.calculate_dew_point(0, 90), -1.4, 0.1),
        (sensor.calculate_humidex(30, 40.2), 34.0, 0.2),         # Environment Canada, dew point 15 C
        (sensor.calculate_absolute_humidity(20, 50), 8.65, 0.05),  # g/m3
        (sensor.calculate_moist_air_enthalpy(25, 50), 50.3, 0.2),  # kJ/kg, ASHRAE
    ],
)
def test_standard_formulas_match_published_values(value, reference, tolerance):
    assert value == pytest.approx(reference, abs=tolerance)


@pytest.mark.parametrize("humidity", [30, 55, 70, 80, 95])
def test_heat_stress_never_falls_as_it_gets_warmer(humidity):
    values = [sensor.calculate_heat_stress(tenth / 10, humidity) for tenth in range(150, 401)]
    assert values == sorted(values)
    assert values[0] == 0 and values[-1] == 100


def test_heat_stress_anchor_points():
    assert [sensor.calculate_heat_stress(t, 40) for t in (18, 20, 22, 25, 28, 32, 35)] == [0, 5, 15, 30, 50, 80, 100]


def change_alert(temps, winds=None, rain=None):
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    series = [
        {"time": (start + timedelta(hours=i + 1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "data": {"air_temperature": temp, "wind_speed": (winds or [3] * len(temps))[i],
                  "probability_of_precipitation": (rain or [0] * len(temps))[i]}}
        for i, temp in enumerate(temps)
    ]
    coordinator = SimpleNamespace(entry=SimpleNamespace(entry_id="x"), current_payload=lambda: {"timeSeries": series})
    return sensor.SmhiWeatherChangeAlertSensor(coordinator).native_value


def test_weather_change_alert_scores_each_change_once():
    level = sensor.WeatherChangeLevel
    assert change_alert([10] * 7) == level.STABLE
    # An ordinary morning warming 7 degrees, or one 5 degree step that then holds.
    assert change_alert([6, 7, 9, 11, 12, 13, 13]) == level.MINOR
    assert change_alert([10, 10, 5, 5, 5, 5, 5]) == level.MINOR
    # A cold front: 10 degrees colder, 10 m/s more wind and rain arriving.
    assert change_alert([15, 14, 10, 6, 5, 5, 5], [3, 5, 9, 13, 13, 13, 13], [0, 20, 80, 90, 90, 90, 90]) == level.SEVERE
    assert change_alert([15, 14, 10, 6, 5, 5, 5]) == level.MODERATE


def test_sun_is_up_for_the_entry_location():
    assert sun_is_up(LAT, LON, datetime(2026, 10, 7, 11, 0, tzinfo=timezone.utc))
    assert not sun_is_up(LAT, LON, datetime(2026, 10, 7, 23, 0, tzinfo=timezone.utc))
    # Midnight sun in Kiruna, polar night in December.
    assert sun_is_up(67.86, 20.23, datetime(2026, 6, 21, 22, 0, tzinfo=timezone.utc))
    assert not sun_is_up(67.86, 20.23, datetime(2026, 12, 21, 11, 0, tzinfo=timezone.utc))


async def test_clear_sky_is_clear_night_after_sunset(hass, aioclient_mock):
    await setup_integration(hass, aioclient_mock, payload=point_payload(every={"symbol_code": 1}),
                            options={"forecast_timeseries": 200})

    expected_now = "sunny" if sun_is_up(LAT, LON, datetime.now(timezone.utc)) else "clear-night"
    assert hass.states.get("weather.smhi").state == expected_now
    assert hass.states.get("sensor.smhi_symbol_code").attributes["home_assistant_condition"] == expected_now

    async def forecast(kind):
        response = await hass.services.async_call(
            "weather", "get_forecasts", {"entity_id": "weather.smhi", "type": kind},
            blocking=True, return_response=True)
        return response["weather.smhi"]["forecast"]

    hourly = await forecast("hourly")
    for row in hourly:
        moment = datetime.fromisoformat(row["datetime"])
        assert row["condition"] == ("sunny" if sun_is_up(LAT, LON, moment) else "clear-night")
    assert {row["condition"] for row in hourly} == {"sunny", "clear-night"}

    for row in await forecast("twice_daily"):
        assert row["condition"] == ("sunny" if row["is_daytime"] else "clear-night")
    assert {row["condition"] for row in await forecast("daily")} == {"sunny"}
