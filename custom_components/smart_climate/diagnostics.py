"""Diagnostics support for Smart Climate."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

REDACT = {"token", "password"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    entity = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("entity")
    if entity is None:
        return {}

    return async_redact_data(
        {
            "config": dict(entry.data | entry.options),
            "state": {
                "hvac_mode": str(entity.hvac_mode),
                "hvac_action": str(entity.hvac_action),
                "current_temp": entity.current_temperature,
                "target_temp": entity.target_temperature,
                "preset": entity.preset_mode,
                "heater_on": entity._heater_on,
                "cooler_on": entity._cooler_on,
                "window_open": entity._window_open,
                "presence_detected": entity._presence_detected,
                "cascade_primary_heat_on": entity._cascade_primary_heat_on,
                "cascade_primary_cool_on": entity._cascade_primary_cool_on,
                "cascade_secondary_active": entity._cascade_secondary_active,
                "cascade_reason": entity._cascade_reason,
                "ramp_target": entity._ramp_target,
                "notify_sent": entity._notify_sent,
                "learned_heating_rate": (
                    entity._hist_heat._known_rate
                    if hasattr(entity._hist_heat, "_known_rate")
                    else entity._learned_heating_rate
                ),
                "pid_integral": (
                    entity._pid._integral
                    if hasattr(entity._pid, "_integral")
                    else None
                ),
                "weather_adj": entity._weather_adj,
                "algorithm": entity._algorithm,
            },
        },
        REDACT,
    )
