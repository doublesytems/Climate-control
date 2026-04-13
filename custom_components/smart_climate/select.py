"""Smart Climate — select platform.

Exposes the control algorithm as a selectable entity so it can be
switched from the HA dashboard or automations at runtime.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ALGORITHMS,
    DOMAIN,
    SUFFIX_ALGORITHM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate select entity."""
    climate_entity = hass.data[DOMAIN][config_entry.entry_id].get("entity")
    if climate_entity is None:
        return

    async_add_entities(
        [
            AlgorithmSelect(
                climate_entity=climate_entity,
                unique_id=config_entry.entry_id + SUFFIX_ALGORITHM,
                name=f"{config_entry.title} algoritme",
            )
        ]
    )


class AlgorithmSelect(SelectEntity):
    """Select entity for switching the control algorithm at runtime."""

    _attr_should_poll = False
    _attr_icon = "mdi:sine-wave"

    def __init__(self, climate_entity, unique_id: str, name: str) -> None:
        self._climate = climate_entity
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_options = list(ALGORITHMS)

    @property
    def current_option(self) -> str:
        return self._climate.algorithm

    async def async_select_option(self, option: str) -> None:
        if option not in ALGORITHMS:
            return
        self._climate.algorithm = option
        self.async_write_ha_state()
