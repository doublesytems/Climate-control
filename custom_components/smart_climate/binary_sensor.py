"""Smart Climate — binary sensor platform.

Exposes:
* Prijssetback actief (aan/uit) — True wanneer energie duur is en setback actief
"""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SUFFIX_PRICE_SETBACK


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate binary sensors."""
    climate_entity = hass.data[DOMAIN][config_entry.entry_id].get("entity")
    if climate_entity is None:
        return

    async_add_entities([
        SmartClimatePriceSetbackSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_PRICE_SETBACK,
            name=f"{config_entry.title} prijssetback actief",
        )
    ])


class SmartClimatePriceSetbackSensor(BinarySensorEntity):
    """True when energy price setback is active."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:currency-eur-off"

    def __init__(self, climate_entity, unique_id: str, name: str) -> None:
        self._climate = climate_entity
        self._attr_unique_id = unique_id
        self._attr_name = name

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_update, timedelta(seconds=30)
            )
        )

    @callback
    def _async_update(self, _now=None) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return bool(getattr(self._climate, "_price_setback_active", False))
