"""Shared fixtures for the SMHI tests."""
import pytest

# Import the package under test first, so Home Assistant's loader resolves
# "custom_components" to this repository and not to the test plugin's own folder.
import custom_components  # noqa: F401


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load integrations from custom_components."""
    yield


@pytest.fixture(autouse=True)
async def swedish_time_zone(hass):
    """Run every test in the time zone the integration is written for."""
    await hass.config.async_set_time_zone("Europe/Stockholm")
