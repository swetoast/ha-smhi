"""Setup, entities, recorder limits and option changes."""
from homeassistant.components.recorder.db_schema import MAX_STATE_ATTRS_BYTES, StateAttributes
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import DOMAIN, point_url, setup_integration


async def test_setup_uses_one_request_and_creates_every_entity(hass, aioclient_mock):
    entry = await setup_integration(hass, aioclient_mock)

    assert entry.state is ConfigEntryState.LOADED
    assert aioclient_mock.call_count == 1

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == 25
    states = {item.entity_id: hass.states.get(item.entity_id) for item in entities}
    assert all(state and state.state not in ("unavailable", "unknown") for state in states.values())

    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.manufacturer == "SMHI"


async def test_no_entity_exceeds_the_recorder_attribute_limit(hass, aioclient_mock):
    entry = await setup_integration(hass, aioclient_mock, options={"forecast_timeseries": 200})

    for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        state = hass.states.get(item.entity_id)
        event = Event(EVENT_STATE_CHANGED, {"entity_id": item.entity_id, "old_state": None, "new_state": state})
        recorded = StateAttributes.shared_attrs_bytes_from_event(event, None)
        assert len(recorded) <= MAX_STATE_ATTRS_BYTES, item.entity_id
        assert recorded != b"{}", item.entity_id

    weather = hass.states.get("weather.smhi")
    assert len(weather.attributes["raw_forecast"]) == 81  # still there for dashboards


async def test_metadata_comes_from_the_forecast_response(hass, aioclient_mock):
    await setup_integration(hass, aioclient_mock)

    metadata = hass.states.get("sensor.smhi_metadata")
    assert metadata.state.endswith("Z")
    assert metadata.attributes["available_times_count"] == 81
    assert metadata.attributes["grid_point"] == {"lon": 12.94439, "lat": 57.714622}
    assert metadata.attributes["approved_time"] == metadata.attributes["created_time"]


async def test_forecast_step_option_caps_the_series(hass, aioclient_mock):
    await setup_integration(hass, aioclient_mock, options={"forecast_timeseries": 24})

    assert len(hass.states.get("weather.smhi").attributes["raw_forecast"]) == 24
    assert hass.states.get("sensor.smhi_metadata").attributes["available_times_count"] == 81


async def test_disabling_a_group_removes_its_entities(hass, aioclient_mock):
    entry = await setup_integration(hass, aioclient_mock)
    registry = er.async_get(hass)
    assert registry.async_get("sensor.smhi_frost_risk")
    assert registry.async_get("binary_sensor.smhi_frost_possible")

    hass.config_entries.async_update_entry(entry, options={"enable_frost_sensors": False})
    await hass.async_block_till_done()

    assert registry.async_get("sensor.smhi_frost_risk") is None
    assert registry.async_get("binary_sensor.smhi_frost_possible") is None
    assert registry.async_get("sensor.smhi_slippery_risk")


async def test_failed_update_keeps_last_data_and_raises_the_problem_sensor(hass, aioclient_mock):
    entry = await setup_integration(hass, aioclient_mock)
    assert hass.states.get("binary_sensor.smhi_api_problem").state == "off"

    aioclient_mock.clear_requests()
    aioclient_mock.get(point_url(), status=503)
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.smhi_api_problem").state == "on"
    assert hass.states.get("weather.smhi").state not in ("unavailable", "unknown")


async def test_unload_cleans_up(hass, aioclient_mock):
    entry = await setup_integration(hass, aioclient_mock)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data[DOMAIN]
