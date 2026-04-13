"""Smart Climate — HACS custom integration for Home Assistant.

Platforms  : climate, sensor, number, select
Services   : set_boost, clear_boost, set_vacation, clear_vacation,
             set_schedule, clear_schedule
"""
from __future__ import annotations

from datetime import date
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_BOOST_DURATION,
    ATTR_BOOST_TARGET,
    ATTR_SCHEDULE_ENTRIES,
    ATTR_VACATION_END,
    ATTR_VACATION_START,
    ATTR_VACATION_TEMP,
    DEFAULT_BOOST_DURATION,
    DEFAULT_PRESET_AWAY,
    DEFAULT_PRESET_BOOST,
    DEFAULT_PUMP_ANTI_SEIZE_DURATION,
    DOMAIN,
    SERVICE_BOOST,
    SERVICE_CLEAR_BOOST,
    SERVICE_CLEAR_SCHEDULE,
    SERVICE_CLEAR_VACATION,
    SERVICE_SET_SCHEDULE,
    SERVICE_SET_VACATION,
    SERVICE_PUMP_EXERCISE,
)
from .schedule import validate_schedule_entries

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,   # pump controller
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Climate from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


# ---------------------------------------------------------------------------
# Service helpers
# ---------------------------------------------------------------------------

def _get_climate_entity(hass: HomeAssistant, call: ServiceCall):
    """Return the SmartClimate entity for the service call target."""
    entity_ids = call.data.get("entity_id", [])
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]

    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        entity = data.get("entity")
        if entity is None:
            continue
        if not entity_ids or entity.entity_id in entity_ids:
            return entity

    raise HomeAssistantError("No matching Smart Climate entity found for service call")


def _register_services(hass: HomeAssistant) -> None:
    """Register custom services (idempotent — safe to call multiple times)."""
    if hass.services.has_service(DOMAIN, SERVICE_BOOST):
        return

    # ---- set_boost -------------------------------------------------------
    hass.services.async_register(
        DOMAIN,
        SERVICE_BOOST,
        _handle_set_boost,
        schema=vol.Schema(
            {
                vol.Optional("entity_id"): cv.entity_ids,
                vol.Optional(ATTR_BOOST_DURATION): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=480)
                ),
                vol.Optional(ATTR_BOOST_TARGET): vol.All(
                    vol.Coerce(float), vol.Range(min=15, max=35)
                ),
            }
        ),
    )

    # ---- clear_boost -----------------------------------------------------
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_BOOST,
        _handle_clear_boost,
        schema=vol.Schema({vol.Optional("entity_id"): cv.entity_ids}),
    )

    # ---- set_vacation ----------------------------------------------------
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VACATION,
        _handle_set_vacation,
        schema=vol.Schema(
            {
                vol.Optional("entity_id"): cv.entity_ids,
                vol.Required(ATTR_VACATION_START): cv.date,
                vol.Required(ATTR_VACATION_END): cv.date,
                vol.Optional(ATTR_VACATION_TEMP, default=DEFAULT_PRESET_AWAY): vol.All(
                    vol.Coerce(float), vol.Range(min=5, max=18)
                ),
            }
        ),
    )

    # ---- clear_vacation --------------------------------------------------
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_VACATION,
        _handle_clear_vacation,
        schema=vol.Schema({vol.Optional("entity_id"): cv.entity_ids}),
    )

    # ---- set_schedule ----------------------------------------------------
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SCHEDULE,
        _handle_set_schedule,
        schema=vol.Schema(
            {
                vol.Optional("entity_id"): cv.entity_ids,
                vol.Required(ATTR_SCHEDULE_ENTRIES): list,
            }
        ),
    )

    # ---- clear_schedule --------------------------------------------------
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_SCHEDULE,
        _handle_clear_schedule,
        schema=vol.Schema({vol.Optional("entity_id"): cv.entity_ids}),
    )

    # ---- trigger_pump_exercise -------------------------------------------
    hass.services.async_register(
        DOMAIN,
        SERVICE_PUMP_EXERCISE,
        _handle_pump_exercise,
        schema=vol.Schema(
            {
                vol.Optional("entity_id"): cv.entity_ids,
                vol.Optional("duration"): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=120)
                ),
            }
        ),
    )


# ---------------------------------------------------------------------------
# Service handlers
# ---------------------------------------------------------------------------

async def _handle_set_boost(call: ServiceCall) -> None:
    hass = call.hass if hasattr(call, "hass") else _get_hass_from_call(call)
    entity = _get_climate_entity(hass, call)
    await entity.async_activate_boost(
        duration=call.data.get(ATTR_BOOST_DURATION),
        target=call.data.get(ATTR_BOOST_TARGET),
    )


async def _handle_clear_boost(call: ServiceCall) -> None:
    entity = _get_climate_entity(call.hass, call)
    await entity.async_clear_boost()


async def _handle_set_vacation(call: ServiceCall) -> None:
    entity = _get_climate_entity(call.hass, call)
    await entity.async_set_vacation(
        start_date=call.data[ATTR_VACATION_START],
        end_date=call.data[ATTR_VACATION_END],
        temperature=call.data.get(ATTR_VACATION_TEMP, DEFAULT_PRESET_AWAY),
    )


async def _handle_clear_vacation(call: ServiceCall) -> None:
    entity = _get_climate_entity(call.hass, call)
    await entity.async_clear_vacation()


async def _handle_set_schedule(call: ServiceCall) -> None:
    entity = _get_climate_entity(call.hass, call)
    entries = call.data[ATTR_SCHEDULE_ENTRIES]
    errors = validate_schedule_entries(entries)
    if errors:
        raise HomeAssistantError(f"Ongeldig schema: {'; '.join(errors)}")
    await entity.async_set_schedule(entries)


async def _handle_clear_schedule(call: ServiceCall) -> None:
    entity = _get_climate_entity(call.hass, call)
    await entity.async_clear_schedule()


async def _handle_pump_exercise(call: ServiceCall) -> None:
    """Trigger a pump exercise run."""
    hass = call.hass
    entity_ids = call.data.get("entity_id", [])
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]

    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        pump = data.get("pump")
        if pump is None:
            continue
        if not entity_ids or pump.entity_id in entity_ids:
            await pump.async_trigger_exercise(
                duration_min=call.data.get("duration")
            )
