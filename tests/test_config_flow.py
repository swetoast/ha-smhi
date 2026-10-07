"""Setup, reconfigure and options flows."""
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from .common import DOMAIN, LAT, LON, mock_point, point_url, setup_integration

STOCKHOLM = {"name": "Stockholm", "use_home_location": False, "latitude": 59.3293, "longitude": 18.0686}


async def test_user_flow_creates_an_entry(hass, aioclient_mock):
    hass.config.latitude, hass.config.longitude = LAT, LON
    mock_point(aioclient_mock)
    flow = hass.config_entries.flow

    result = await flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    result = await flow.async_configure(result["flow_id"], {"name": "Home", "use_home_location": True})
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["grid_point"] == "57.714622, 12.944390"
    result = await flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "sensors"
    result = await flow.async_configure(result["flow_id"], {"enable_thermal_sensors": False})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == {"name": "Home", "use_home_location": True, "latitude": LAT, "longitude": LON}
    assert result["options"]["enable_thermal_sensors"] is False
    assert result["options"]["forecast_timeseries"] == 70
    assert result["result"].unique_id == f"{DOMAIN}_{LAT:.6f}_{LON:.6f}"


async def test_user_flow_reports_out_of_grid_and_connection_errors(hass, aioclient_mock):
    flow = hass.config_entries.flow
    aioclient_mock.get(point_url(5.0, 40.0), status=404, text="Requested point is out of bounds")
    aioclient_mock.get(point_url(60.0, 10.0), exc=TimeoutError())
    aioclient_mock.get(point_url(61.0, 11.0), status=500)

    result = await flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    for lat, lon, error in ((5.0, 40.0, "out_of_bounds"), (60.0, 10.0, "cannot_connect"), (61.0, 11.0, "cannot_connect")):
        result = await flow.async_configure(
            result["flow_id"], {"name": "X", "use_home_location": False, "latitude": lat, "longitude": lon})
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}


async def test_user_flow_aborts_for_a_configured_location(hass, aioclient_mock):
    await setup_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Again", "use_home_location": False, "latitude": LAT, "longitude": LON})

    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"


async def test_reconfigure_moves_the_entry_and_reloads_once(hass, aioclient_mock):
    entry = await setup_integration(hass, aioclient_mock)
    mock_point(aioclient_mock, lat=STOCKHOLM["latitude"], lon=STOCKHOLM["longitude"])
    real_reload = hass.config_entries.async_reload
    reloads = []

    async def counting_reload(entry_id):
        reloads.append(entry_id)
        return await real_reload(entry_id)

    with patch.object(hass.config_entries, "async_reload", side_effect=counting_reload):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
        assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], STOCKHOLM)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert reloads == [entry.entry_id]
    assert entry.title == "Stockholm"
    assert entry.unique_id == f"{DOMAIN}_59.329300_18.068600"
    assert (entry.data["latitude"], entry.data["longitude"]) == (59.3293, 18.0686)


async def test_reconfigure_refuses_a_location_another_entry_uses(hass, aioclient_mock):
    first = await setup_integration(hass, aioclient_mock)
    mock_point(aioclient_mock, lat=STOCKHOLM["latitude"], lon=STOCKHOLM["longitude"])
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], STOCKHOLM)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    second = result["result"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_RECONFIGURE, "entry_id": second.entry_id})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Dup", "use_home_location": False, "latitude": LAT, "longitude": LON})

    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
    assert second.unique_id == f"{DOMAIN}_59.329300_18.068600"
    assert first.unique_id == f"{DOMAIN}_{LAT:.6f}_{LON:.6f}"


async def test_options_flow_stores_flat_whole_numbers(hass, aioclient_mock):
    entry = await setup_integration(hass, aioclient_mock)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        "updates": {"forecast_timeseries": 100.0, "scan_interval": 15.0},
        "sensors": {"enable_comfort_sensors": True, "enable_frost_sensors": False,
                    "enable_slippery_sensors": True, "enable_impact_sensor": True,
                    "enable_practical_sensors": True, "enable_thermal_sensors": True},
    })
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["forecast_timeseries"] == 100 and isinstance(entry.options["forecast_timeseries"], int)
    assert entry.options["scan_interval"] == 15 and isinstance(entry.options["scan_interval"], int)
    assert entry.options["enable_frost_sensors"] is False
    assert "updates" not in entry.options and "sensors" not in entry.options
    assert hass.data[DOMAIN][entry.entry_id].update_interval.total_seconds() == 15 * 60
