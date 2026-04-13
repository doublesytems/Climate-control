"""Smart Climate — sensor platform.

Exposes:
* Heater runtime today (h)
* Cooler runtime today (h)
* Heater energy today (kWh)   — requires heater_watt > 0
* Cooler energy today (kWh)   — requires cooler_watt > 0
"""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import (
    DOMAIN,
    SUFFIX_COOLER_ENERGY,
    SUFFIX_COOLER_RUNTIME,
    SUFFIX_HEATER_ENERGY,
    SUFFIX_HEATER_RUNTIME,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate sensors."""
    climate_entity = hass.data[DOMAIN][config_entry.entry_id].get("entity")
    if climate_entity is None:
        return

    sensors: list[SensorEntity] = [
        SmartClimateRuntimeSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_HEATER_RUNTIME,
            name=f"{config_entry.title} verwarmingstijd vandaag",
            actuator="heater",
        ),
        SmartClimateRuntimeSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_COOLER_RUNTIME,
            name=f"{config_entry.title} koeltijd vandaag",
            actuator="cooler",
        ),
    ]

    if climate_entity.heater_watt > 0:
        sensors.append(
            SmartClimateEnergySensor(
                climate_entity=climate_entity,
                unique_id=config_entry.entry_id + SUFFIX_HEATER_ENERGY,
                name=f"{config_entry.title} verbruik verwarming vandaag",
                actuator="heater",
            )
        )
    if climate_entity.cooler_watt > 0:
        sensors.append(
            SmartClimateEnergySensor(
                climate_entity=climate_entity,
                unique_id=config_entry.entry_id + SUFFIX_COOLER_ENERGY,
                name=f"{config_entry.title} verbruik koeling vandaag",
                actuator="cooler",
            )
        )

    async_add_entities(sensors)


# ---------------------------------------------------------------------------
# Runtime sensor
# ---------------------------------------------------------------------------

class SmartClimateRuntimeSensor(SensorEntity):
    """How many hours the heater or cooler ran today."""

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, climate_entity, unique_id: str, name: str, actuator: str) -> None:
        self._climate = climate_entity
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._actuator = actuator  # "heater" or "cooler"

    async def async_added_to_hass(self) -> None:
        # Update every 30 seconds
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_update, timedelta(seconds=30)
            )
        )

    @callback
    def _async_update(self, _now=None) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        if self._actuator == "heater":
            return round(self._climate.heater_runtime_today / 60, 3)
        return round(self._climate.cooler_runtime_today / 60, 3)


# ---------------------------------------------------------------------------
# Energy sensor
# ---------------------------------------------------------------------------

class SmartClimateEnergySensor(SensorEntity):
    """Estimated energy consumed today in kWh."""

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, climate_entity, unique_id: str, name: str, actuator: str) -> None:
        self._climate = climate_entity
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._actuator = actuator

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_update, timedelta(seconds=60)
            )
        )

    @callback
    def _async_update(self, _now=None) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        if self._actuator == "heater":
            runtime_h = self._climate.heater_runtime_today / 60
            watt = self._climate.heater_watt
        else:
            runtime_h = self._climate.cooler_runtime_today / 60
            watt = self._climate.cooler_watt
        return round(watt * runtime_h / 1000, 4)
