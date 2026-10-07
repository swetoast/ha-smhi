"""The three SMHI fields that do not share one scale (verified against the live API).

thunderstorm_probability is percent, probability_of_frozen_precipitation is a 0-1
fraction, precipitation_frozen_part is percent with -9 for "no precipitation".
"""
from .common import point_payload, setup_integration

SLEET = {
    "air_temperature": 0.5, "relative_humidity": 95, "wind_speed": 2.0, "visibility_in_air": 5.0,
    "thunderstorm_probability": 1, "probability_of_frozen_precipitation": 0.53,
    "precipitation_frozen_part": 30, "precipitation_amount_mean": 0.6,
    "precipitation_amount_mean_deterministic": 0.6, "precipitation_amount_max": 1.2,
}


async def test_one_percent_thunder_is_one_percent(hass, aioclient_mock):
    await setup_integration(hass, aioclient_mock, payload=point_payload(first=SLEET))

    assert float(hass.states.get("sensor.smhi_thunderstorm_probability").state) == 1
    assert hass.states.get("sensor.smhi_impact_severity").attributes["current_thunderstorm_probability"] == 1


async def test_high_thunder_probability_raises_the_impact_score(hass, aioclient_mock):
    calm = point_payload(first=dict(SLEET, thunderstorm_probability=1))
    stormy = point_payload(first=dict(SLEET, thunderstorm_probability=80))
    await setup_integration(hass, aioclient_mock, payload=calm)
    calm_score = float(hass.states.get("sensor.smhi_impact_severity").state)

    entry = hass.config_entries.async_entries("smhi")[0]
    aioclient_mock.clear_requests()
    from .common import mock_point
    mock_point(aioclient_mock, payload=stormy)
    await hass.data["smhi"][entry.entry_id].async_refresh()
    await hass.async_block_till_done()

    assert float(hass.states.get("sensor.smhi_impact_severity").state) == calm_score + 15


async def test_frozen_fields_use_their_own_scales(hass, aioclient_mock):
    await setup_integration(hass, aioclient_mock, payload=point_payload(first=SLEET))

    attributes = hass.states.get("sensor.smhi_precipitation").attributes
    assert attributes["probability_of_frozen_precipitation"] == 53.0
    assert attributes["precipitation_frozen_part"] == 30
    # 0.5 C: 50 for temperature, 10 for a 30 % frozen share, 10 for 0.6 mm.
    assert float(hass.states.get("sensor.smhi_slippery_risk").state) == 70
    # A 30 % frozen share is mostly rain, so it needs a shell rather than snow handling.
    assert hass.states.get("sensor.smhi_practical_clothing").attributes["rain_protection"] == "light_shell"


async def test_no_precipitation_sentinel_is_not_a_value(hass, aioclient_mock):
    await setup_integration(hass, aioclient_mock, payload=point_payload(first=dict(SLEET, precipitation_frozen_part=-9)))

    assert hass.states.get("sensor.smhi_precipitation").attributes["precipitation_frozen_part"] is None
