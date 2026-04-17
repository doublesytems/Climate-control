"""Smart Climate — sensor platform.

Exposes:
* Heater runtime today (h)
* Cooler runtime today (h)
* Heater energy today (kWh)           — requires heater_watt > 0
* Cooler energy today (kWh)           — requires cooler_watt > 0
* Effectieve doeltemperatuur (°C)     — incl. weerscomp., vocht, hold, setback
* Geschatte tijd tot doel (min)       — alleen predictief algoritme
* Volgende schema-overgang (tekst)    — alleen bij schema-preset
* Geleerde verwarmingssnelheid (°C/min)
* PID-uitvoer (%)                     — alleen bij PID algoritme
* Hold resterende tijd (min)          — alleen actief tijdens hold
"""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
import homeassistant.util.dt as dt_util

from .const import (
    ALGORITHM_PID,
    DOMAIN,
    SUFFIX_COOLER_ENERGY,
    SUFFIX_COOLER_RUNTIME,
    SUFFIX_EFFECTIVE_TARGET,
    SUFFIX_HEATING_RATE,
    SUFFIX_HEATER_ENERGY,
    SUFFIX_HEATER_RUNTIME,
    SUFFIX_HOLD_REMAINING,
    SUFFIX_NEXT_SCHEDULE,
    SUFFIX_PID_OUTPUT,
    SUFFIX_TIME_TO_TARGET,
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
        # Runtime
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
        # Effectieve doeltemperatuur
        SmartClimateEffectiveTargetSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_EFFECTIVE_TARGET,
            name=f"{config_entry.title} effectieve doeltemperatuur",
        ),
        # Geleerde verwarmingssnelheid
        SmartClimateHeatRateSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_HEATING_RATE,
            name=f"{config_entry.title} verwarmingssnelheid",
        ),
        # Geschatte tijd tot doel
        SmartClimateTimeToTargetSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_TIME_TO_TARGET,
            name=f"{config_entry.title} tijd tot doel",
        ),
        # Volgende schema-overgang
        SmartClimateNextScheduleSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_NEXT_SCHEDULE,
            name=f"{config_entry.title} volgende schema",
        ),
        # PID-uitvoer
        SmartClimatePidOutputSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_PID_OUTPUT,
            name=f"{config_entry.title} PID-uitvoer",
        ),
        # Hold resterende tijd
        SmartClimateHoldRemainingSensor(
            climate_entity=climate_entity,
            unique_id=config_entry.entry_id + SUFFIX_HOLD_REMAINING,
            name=f"{config_entry.title} hold resterende tijd",
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
# Base helper
# ---------------------------------------------------------------------------

class _SmartClimateSensorBase(SensorEntity):
    """Polls the climate entity every 30 s."""

    _attr_should_poll = False

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


# ---------------------------------------------------------------------------
# Runtime sensor
# ---------------------------------------------------------------------------

class SmartClimateRuntimeSensor(_SmartClimateSensorBase):
    """Hours the heater or cooler ran today."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, climate_entity, unique_id: str, name: str, actuator: str) -> None:
        super().__init__(climate_entity, unique_id, name)
        self._actuator = actuator

    @property
    def native_value(self) -> float:
        if self._actuator == "heater":
            return round(self._climate.heater_runtime_today / 60, 3)
        return round(self._climate.cooler_runtime_today / 60, 3)


# ---------------------------------------------------------------------------
# Energy sensor
# ---------------------------------------------------------------------------

class SmartClimateEnergySensor(_SmartClimateSensorBase):
    """Estimated energy consumed today in kWh."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, climate_entity, unique_id: str, name: str, actuator: str) -> None:
        super().__init__(climate_entity, unique_id, name)
        self._actuator = actuator

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_update, timedelta(seconds=60)
            )
        )

    @property
    def native_value(self) -> float:
        if self._actuator == "heater":
            runtime_h = self._climate.heater_runtime_today / 60
            watt = self._climate.heater_watt
        else:
            runtime_h = self._climate.cooler_runtime_today / 60
            watt = self._climate.cooler_watt
        return round(watt * runtime_h / 1000, 4)


