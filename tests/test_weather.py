"""Weather entity forecasts."""
from homeassistant.components.weather import DATA_COMPONENT

from custom_components.smhi.helpers import mean_bearing

from .common import DOMAIN, setup_integration


async def get_forecast(hass, kind):
    response = await hass.services.async_call(
        "weather", "get_forecasts", {"entity_id": "weather.smhi", "type": kind},
        blocking=True, return_response=True)
    return response["weather.smhi"]["forecast"]


async def test_all_three_forecast_types(hass, aioclient_mock):
    await setup_integration(hass, aioclient_mock, options={"forecast_timeseries": 200})

    hourly = await get_forecast(hass, "hourly")
    twice_daily = await get_forecast(hass, "twice_daily")
    daily = await get_forecast(hass, "daily")

    assert len(hourly) == 81
    for rows in (hourly, twice_daily, daily):
        stamps = [row["datetime"] for row in rows]
        assert stamps == sorted(stamps) and len(set(stamps)) == len(stamps)

    periods = [row["is_daytime"] for row in twice_daily]
    assert all(a != b for a, b in zip(periods, periods[1:]))  # day and night alternate

    assert 10 <= len(daily) <= 12  # about ten days of forecast
    for row in daily:
        assert row["templow"] <= row["temperature"]
        assert isinstance(row["cloud_coverage"], int)
        assert isinstance(row["humidity"], int)
        assert row["precipitation"] == round(row["precipitation"], 1)
        assert 0 <= row["wind_bearing"] < 360


async def test_forecast_subscribers_get_every_update(hass, aioclient_mock):
    entry = await setup_integration(hass, aioclient_mock)
    entity = hass.data[DATA_COMPONENT].get_entity("weather.smhi")
    received = []
    unsubscribe = entity.async_subscribe_forecast("daily", lambda forecast: received.append(forecast))

    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await hass.async_block_till_done()
    unsubscribe()

    assert len(received) == 1 and received[0]


def test_mean_bearing_wraps_around_north():
    assert mean_bearing([350, 10]) == 0.0
    assert mean_bearing([90, 90, 9999]) == 90.0  # 9999 is SMHI's missing value
    assert mean_bearing([0, 180]) is None  # opposite winds have no mean direction
    assert mean_bearing([]) is None
