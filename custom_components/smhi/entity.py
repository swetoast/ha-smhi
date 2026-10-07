"""Pieces shared by every SMHI entity platform."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import CONF_NAME, DEFAULT_NAME, DOMAIN


def smhi_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Device shown for one configured SMHI location."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        manufacturer="SMHI",
        model="Open Data forecast",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://opendata.smhi.se/metfcst/snow1gv1/",
    )


@callback
def async_remove_stale_entities(
    hass: HomeAssistant, entry: ConfigEntry, platform: str, unique_ids: set[str]
) -> None:
    """Drop registry entries of this platform that the entry no longer provides.

    Turning a sensor group off in the options stops creating its entities. Without
    this they would stay in the entity registry as permanently unavailable.
    """
    registry = er.async_get(hass)
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        if item.domain == platform and item.unique_id not in unique_ids:
            registry.async_remove(item.entity_id)
