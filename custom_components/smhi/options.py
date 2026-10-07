"""Options flow for the SMHI integration.

Presents the adjustable settings in two collapsible sections - update behaviour
and which optional sensor groups are enabled - so the form stays readable. The
values are stored as flat option keys (unchanged from earlier versions), so the
coordinator and platforms keep reading them the same way.
"""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from .const import (
    CONF_ENABLE_COMFORT_SENSORS,
    CONF_ENABLE_FROST_SENSORS,
    CONF_ENABLE_IMPACT_SENSOR,
    CONF_ENABLE_PRACTICAL_SENSORS,
    CONF_ENABLE_SLIPPERY_SENSORS,
    CONF_ENABLE_THERMAL_SENSORS,
    CONF_FORECAST_TIMESERIES,
    CONF_SCAN_INTERVAL,
    DEFAULT_FORECAST_TIMESERIES,
    DEFAULT_SCAN_INTERVAL_MIN,
)

# Section keys (used both in the schema and in translations/*.json)
SECTION_UPDATES = "updates"
SECTION_SENSORS = "sensors"

# Which flat option keys live in which section, so saving can flatten reliably
_SECTION_KEYS = {
    SECTION_UPDATES: (CONF_FORECAST_TIMESERIES, CONF_SCAN_INTERVAL),
    SECTION_SENSORS: (
        CONF_ENABLE_COMFORT_SENSORS,
        CONF_ENABLE_FROST_SENSORS,
        CONF_ENABLE_SLIPPERY_SENSORS,
        CONF_ENABLE_IMPACT_SENSOR,
        CONF_ENABLE_PRACTICAL_SENSORS,
        CONF_ENABLE_THERMAL_SENSORS,
    ),
}


class SmhiOptionsFlow(config_entries.OptionsFlow):
    """Handle SMHI options."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            # Sections arrive nested; flatten to the flat option keys we store.
            flat: dict[str, Any] = {}
            for section_key in (SECTION_UPDATES, SECTION_SENSORS):
                flat.update(user_input.get(section_key, {}))
            # Sliders return floats; both settings are whole numbers.
            for key in (CONF_FORECAST_TIMESERIES, CONF_SCAN_INTERVAL):
                if key in flat:
                    flat[key] = int(flat[key])
            return self.async_create_entry(title="", data=flat)

        opts = self.entry.options

        updates_schema = vol.Schema(
            {
                vol.Required(
                    CONF_FORECAST_TIMESERIES,
                    default=opts.get(CONF_FORECAST_TIMESERIES, DEFAULT_FORECAST_TIMESERIES),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=200, step=1, mode=selector.NumberSelectorMode.SLIDER
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=180,
                        step=5,
                        unit_of_measurement="min",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
            }
        )

        sensors_schema = vol.Schema(
            {
                vol.Required(
                    CONF_ENABLE_COMFORT_SENSORS,
                    default=opts.get(CONF_ENABLE_COMFORT_SENSORS, True),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_FROST_SENSORS,
                    default=opts.get(CONF_ENABLE_FROST_SENSORS, True),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_SLIPPERY_SENSORS,
                    default=opts.get(CONF_ENABLE_SLIPPERY_SENSORS, True),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_IMPACT_SENSOR,
                    default=opts.get(CONF_ENABLE_IMPACT_SENSOR, True),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_PRACTICAL_SENSORS,
                    default=opts.get(CONF_ENABLE_PRACTICAL_SENSORS, True),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_ENABLE_THERMAL_SENSORS,
                    default=opts.get(CONF_ENABLE_THERMAL_SENSORS, True),
                ): selector.BooleanSelector(),
            }
        )

        schema = vol.Schema(
            {
                vol.Required(SECTION_UPDATES): section(updates_schema, {"collapsed": False}),
                vol.Required(SECTION_SENSORS): section(sensors_schema, {"collapsed": True}),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
