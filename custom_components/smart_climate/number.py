"""Smart Climate — number platform.

Exposes PID parameters (Kp / Ki / Kd) as adjustable number entities
so they can be tuned from the HA dashboard without restarting.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SUFFIX_PID_KD,
    SUFFIX_PID_KI,
    SUFFIX_PID_KP,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PID number entities."""
    climate_entity = hass.data[DOMAIN][config_entry.entry_id].get("entity")
    if climate_entity is None:
        return

    async_add_entities(
        [
            PIDParameterNumber(
                climate_entity=climate_entity,
                unique_id=config_entry.entry_id + SUFFIX_PID_KP,
                name=f"{config_entry.title} PID Kp",
                param="kp",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
            ),
            PIDParameterNumber(
                climate_entity=climate_entity,
                unique_id=config_entry.entry_id + SUFFIX_PID_KI,
                name=f"{config_entry.title} PID Ki",
                param="ki",
                min_value=0.0,
                max_value=10.0,
                step=0.01,
            ),
            PIDParameterNumber(
                climate_entity=climate_entity,
                unique_id=config_entry.entry_id + SUFFIX_PID_KD,
                name=f"{config_entry.title} PID Kd",
                param="kd",
                min_value=0.0,
                max_value=100.0,
                step=0.1,
            ),
        ]
    )


class PIDParameterNumber(NumberEntity):
    """Adjustable PID coefficient."""

    _attr_should_poll = False
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:tune"

    def __init__(
        self,
        climate_entity,
        unique_id: str,
        name: str,
        param: str,
        min_value: float,
        max_value: float,
        step: float,
    ) -> None:
        self._climate = climate_entity
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._param = param  # "kp", "ki", or "kd"
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step

    @property
    def native_value(self) -> float:
        return getattr(self._climate, f"pid_{self._param}")

    async def async_set_native_value(self, value: float) -> None:
        setattr(self._climate, f"pid_{self._param}", value)
        self.async_write_ha_state()