# ---------------------------------------------------------------------------
# Effectieve doeltemperatuur
# ---------------------------------------------------------------------------

class SmartClimateEffectiveTargetSensor(_SmartClimateSensorBase):
    """Actual setpoint including weather comp., humidity, hold and price setback."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer-check"

    @property
    def native_value(self) -> float | None:
        try:
            return self._climate.effective_target_temperature
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Geleerde verwarmingssnelheid
# ---------------------------------------------------------------------------

class SmartClimateHeatRateSensor(_SmartClimateSensorBase):
    """Learned heating rate in °C/min (EMA over recent sessions)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "°C/min"
    _attr_icon = "mdi:trending-up"

    @property
    def native_value(self) -> float | None:
        rate = getattr(self._climate, "_learned_heating_rate", None)
        if rate is None:
            return None
        return round(rate, 4)


# ---------------------------------------------------------------------------
# Geschatte tijd tot doel
# ---------------------------------------------------------------------------

class SmartClimateTimeToTargetSensor(_SmartClimateSensorBase):
    """Estimated minutes until the target temperature is reached."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:clock-fast"

    @property
    def native_value(self) -> float | None:
        current = getattr(self._climate, "_attr_current_temperature", None)
        if current is None:
            return None
        try:
            target = self._climate.effective_target_temperature
        except Exception:
            return None

        # Try predictive history first
        hist = None
        heater_on = getattr(self._climate, "_heater_on", False)
        cooler_on = getattr(self._climate, "_cooler_on", False)
        if heater_on:
            hist = getattr(self._climate, "_hist_heat", None)
        elif cooler_on:
            hist = getattr(self._climate, "_hist_cool", None)

        if hist is not None:
            try:
                eta = hist.minutes_to_reach(current, target)
                if eta is not None:
                    return round(eta, 1)
            except Exception:
                pass

        # Fallback: estimate from learned heating rate
        rate = getattr(self._climate, "_learned_heating_rate", None)
        if rate and rate > 0 and heater_on:
            delta = target - current
            if delta > 0:
                return round(delta / rate, 1)

        return None


# ---------------------------------------------------------------------------
# Volgende schema-overgang
# ---------------------------------------------------------------------------

class SmartClimateNextScheduleSensor(_SmartClimateSensorBase):
    """Next schedule transition as 'HH:MM → preset'."""

    _attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> str | None:
        schedule = getattr(self._climate, "_schedule", None)
        if schedule is None:
            return None
        try:
            preset, dt = schedule.get_next_change()
        except Exception:
            return None
        if preset is None or dt is None:
            return None
        local_dt = dt_util.as_local(dt)
        return f"{local_dt.strftime('%a %H:%M')} → {preset}"


# ---------------------------------------------------------------------------
# PID-uitvoer
# ---------------------------------------------------------------------------

class SmartClimatePidOutputSensor(_SmartClimateSensorBase):
    """Current PID output value (0–100 %)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> float | None:
        algorithm = getattr(self._climate, "_algorithm", None)
        if algorithm != ALGORITHM_PID:
            return None
        return round(getattr(self._climate, "_pid_output", 0.0), 1)


# ---------------------------------------------------------------------------
# Hold resterende tijd
# ---------------------------------------------------------------------------

class SmartClimateHoldRemainingSensor(_SmartClimateSensorBase):
    """Minutes remaining in hold mode (None / unavailable when not active)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_icon = "mdi:timer-lock-outline"

    @property
    def native_value(self) -> float | None:
        hold_end = getattr(self._climate, "_hold_end", None)
        hold_temp = getattr(self._climate, "_hold_temp", None)
        if hold_end is None or hold_temp is None:
            return None
        remaining = (hold_end - dt_util.utcnow()).total_seconds() / 60
        if remaining <= 0:
            return None
        return round(remaining, 1)
