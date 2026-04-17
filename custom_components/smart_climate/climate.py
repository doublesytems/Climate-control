"""Smart Climate — climate platform (full-featured version).

Features
--------
* Three control algorithms: Hysteresis, PID, Predictive
* Self-learning: heating/cooling rate learned per session (EMA), persisted across restarts
* Early Start (Tado-style): starts heating before scheduled preset change based on learned rate
* Preset modes: Comfort, Eco, Sleep, Away, Boost, Schedule
* Weekly schedule with time blocks per preset
* Presence detection (person / device_tracker)
* Open-window detection (rapid temp-drop detection)
* Vacation mode with date range
* Weather compensation (outdoor heating curve)
* Auto heat/cool mode
* Runtime & energy tracking (consumed by sensor.py)
* Boost mode with configurable duration
* PID integral persistent across restarts
"""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    EVENT_HOMEASSISTANT_START,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.util.dt as dt_util

from .const import (
    ALGORITHM_HYSTERESIS,
    ALGORITHM_PID,
    ALGORITHM_PREDICTIVE,
    ATTR_ALGORITHM,
    ATTR_BOOST_END,
    ATTR_BOOST_REMAINING,
    ATTR_COOLER_ON,
    ATTR_CASCADE_PRIMARY_ON,
    ATTR_CASCADE_REASON,
    ATTR_CASCADE_SECONDARY_ON,
    ATTR_CASCADE_SECONDARY_SINCE,
    ATTR_COOLER_RUNTIME_TODAY,
    ATTR_COOLING_RATE,
    ATTR_HEATER_ON,
    ATTR_HEATER_RUNTIME_TODAY,
    ATTR_HEATING_RATE,
    ATTR_PID_ERROR,
    ATTR_PID_INTEGRAL,
    ATTR_PID_KD,
    ATTR_PID_KI,
    ATTR_PID_KP,
    ATTR_PID_OUTPUT,
    ATTR_PREDICTED_REACH_TIME,
    ATTR_PRESENCE,
    ATTR_ACTIVE_SCHEDULE,
    ATTR_WEATHER_ADJ,
    ATTR_WEATHER_COMPENSATION,
    ATTR_WINDOW_OPEN,
    ATTR_WINDOW_OPEN_SINCE,
    AC_IDLE_FAN_ONLY,
    AC_IDLE_OFF,
    CONF_AC_IDLE_MODE,
    CONF_AC_MODE,
    CONF_ALGORITHM,
    CONF_BOOST_DURATION,
    CONF_COLD_TOLERANCE,
    CONF_COOLER,
    CONF_COOLER_WATT,
    CONF_HEATER,
    CONF_HEATER_WATT,
    CONF_HOT_TOLERANCE,
    CONF_KEEP_ALIVE,
    CONF_MAX_TEMP,
    CONF_MIN_CYCLE_DURATION,
    CONF_MIN_TEMP,
    CONF_PID_KD,
    CONF_PID_KI,
    CONF_PID_KP,
    CONF_PRESET_AWAY_TEMP,
    CONF_PRESET_BOOST_TEMP,
    CONF_PRESET_COMFORT_TEMP,
    CONF_PRESET_ECO_TEMP,
    CONF_PRESET_SLEEP_TEMP,
    CONF_PRESENCE_SENSORS,
    CONF_SCHEDULE,
    CONF_SENSOR,
    CONF_SENSOR_OUTSIDE,
    CONF_TARGET_TEMP,
    CONF_WEATHER_COMPENSATION,
    CONF_WEATHER_OUTSIDE_REF,
    CONF_WEATHER_SLOPE,
    CONF_CASCADE_DEACTIVATE_DELAY,
    CONF_CASCADE_ENABLED,
    CONF_CASCADE_PRIMARY_COOLER,
    CONF_CASCADE_PRIMARY_HEATER,
    CONF_CASCADE_TEMP_THRESHOLD,
    CONF_CASCADE_TIMEOUT,
    CONF_EARLY_START,
    CONF_LEARNING_ENABLED,
    CONF_COOL_BLOCK_OUTSIDE_TEMP,
    CONF_CASCADE_INSTANT_THRESHOLD,
    CONF_NOTIFY_ON_DELAY,
    CONF_NOTIFY_DELAY_MIN,
    CONF_NOTIFY_SERVICE,
    CONF_TEMP_RAMP,
    CONF_TEMP_RAMP_STEP,
    CONF_TEMP_RAMP_INTERVAL,
    CONF_WINDOW_DETECTION,
    CONF_WINDOW_SENSOR,
    CONF_WINDOW_OPEN_DURATION,
    CONF_WINDOW_TEMP_DROP,
    CONF_WINDOW_TEMP_DROP_TIME,
    CONF_FROST_PROTECTION_TEMP,
    CONF_SENSOR_TIMEOUT_MIN,
    CONF_HUMIDITY_SENSOR,
    CONF_HUMIDITY_REF,
    CONF_HUMIDITY_FACTOR,
    CONF_ENERGY_PRICE_SENSOR,
    CONF_ENERGY_PRICE_THRESHOLD,
    CONF_ENERGY_PRICE_SETBACK,
    CONF_AUTO_MODE,
    CONF_AUTO_MODE_COOL_THRESHOLD,
    CONF_AUTO_MODE_HEAT_THRESHOLD,
    CONF_VACATION_CALENDAR,
    DEFAULT_BOOST_DURATION,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_PID_KD,
    DEFAULT_PID_KI,
    DEFAULT_PID_KP,
    DEFAULT_PRESET_AWAY,
    DEFAULT_PRESET_BOOST,
    DEFAULT_PRESET_COMFORT,
    DEFAULT_PRESET_ECO,
    DEFAULT_PRESET_SLEEP,
    DEFAULT_TARGET_TEMP,
    DEFAULT_TOLERANCE,
    DEFAULT_WEATHER_OUTSIDE_REF,
    DEFAULT_WEATHER_SLOPE,
    DEFAULT_WINDOW_OPEN_DURATION,
    DEFAULT_WINDOW_TEMP_DROP,
    DEFAULT_AC_IDLE_MODE,
    DEFAULT_CASCADE_DEACTIVATE_DELAY,
    DEFAULT_CASCADE_INSTANT_THRESHOLD,
    DEFAULT_CASCADE_TEMP_THRESHOLD,
    DEFAULT_CASCADE_TIMEOUT,
    DEFAULT_COOL_BLOCK_OUTSIDE_TEMP,
    DEFAULT_NOTIFY_DELAY_MIN,
    DEFAULT_TEMP_RAMP_STEP,
    DEFAULT_TEMP_RAMP_INTERVAL,
    DEFAULT_FROST_PROTECTION_TEMP,
    DEFAULT_SENSOR_TIMEOUT_MIN,
    DEFAULT_HUMIDITY_REF,
    DEFAULT_HUMIDITY_FACTOR,
    DEFAULT_ENERGY_PRICE_THRESHOLD,
    DEFAULT_ENERGY_PRICE_SETBACK,
    DEFAULT_AUTO_MODE_COOL_THRESHOLD,
    DEFAULT_AUTO_MODE_HEAT_THRESHOLD,
    NOTIFICATION_ID_PREFIX,
    SERVICE_SET_HOLD,
    SERVICE_CLEAR_HOLD,
    ATTR_HOLD_TEMP,
    ATTR_HOLD_DURATION,
    DEFAULT_WINDOW_TEMP_DROP_TIME,
    CONF_MULTISPLIT_GROUP,
    CONF_MULTISPLIT_PRIORITY_TEMP,
    CONF_MULTISPLIT_SWITCH_MARGIN,
    DEFAULT_MULTISPLIT_PRIORITY_TEMP,
    DEFAULT_MULTISPLIT_SWITCH_MARGIN,
    CONF_WEATHER_ENTITY,
    CONF_FORECAST_COOL_BLOCK_THRESHOLD,
    CONF_FORECAST_COOL_BLOCK_HOURS,
    DEFAULT_FORECAST_COOL_BLOCK_THRESHOLD,
    DEFAULT_FORECAST_COOL_BLOCK_HOURS,
    DOMAIN,
    EMA_ALPHA,
    PID_OUTPUT_MAX,
    PID_OUTPUT_MIN,
    PREDICTIVE_HISTORY_SIZE,
    PREDICTIVE_MIN_SAMPLES,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SCHEDULE,
    PRESET_SLEEP,
)
from .schedule import WeekSchedule
from .storage import SmartClimateStorage

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smart Climate platform."""
    d = {**config_entry.data, **config_entry.options}

    entity = SmartClimate(
        hass=hass,
        config_entry=config_entry,
        unique_id=config_entry.entry_id,
        name=config_entry.title,
        heater_entity_id=d.get(CONF_HEATER),
        cooler_entity_id=d.get(CONF_COOLER),
        sensor_entity_id=d[CONF_SENSOR],
        outside_sensor_entity_id=d.get(CONF_SENSOR_OUTSIDE),
        algorithm=d.get(CONF_ALGORITHM, ALGORITHM_HYSTERESIS),
        cold_tolerance=float(d.get(CONF_COLD_TOLERANCE, DEFAULT_TOLERANCE)),
        hot_tolerance=float(d.get(CONF_HOT_TOLERANCE, DEFAULT_TOLERANCE)),
        target_temp=float(d.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP)),
        min_temp=float(d.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)),
        max_temp=float(d.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)),
        keep_alive=timedelta(seconds=int(d.get(CONF_KEEP_ALIVE, 30))),
        min_cycle_duration=timedelta(seconds=int(d.get(CONF_MIN_CYCLE_DURATION, 10))),
        pid_kp=float(d.get(CONF_PID_KP, DEFAULT_PID_KP)),
        pid_ki=float(d.get(CONF_PID_KI, DEFAULT_PID_KI)),
        pid_kd=float(d.get(CONF_PID_KD, DEFAULT_PID_KD)),
        ac_mode=bool(d.get(CONF_AC_MODE, False)),
        preset_temps={
            PRESET_COMFORT: float(d.get(CONF_PRESET_COMFORT_TEMP, DEFAULT_PRESET_COMFORT)),
            PRESET_ECO: float(d.get(CONF_PRESET_ECO_TEMP, DEFAULT_PRESET_ECO)),
            PRESET_SLEEP: float(d.get(CONF_PRESET_SLEEP_TEMP, DEFAULT_PRESET_SLEEP)),
            PRESET_AWAY: float(d.get(CONF_PRESET_AWAY_TEMP, DEFAULT_PRESET_AWAY)),
            PRESET_BOOST: float(d.get(CONF_PRESET_BOOST_TEMP, DEFAULT_PRESET_BOOST)),
        },
        boost_duration=int(d.get(CONF_BOOST_DURATION, DEFAULT_BOOST_DURATION)),
        presence_sensors=list(d.get(CONF_PRESENCE_SENSORS) or []),
        window_detection=bool(d.get(CONF_WINDOW_DETECTION, False)),
        window_temp_drop=float(d.get(CONF_WINDOW_TEMP_DROP, DEFAULT_WINDOW_TEMP_DROP)),
        window_temp_drop_time=int(d.get(CONF_WINDOW_TEMP_DROP_TIME, DEFAULT_WINDOW_TEMP_DROP_TIME)),
        window_open_duration=int(d.get(CONF_WINDOW_OPEN_DURATION, DEFAULT_WINDOW_OPEN_DURATION)),
        weather_compensation=bool(d.get(CONF_WEATHER_COMPENSATION, False)),
        weather_slope=float(d.get(CONF_WEATHER_SLOPE, DEFAULT_WEATHER_SLOPE)),
        weather_outside_ref=float(d.get(CONF_WEATHER_OUTSIDE_REF, DEFAULT_WEATHER_OUTSIDE_REF)),
        heater_watt=float(d.get(CONF_HEATER_WATT, 0)),
        cooler_watt=float(d.get(CONF_COOLER_WATT, 0)),
        schedule_data=list(d.get(CONF_SCHEDULE) or []),
        learning_enabled=bool(d.get(CONF_LEARNING_ENABLED, True)),
        early_start=bool(d.get(CONF_EARLY_START, True)),
        cascade_enabled=bool(d.get(CONF_CASCADE_ENABLED, False)),
        cascade_primary_heater=d.get(CONF_CASCADE_PRIMARY_HEATER),
        cascade_primary_cooler=d.get(CONF_CASCADE_PRIMARY_COOLER),
        cascade_timeout_min=int(d.get(CONF_CASCADE_TIMEOUT, DEFAULT_CASCADE_TIMEOUT)),
        cascade_temp_threshold=float(d.get(CONF_CASCADE_TEMP_THRESHOLD, DEFAULT_CASCADE_TEMP_THRESHOLD)),
        cascade_deactivate_delay_min=int(d.get(CONF_CASCADE_DEACTIVATE_DELAY, DEFAULT_CASCADE_DEACTIVATE_DELAY)),
        cascade_instant_threshold=float(d[CONF_CASCADE_INSTANT_THRESHOLD]) if d.get(CONF_CASCADE_INSTANT_THRESHOLD) is not None else None,
        ac_idle_mode=d.get(CONF_AC_IDLE_MODE, DEFAULT_AC_IDLE_MODE),
        window_sensor=d.get(CONF_WINDOW_SENSOR),
        cool_block_outside_temp=float(d[CONF_COOL_BLOCK_OUTSIDE_TEMP]) if d.get(CONF_COOL_BLOCK_OUTSIDE_TEMP) is not None else None,
        temp_ramp=bool(d.get(CONF_TEMP_RAMP, False)),
        temp_ramp_step=float(d.get(CONF_TEMP_RAMP_STEP, DEFAULT_TEMP_RAMP_STEP)),
        temp_ramp_interval=int(d.get(CONF_TEMP_RAMP_INTERVAL, DEFAULT_TEMP_RAMP_INTERVAL)),
        notify_on_delay=bool(d.get(CONF_NOTIFY_ON_DELAY, False)),
        notify_delay_min=int(d.get(CONF_NOTIFY_DELAY_MIN, DEFAULT_NOTIFY_DELAY_MIN)),
        notify_service=d.get(CONF_NOTIFY_SERVICE),
        frost_protection_temp=float(d[CONF_FROST_PROTECTION_TEMP]) if d.get(CONF_FROST_PROTECTION_TEMP) is not None else None,
        sensor_timeout_min=int(d.get(CONF_SENSOR_TIMEOUT_MIN, DEFAULT_SENSOR_TIMEOUT_MIN)) if d.get(CONF_SENSOR_TIMEOUT_MIN) else None,
        humidity_sensor=d.get(CONF_HUMIDITY_SENSOR),
        humidity_ref=float(d.get(CONF_HUMIDITY_REF, DEFAULT_HUMIDITY_REF)),
        humidity_factor=float(d.get(CONF_HUMIDITY_FACTOR, DEFAULT_HUMIDITY_FACTOR)),
        energy_price_sensor=d.get(CONF_ENERGY_PRICE_SENSOR),
        energy_price_threshold=float(d.get(CONF_ENERGY_PRICE_THRESHOLD, DEFAULT_ENERGY_PRICE_THRESHOLD)),
        energy_price_setback=float(d.get(CONF_ENERGY_PRICE_SETBACK, DEFAULT_ENERGY_PRICE_SETBACK)),
        auto_mode=bool(d.get(CONF_AUTO_MODE, False)),
        auto_mode_cool_threshold=float(d.get(CONF_AUTO_MODE_COOL_THRESHOLD, DEFAULT_AUTO_MODE_COOL_THRESHOLD)),
        auto_mode_heat_threshold=float(d.get(CONF_AUTO_MODE_HEAT_THRESHOLD, DEFAULT_AUTO_MODE_HEAT_THRESHOLD)),
        vacation_calendar=d.get(CONF_VACATION_CALENDAR),
        multisplit_group=d.get(CONF_MULTISPLIT_GROUP) or None,
        multisplit_priority_temp=float(d.get(CONF_MULTISPLIT_PRIORITY_TEMP, DEFAULT_MULTISPLIT_PRIORITY_TEMP)),
        multisplit_switch_margin=float(d.get(CONF_MULTISPLIT_SWITCH_MARGIN, DEFAULT_MULTISPLIT_SWITCH_MARGIN)),
        weather_entity=d.get(CONF_WEATHER_ENTITY) or None,
        forecast_cool_block_threshold=float(d[CONF_FORECAST_COOL_BLOCK_THRESHOLD]) if d.get(CONF_FORECAST_COOL_BLOCK_THRESHOLD) is not None else None,
        forecast_cool_block_hours=int(d.get(CONF_FORECAST_COOL_BLOCK_HOURS, DEFAULT_FORECAST_COOL_BLOCK_HOURS)),
    )

    # Registreer hold-modus services
    async def _async_handle_set_hold(call) -> None:
        temp = call.data.get(ATTR_HOLD_TEMP)
        duration_h = call.data.get(ATTR_HOLD_DURATION, 2)
        if temp is not None:
            await entity.async_set_hold(float(temp), float(duration_h))

    async def _async_handle_clear_hold(call) -> None:
        await entity.async_clear_hold()

    hass.services.async_register(DOMAIN, SERVICE_SET_HOLD, _async_handle_set_hold)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_HOLD, _async_handle_clear_hold)

    # Load persistent storage (learned rates etc.)
    await entity.async_load_storage()

    # Store reference so helper entities and services can find it
    hass.data[DOMAIN][config_entry.entry_id]["entity"] = entity

    async_add_entities([entity])


# ---------------------------------------------------------------------------
# PID Controller
# ---------------------------------------------------------------------------

class PIDController:
    """Discrete PID with anti-windup and derivative-on-measurement."""

    def __init__(self, kp: float, ki: float, kd: float) -> None:
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self._integral: float = 0.0
        self._prev_error: float = 0.0
        self._last_time: datetime | None = None

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = 0.0
        self._last_time = None

    def compute(self, setpoint: float, measured: float) -> float:
        """Return output in [0, 100]."""
        now = dt_util.utcnow()
        error = setpoint - measured
        dt = 1.0
        if self._last_time is not None:
            dt = max((now - self._last_time).total_seconds(), 1.0)

        proportional = self.kp * error
        self._integral = max(
            PID_OUTPUT_MIN,
            min(PID_OUTPUT_MAX, self._integral + self.ki * error * dt),
        )
        derivative = -self.kd * (error - self._prev_error) / dt

        output = max(PID_OUTPUT_MIN, min(PID_OUTPUT_MAX, proportional + self._integral + derivative))
        self._prev_error = error
        self._last_time = now
        return output

    @property
    def integral(self) -> float:
        return self._integral

    @property
    def last_error(self) -> float:
        return self._prev_error


# ---------------------------------------------------------------------------
# Temperature history for predictive algorithm
# ---------------------------------------------------------------------------

class TemperatureHistory:
    """Rolling window of (timestamp, temperature) for rate estimation."""

    def __init__(self, maxlen: int = PREDICTIVE_HISTORY_SIZE) -> None:
        self._samples: deque[tuple[datetime, float]] = deque(maxlen=maxlen)

    def add(self, temp: float) -> None:
        self._samples.append((dt_util.utcnow(), temp))

    def clear(self) -> None:
        self._samples.clear()

    @property
    def rate_per_minute(self) -> float | None:
        """°C/min via linear regression. None if not enough data."""
        if len(self._samples) < PREDICTIVE_MIN_SAMPLES:
            return None
        t0 = self._samples[0][0]
        times = [(s[0] - t0).total_seconds() / 60.0 for s in self._samples]
        temps = [s[1] for s in self._samples]
        n = len(times)
        mean_t = sum(times) / n
        mean_temp = sum(temps) / n
        num = sum((times[i] - mean_t) * (temps[i] - mean_temp) for i in range(n))
        den = sum((times[i] - mean_t) ** 2 for i in range(n))
        return num / den if abs(den) > 1e-9 else None

    def minutes_to_reach(self, current: float, target: float) -> float | None:
        rate = self.rate_per_minute
        if rate is None or abs(rate) < 1e-6:
            return None
        diff = target - current
        if (diff > 0 and rate <= 0) or (diff < 0 and rate >= 0):
            return None
        return diff / rate


class _SeedableTemperatureHistory(TemperatureHistory):
    """TemperatureHistory that can be pre-seeded with a known rate.

    Used to initialise the predictive algorithm immediately on startup
    with previously learned rates from persistent storage, rather than
    waiting for PREDICTIVE_MIN_SAMPLES new readings.
    """

    def __init__(self, known_rate: float, maxlen: int = PREDICTIVE_HISTORY_SIZE) -> None:
        super().__init__(maxlen)
        self._known_rate = known_rate

    @property
    def rate_per_minute(self) -> float | None:
        """Return live regression if enough samples, else fall back to known rate."""
        live = super().rate_per_minute
        return live if live is not None else self._known_rate


# ---------------------------------------------------------------------------
# Main Climate Entity
# ---------------------------------------------------------------------------

class SmartClimate(ClimateEntity, RestoreEntity):
    """Smart thermostat entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        unique_id: str,
        name: str,
        heater_entity_id: str | None,
        cooler_entity_id: str | None,
        sensor_entity_id: str,
        outside_sensor_entity_id: str | None,
        algorithm: str,
        cold_tolerance: float,
        hot_tolerance: float,
        target_temp: float,
        min_temp: float,
        max_temp: float,
        keep_alive: timedelta,
        min_cycle_duration: timedelta,
        pid_kp: float,
        pid_ki: float,
        pid_kd: float,
        ac_mode: bool,
        preset_temps: dict[str, float],
        boost_duration: int,
        presence_sensors: list[str],
        window_detection: bool,
        window_temp_drop: float,
        window_temp_drop_time: int,
        window_open_duration: int,
        weather_compensation: bool,
        weather_slope: float,
        weather_outside_ref: float,
        heater_watt: float,
        cooler_watt: float,
        schedule_data: list[dict],
        learning_enabled: bool,
        early_start: bool,
        cascade_enabled: bool,
        cascade_primary_heater: str | None,
        cascade_primary_cooler: str | None,
        cascade_timeout_min: int,
        cascade_temp_threshold: float,
        cascade_deactivate_delay_min: int,
        cascade_instant_threshold: float | None = None,
        ac_idle_mode: str = AC_IDLE_OFF,
        window_sensor: str | None = None,
        cool_block_outside_temp: float | None = None,
        temp_ramp: bool = False,
        temp_ramp_step: float = DEFAULT_TEMP_RAMP_STEP,
        temp_ramp_interval: int = DEFAULT_TEMP_RAMP_INTERVAL,
        notify_on_delay: bool = False,
        notify_delay_min: int = DEFAULT_NOTIFY_DELAY_MIN,
        notify_service: str | None = None,
        frost_protection_temp: float | None = None,
        sensor_timeout_min: int | None = None,
        humidity_sensor: str | None = None,
        humidity_ref: float = DEFAULT_HUMIDITY_REF,
        humidity_factor: float = DEFAULT_HUMIDITY_FACTOR,
        energy_price_sensor: str | None = None,
        energy_price_threshold: float = DEFAULT_ENERGY_PRICE_THRESHOLD,
        energy_price_setback: float = DEFAULT_ENERGY_PRICE_SETBACK,
        auto_mode: bool = False,
        auto_mode_cool_threshold: float = DEFAULT_AUTO_MODE_COOL_THRESHOLD,
        auto_mode_heat_threshold: float = DEFAULT_AUTO_MODE_HEAT_THRESHOLD,
        vacation_calendar: str | None = None,
        multisplit_group: str | None = None,
        multisplit_priority_temp: float = DEFAULT_MULTISPLIT_PRIORITY_TEMP,
        multisplit_switch_margin: float = DEFAULT_MULTISPLIT_SWITCH_MARGIN,
        weather_entity: str | None = None,
        forecast_cool_block_threshold: float | None = None,
        forecast_cool_block_hours: int = DEFAULT_FORECAST_COOL_BLOCK_HOURS,
    ) -> None:
        self.hass = hass
        self._config_entry = config_entry
        self._attr_unique_id = unique_id
        self._attr_name = name

        # Actuators / sensors
        self._heater_entity_id = heater_entity_id
        self._cooler_entity_id = cooler_entity_id
        self._sensor_entity_id = sensor_entity_id
        self._outside_sensor_entity_id = outside_sensor_entity_id

        # Algorithm
        self._algorithm = algorithm
        self._cold_tolerance = cold_tolerance
        self._hot_tolerance = hot_tolerance
        self._attr_target_temperature = target_temp
        self._attr_min_temp = min_temp
        self._attr_max_temp = max_temp
        self._keep_alive = keep_alive
        self._min_cycle_duration = min_cycle_duration
        self._ac_mode = ac_mode

        # PID
        self._pid = PIDController(pid_kp, pid_ki, pid_kd)
        self._pid_output: float = 0.0

        # Predictive
        self._hist_heat = TemperatureHistory()
        self._hist_cool = TemperatureHistory()
        self._hist_idle = TemperatureHistory()

        # Presets
        self._preset_temps = preset_temps
        self._boost_duration = boost_duration  # minutes
        self._attr_preset_mode: str = PRESET_NONE
        self._prev_preset: str = PRESET_NONE

        # Boost
        self._boost_end: datetime | None = None

        # Presence
        self._presence_sensors = presence_sensors
        self._presence_detected: bool = True  # assume home until told otherwise

        # Window detection
        self._window_detection = window_detection
        self._window_temp_drop = window_temp_drop
        self._window_temp_drop_time = window_temp_drop_time  # minutes
        self._window_open_duration = window_open_duration  # minutes
        self._window_open: bool = False
        self._window_open_since: datetime | None = None
        self._temp_history: deque[tuple[datetime, float]] = deque(maxlen=30)

        # Weather compensation
        self._weather_compensation = weather_compensation
        self._weather_slope = weather_slope
        self._weather_outside_ref = weather_outside_ref
        self._weather_adj: float = 0.0

        # Vacation
        self._vacation_start: date | None = None
        self._vacation_end: date | None = None
        self._vacation_temp: float = DEFAULT_PRESET_AWAY

        # Schedule
        self._schedule = WeekSchedule(schedule_data)

        # Runtime tracking (minutes on today)
        self._heater_on_since: datetime | None = None
        self._cooler_on_since: datetime | None = None
        self._heater_runtime_today: float = 0.0  # minutes
        self._cooler_runtime_today: float = 0.0
        self._runtime_reset_day: int = -1

        # Internal state
        self._attr_current_temperature: float | None = None
        self._outside_temp: float | None = None
        self._hvac_mode = HVACMode.OFF
        self._heater_on = False
        self._cooler_on = False
        self._last_switch_time: datetime | None = None

        # Energy (watt)
        self.heater_watt = heater_watt
        self.cooler_watt = cooler_watt

        # HVAC modes
        modes = [HVACMode.OFF]
        if heater_entity_id and cooler_entity_id:
            modes += [HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL]
        elif heater_entity_id:
            modes += [HVACMode.HEAT]
            if ac_mode:
                modes += [HVACMode.COOL]
        elif cooler_entity_id:
            modes += [HVACMode.COOL]
        self._attr_hvac_modes = modes

        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
        )
        self._attr_preset_modes = [PRESET_NONE] + [
            PRESET_COMFORT, PRESET_ECO, PRESET_SLEEP, PRESET_AWAY, PRESET_BOOST, PRESET_SCHEDULE
        ]

        # Cascade (primaire + secundaire verwarming/koeling)
        self._cascade_enabled = cascade_enabled
        self._cascade_primary_heater = cascade_primary_heater
        self._cascade_primary_cooler = cascade_primary_cooler
        self._cascade_timeout_min = cascade_timeout_min
        self._cascade_temp_threshold = cascade_temp_threshold
        self._cascade_deactivate_delay_min = cascade_deactivate_delay_min
        self._cascade_instant_threshold = cascade_instant_threshold
        self._ac_idle_mode = ac_idle_mode

        self._cascade_primary_heat_on: bool = False
        self._cascade_primary_cool_on: bool = False
        self._cascade_primary_start_time: datetime | None = None
        self._cascade_secondary_active: bool = False
        self._cascade_secondary_start_time: datetime | None = None
        self._cascade_reason: str = ""

        # Window sensor (binary_sensor — directe detectie, hogere prioriteit dan temp-val)
        self._window_sensor = window_sensor

        # Koeling blokkeren bij lage buitentemperatuur
        self._cool_block_outside_temp = cool_block_outside_temp

        # Geleidelijke preset-overgang (ramp)
        self._temp_ramp = temp_ramp
        self._temp_ramp_step = temp_ramp_step
        self._temp_ramp_interval = temp_ramp_interval
        self._ramp_target: float | None = None
        self._ramp_cancel: Any = None  # callable returned by async_track_time_interval

        # Persistent notification bij vertraging
        self._notify_on_delay = notify_on_delay
        self._notify_delay_min = notify_delay_min
        self._notify_service = notify_service
        self._heat_cool_start_time: datetime | None = None
        self._notify_sent: bool = False

        # Vorstbeveiliging
        self._frost_protection_temp = frost_protection_temp
        self._frost_active: bool = False

        # Sensorfailsafe
        self._sensor_timeout_min = sensor_timeout_min
        self._last_sensor_update: datetime | None = None

        # Vochtcomfortcorrectie
        self._humidity_sensor = humidity_sensor
        self._humidity_ref = humidity_ref
        self._humidity_factor = humidity_factor
        self._current_humidity: float | None = None
        self._humidity_adj: float = 0.0

        # Prijsgestuurde setback
        self._energy_price_sensor = energy_price_sensor
        self._energy_price_threshold = energy_price_threshold
        self._energy_price_setback = energy_price_setback
        self._current_energy_price: float | None = None
        self._price_setback_active: bool = False

        # Hold-modus
        self._hold_temp: float | None = None
        self._hold_end: datetime | None = None

        # Seizoensdetectie
        self._auto_mode = auto_mode
        self._auto_mode_cool_threshold = auto_mode_cool_threshold
        self._auto_mode_heat_threshold = auto_mode_heat_threshold

        # HA Calendar koppeling
        self._vacation_calendar = vacation_calendar

        # Self-learning
        self._learning_enabled = learning_enabled
        self._early_start = early_start
        self._learned_heating_rate: float | None = None   # °C/min EMA
        self._learned_cooling_rate: float | None = None   # °C/min EMA
        self._session_start_temp: float | None = None     # temp at heater-on
        self._session_start_time: datetime | None = None  # time at heater-on
        self._storage: SmartClimateStorage | None = None

        # Early start tracking
        self._early_start_active: bool = False  # True when heating early for schedule
        self._early_start_target_preset: str | None = None

        # Multi-split groepscoördinatie
        self._multisplit_group = multisplit_group
        self._multisplit_priority_temp = multisplit_priority_temp
        self._multisplit_switch_margin = multisplit_switch_margin
        self._multisplit_allowed_mode: str | None = None  # "heat", "cool" or None

        # Voorspellende koelblokkering
        self._weather_entity = weather_entity
        self._forecast_cool_block_threshold = forecast_cool_block_threshold
        self._forecast_cool_block_hours = forecast_cool_block_hours
        self._forecast_cool_blocked: bool = False
        self._forecast_min_temp: float | None = None

    # ------------------------------------------------------------------
    # Public accessors used by helper entities
    # ------------------------------------------------------------------

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @algorithm.setter
    def algorithm(self, value: str) -> None:
        self._algorithm = value
        self._pid.reset()
        self.hass.async_create_task(self._async_control_heating())
        self.async_write_ha_state()

    @property
    def pid_kp(self) -> float:
        return self._pid.kp

    @pid_kp.setter
    def pid_kp(self, value: float) -> None:
        self._pid.kp = value
        self._pid.reset()

    @property
    def pid_ki(self) -> float:
        return self._pid.ki

    @pid_ki.setter
    def pid_ki(self, value: float) -> None:
        self._pid.ki = value
        self._pid.reset()

    @property
    def pid_kd(self) -> float:
        return self._pid.kd

    @pid_kd.setter
    def pid_kd(self, value: float) -> None:
        self._pid.kd = value
        self._pid.reset()

    @property
    def heater_runtime_today(self) -> float:
        """Total heater on-time today in minutes."""
        total = self._heater_runtime_today
        if self._heater_on and self._heater_on_since:
            total += (dt_util.utcnow() - self._heater_on_since).total_seconds() / 60
        return total

    @property
    def cooler_runtime_today(self) -> float:
        total = self._cooler_runtime_today
        if self._cooler_on and self._cooler_on_since:
            total += (dt_util.utcnow() - self._cooler_on_since).total_seconds() / 60
        return total

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_load_storage(self) -> None:
        """Load learned data from persistent storage. Called before entity is added."""
        self._storage = SmartClimateStorage(self.hass, self._attr_unique_id)
        await self._storage.async_load()

        # Seed the algorithm with previously learned rates
        if self._storage.heating_rate is not None:
            self._learned_heating_rate = self._storage.heating_rate
            self._hist_heat = _SeedableTemperatureHistory(
                self._learned_heating_rate, PREDICTIVE_HISTORY_SIZE
            )
        if self._storage.cooling_rate is not None:
            self._learned_cooling_rate = self._storage.cooling_rate

        # Restore PID integral so it doesn't start from zero
        if self._storage.pid_integral != 0.0:
            self._pid._integral = self._storage.pid_integral

        _LOGGER.debug(
            "[%s] Storage loaded — heating_rate=%.4f, cooling_rate=%s",
            self._attr_name,
            self._learned_heating_rate or 0,
            self._learned_cooling_rate,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            if last_state.state in [m.value for m in HVACMode]:
                self._hvac_mode = HVACMode(last_state.state)
            attrs = last_state.attributes
            if ATTR_TEMPERATURE in attrs:
                self._attr_target_temperature = float(attrs[ATTR_TEMPERATURE])
            preset = attrs.get("preset_mode")
            if preset in (self._attr_preset_modes or []):
                self._attr_preset_mode = preset

        # Track temperature sensor(s)
        sensors = [self._sensor_entity_id]
        if self._outside_sensor_entity_id:
            sensors.append(self._outside_sensor_entity_id)

        self.async_on_remove(
            async_track_state_change_event(self.hass, sensors, self._async_sensor_changed)
        )

        # Track heater/cooler switches
        switches = [e for e in [self._heater_entity_id, self._cooler_entity_id] if e]
        if switches:
            self.async_on_remove(
                async_track_state_change_event(self.hass, switches, self._async_switch_changed)
            )

        # Track presence sensors
        if self._presence_sensors:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._presence_sensors, self._async_presence_changed
                )
            )

        # Track window sensor (binary_sensor)
        if self._window_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._window_sensor], self._async_window_sensor_changed
                )
            )

        # Track humidity sensor
        if self._humidity_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._humidity_sensor], self._async_humidity_changed
                )
            )

        # Track energy price sensor
        if self._energy_price_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._energy_price_sensor], self._async_price_changed
                )
            )

        # Track vacation calendar
        if self._vacation_calendar:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._vacation_calendar], self._async_calendar_changed
                )
            )

        # Track weather entity (voor forecast-gebaseerde koelblokkering)
        if self._weather_entity and self._forecast_cool_block_threshold is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._weather_entity], self._async_weather_changed
                )
            )

        # Multi-split groepsregistratie
        if self._multisplit_group:
            groups = self.hass.data[DOMAIN].setdefault("_groups", {})
            groups.setdefault(self._multisplit_group, {"mode": None})

        # Keep-alive interval
        if self._keep_alive:
            self.async_on_remove(
                async_track_time_interval(self.hass, self._async_control_heating, self._keep_alive)
            )

        # Schedule checker — every minute at :00 seconds
        self.async_on_remove(
            async_track_time_change(self.hass, self._async_schedule_tick, second=0)
        )

        # Daily runtime reset at midnight
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight_reset, hour=0, minute=0, second=0
            )
        )

        @callback
        def _async_startup(_event=None) -> None:
            sensor_state = self.hass.states.get(self._sensor_entity_id)
            if sensor_state and sensor_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._update_temp(sensor_state)
            if self._outside_sensor_entity_id:
                outside = self.hass.states.get(self._outside_sensor_entity_id)
                if outside and outside.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    self._update_outside_temp(outside)
            if self._humidity_sensor:
                hum = self.hass.states.get(self._humidity_sensor)
                if hum and hum.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    self._update_humidity(hum)
            if self._energy_price_sensor:
                price = self.hass.states.get(self._energy_price_sensor)
                if price and price.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    self._update_energy_price(price)
            if self._vacation_calendar:
                cal = self.hass.states.get(self._vacation_calendar)
                if cal:
                    self._update_vacation_calendar(cal)
            if self._weather_entity and self._forecast_cool_block_threshold is not None:
                weather_state = self.hass.states.get(self._weather_entity)
                if weather_state:
                    self._update_forecast_cool_block(weather_state)
            self._update_presence()
            self.hass.async_create_task(self._async_control_heating())

        if self.hass.is_running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._heater_on or self._cascade_primary_heat_on:
            return HVACAction.HEATING
        if self._cooler_on or self._cascade_primary_cool_on:
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def effective_target_temperature(self) -> float:
        """Target including preset offset, weather compensation, humidity and price adjustments."""
        # Hold-modus overschrijft alles
        if self._hold_temp is not None and self._hold_end and dt_util.utcnow() <= self._hold_end:
            return self._hold_temp
        base = self._attr_target_temperature or DEFAULT_TARGET_TEMP
        # Weerscompensatie en vochtcorrectie alleen bij pure verwarmingsmodus.
        # In COOL en HEAT_COOL (auto) verlagen beide correcties het effectieve koeldoel,
        # waardoor de ruimte veel kouder wordt dan de gebruiker instelt.
        adj = 0.0
        if self._hvac_mode == HVACMode.HEAT:
            adj += self._weather_adj
            adj -= self._humidity_adj
        if self._price_setback_active:
            # Setback: bij verwarmen lager doel, bij koelen hoger doel
            if self._hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL):
                adj -= self._energy_price_setback
            elif self._hvac_mode == HVACMode.COOL:
                adj += self._energy_price_setback
        return round(base + adj, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        attrs: dict[str, Any] = {
            ATTR_ALGORITHM: self._algorithm,
            ATTR_HEATER_ON: self._heater_on,
            ATTR_COOLER_ON: self._cooler_on,
            ATTR_WINDOW_OPEN: self._window_open,
            ATTR_PRESENCE: self._presence_detected,
            ATTR_WEATHER_COMPENSATION: self._weather_compensation,
            ATTR_WEATHER_ADJ: round(self._weather_adj, 2),
            ATTR_HEATER_RUNTIME_TODAY: round(self.heater_runtime_today / 60, 3),
            ATTR_COOLER_RUNTIME_TODAY: round(self.cooler_runtime_today / 60, 3),
            "learning_enabled": self._learning_enabled,
            "early_start_active": self._early_start_active,
            "frost_active": self._frost_active,
            "price_setback_active": self._price_setback_active,
            "humidity_adjustment": round(self._humidity_adj, 2) if self._humidity_sensor else None,
            "auto_mode": self._auto_mode,
        }
        if self._learned_heating_rate is not None:
            attrs["learned_heating_rate_c_per_min"] = round(self._learned_heating_rate, 4)
        if self._learned_cooling_rate is not None:
            attrs["learned_cooling_rate_c_per_min"] = round(self._learned_cooling_rate, 4)
        if self._cascade_enabled:
            attrs[ATTR_CASCADE_PRIMARY_ON] = self._cascade_primary_heat_on or self._cascade_primary_cool_on
            attrs[ATTR_CASCADE_SECONDARY_ON] = self._cascade_secondary_active
            attrs[ATTR_CASCADE_REASON] = self._cascade_reason
            if self._cascade_secondary_active and self._cascade_secondary_start_time:
                elapsed = (now - self._cascade_secondary_start_time).total_seconds() / 60
                attrs[ATTR_CASCADE_SECONDARY_SINCE] = round(elapsed, 1)
        if self._window_open and self._window_open_since:
            attrs[ATTR_WINDOW_OPEN_SINCE] = self._window_open_since.isoformat()
        if self._hold_temp is not None and self._hold_end and dt_util.utcnow() <= self._hold_end:
            remaining_h = (self._hold_end - dt_util.utcnow()).total_seconds() / 3600
            attrs["hold_temp"] = self._hold_temp
            attrs["hold_remaining_h"] = round(remaining_h, 2)
        if self._boost_end:
            remaining = max(0.0, (self._boost_end - now).total_seconds() / 60)
            attrs[ATTR_BOOST_END] = self._boost_end.isoformat()
            attrs[ATTR_BOOST_REMAINING] = round(remaining, 1)
        if self._schedule:
            attrs[ATTR_ACTIVE_SCHEDULE] = self._schedule.get_active_preset()
        if self._algorithm == ALGORITHM_PID:
            attrs.update({
                ATTR_PID_KP: self._pid.kp,
                ATTR_PID_KI: self._pid.ki,
                ATTR_PID_KD: self._pid.kd,
                ATTR_PID_OUTPUT: round(self._pid_output, 2),
                ATTR_PID_ERROR: round(self._pid.last_error, 3),
                ATTR_PID_INTEGRAL: round(self._pid.integral, 3),
            })
        if self._algorithm == ALGORITHM_PREDICTIVE:
            hist = self._hist_heat if self._heater_on else self._hist_cool
            rate = hist.rate_per_minute
            if rate is not None:
                key = ATTR_HEATING_RATE if self._heater_on else ATTR_COOLING_RATE
                attrs[key] = round(rate, 4)
            if self._attr_current_temperature is not None:
                eta = hist.minutes_to_reach(
                    self._attr_current_temperature, self.effective_target_temperature
                )
                if eta is not None:
                    attrs[ATTR_PREDICTED_REACH_TIME] = round(eta, 1)
        if self._multisplit_group:
            attrs["multisplit_group"] = self._multisplit_group
            attrs["multisplit_group_mode"] = self.hass.data[DOMAIN].get("_groups", {}).get(
                self._multisplit_group, {}
            ).get("mode")
        if self._weather_entity and self._forecast_cool_block_threshold is not None:
            attrs["forecast_cool_blocked"] = self._forecast_cool_blocked
            if self._forecast_min_temp is not None:
                attrs["forecast_min_temp_next_hours"] = round(self._forecast_min_temp, 1)
        return attrs

    # ------------------------------------------------------------------
    # Service calls
    # ------------------------------------------------------------------

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self._hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            self._pid.reset()
            await self._async_turn_off_all()
        else:
            await self._async_control_heating()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._attr_preset_mode = PRESET_NONE
        self._pid.reset()
        current = self._attr_target_temperature or temp
        if self._temp_ramp and abs(temp - current) > self._temp_ramp_step:
            await self._async_start_ramp(temp)
        else:
            self._attr_target_temperature = temp
        # Stuur nieuwe doeltemperatuur direct door naar actieve climate-entiteiten
        if self._heater_on and self._heater_entity_id:
            await self._async_update_primary_temperature(self._heater_entity_id)
        if self._cooler_on and self._cooler_entity_id:
            await self._async_update_primary_temperature(self._cooler_entity_id)
        await self._async_control_heating()
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in (self._attr_preset_modes or []):
            return
        self._attr_preset_mode = preset_mode

        if preset_mode == PRESET_BOOST:
            await self.async_activate_boost(
                duration=self._boost_duration,
                target=self._preset_temps.get(PRESET_BOOST, DEFAULT_PRESET_BOOST),
            )
            return

        new_temp: float | None = None
        if preset_mode == PRESET_SCHEDULE:
            active = self._schedule.get_active_preset()
            if active and active in self._preset_temps:
                new_temp = self._preset_temps[active]
        elif preset_mode != PRESET_NONE:
            new_temp = self._preset_temps.get(preset_mode)

        self._boost_end = None
        self._pid.reset()

        if new_temp is not None:
            current = self._attr_target_temperature or new_temp
            if self._temp_ramp and abs(new_temp - current) > self._temp_ramp_step:
                await self._async_start_ramp(new_temp)
            else:
                self._attr_target_temperature = new_temp

        await self._async_control_heating()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Boost mode
    # ------------------------------------------------------------------

    async def async_activate_boost(
        self, duration: int | None = None, target: float | None = None
    ) -> None:
        """Activate boost mode for `duration` minutes at `target` temp."""
        dur = duration or self._boost_duration
        tgt = target or self._preset_temps.get(PRESET_BOOST, DEFAULT_PRESET_BOOST)
        self._prev_preset = self._attr_preset_mode
        self._attr_preset_mode = PRESET_BOOST
        self._attr_target_temperature = tgt
        self._boost_end = dt_util.utcnow() + timedelta(minutes=dur)
        self._pid.reset()
        await self._async_control_heating()
        self.async_write_ha_state()

    async def async_clear_boost(self) -> None:
        """Cancel boost and restore previous preset."""
        self._boost_end = None
        self._attr_preset_mode = self._prev_preset or PRESET_NONE
        if self._attr_preset_mode in self._preset_temps:
            self._attr_target_temperature = self._preset_temps[self._attr_preset_mode]
        self._pid.reset()
        await self._async_control_heating()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Vacation mode
    # ------------------------------------------------------------------

    async def async_set_vacation(
        self, start_date: date, end_date: date, temperature: float
    ) -> None:
        """Activate vacation mode between two dates."""
        self._vacation_start = start_date
        self._vacation_end = end_date
        self._vacation_temp = temperature
        await self._async_control_heating()
        self.async_write_ha_state()

    async def async_clear_vacation(self) -> None:
        self._vacation_start = None
        self._vacation_end = None
        await self._async_control_heating()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Hold-modus
    # ------------------------------------------------------------------

    async def async_set_hold(self, temperature: float, duration_h: float = 2.0) -> None:
        """Houd temperatuur vast voor `duration_h` uur, dan schema hervatten."""
        self._hold_temp = temperature
        self._hold_end = dt_util.utcnow() + timedelta(hours=duration_h)
        _LOGGER.info("[%s] Hold: %.1f°C voor %.1f uur", self.name, temperature, duration_h)
        await self._async_control_heating()
        self.async_write_ha_state()

    async def async_clear_hold(self) -> None:
        """Annuleer hold-modus."""
        self._hold_temp = None
        self._hold_end = None
        await self._async_control_heating()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Schedule management
    # ------------------------------------------------------------------

    async def async_set_schedule(self, entries: list[dict]) -> None:
        self._schedule.set_entries(entries)
        # Persist in options
        options = dict(self._config_entry.options)
        options[CONF_SCHEDULE] = entries
        self.hass.config_entries.async_update_entry(self._config_entry, options=options)
        await self._async_control_heating()
        self.async_write_ha_state()

    async def async_clear_schedule(self) -> None:
        self._schedule.clear()
        options = dict(self._config_entry.options)
        options[CONF_SCHEDULE] = []
        self.hass.config_entries.async_update_entry(self._config_entry, options=options)
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Event callbacks
    # ------------------------------------------------------------------

    @callback
    def _async_sensor_changed(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        if new_state.entity_id == self._sensor_entity_id:
            self._update_temp(new_state)
        elif new_state.entity_id == self._outside_sensor_entity_id:
            self._update_outside_temp(new_state)
        self.hass.async_create_task(self._async_control_heating())
        self.async_write_ha_state()

    @callback
    def _async_switch_changed(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        if new_state.entity_id == self._heater_entity_id:
            is_on = new_state.state == STATE_ON
            if is_on and not self._heater_on:
                self._heater_on_since = dt_util.utcnow()
            elif not is_on and self._heater_on and self._heater_on_since:
                self._heater_runtime_today += (
                    dt_util.utcnow() - self._heater_on_since
                ).total_seconds() / 60
                self._heater_on_since = None
            self._heater_on = is_on
        elif new_state.entity_id == self._cooler_entity_id:
            is_on = new_state.state == STATE_ON
            if is_on and not self._cooler_on:
                self._cooler_on_since = dt_util.utcnow()
            elif not is_on and self._cooler_on and self._cooler_on_since:
                self._cooler_runtime_today += (
                    dt_util.utcnow() - self._cooler_on_since
                ).total_seconds() / 60
                self._cooler_on_since = None
            self._cooler_on = is_on
        self.async_write_ha_state()

    @callback
    def _async_presence_changed(self, event) -> None:
        self._update_presence()
        self.hass.async_create_task(self._async_presence_response())

    @callback
    def _async_schedule_tick(self, now: datetime) -> None:
        """Called every minute — handle schedule changes and early start."""
        if self._attr_preset_mode != PRESET_SCHEDULE:
            return

        # 1. Check if current schedule slot changed
        active = self._schedule.get_active_preset(now)
        if active and active in self._preset_temps:
            new_temp = self._preset_temps[active]
            if new_temp != self._attr_target_temperature and not self._early_start_active:
                self._attr_target_temperature = new_temp
                self._pid.reset()
                self.hass.async_create_task(self._async_control_heating())
                self.async_write_ha_state()

        # 2. Early start — look ahead and begin heating before schedule change
        if self._early_start and self._learning_enabled:
            self._check_early_start(now)

    @callback
    def _async_midnight_reset(self, _now: datetime) -> None:
        """Reset daily runtime counters at midnight."""
        self._heater_runtime_today = 0.0
        self._cooler_runtime_today = 0.0
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _update_temp(self, state) -> None:
        try:
            temp = float(state.state)
            self._attr_current_temperature = temp
            self._last_sensor_update = dt_util.utcnow()
            self._temp_history.append((dt_util.utcnow(), temp))
            if self._window_detection:
                self._check_window_open()
        except (ValueError, TypeError):
            _LOGGER.warning("Cannot parse temperature: %s", state.state)

    def _update_outside_temp(self, state) -> None:
        try:
            self._outside_temp = float(state.state)
            self._update_weather_compensation()
        except (ValueError, TypeError):
            pass

    def _update_weather_compensation(self) -> None:
        if not self._weather_compensation or self._outside_temp is None:
            self._weather_adj = 0.0
            return
        delta = self._weather_outside_ref - self._outside_temp
        self._weather_adj = round(self._weather_slope * delta, 2)

    def _update_humidity(self, state) -> None:
        try:
            self._current_humidity = float(state.state)
            if self._humidity_sensor:
                # Hoge vochtigheid = voelt warmer → doel verlagen
                deviation = self._current_humidity - self._humidity_ref
                self._humidity_adj = round(deviation * self._humidity_factor, 2)
        except (ValueError, TypeError):
            pass

    def _update_energy_price(self, state) -> None:
        try:
            self._current_energy_price = float(state.state)
            self._price_setback_active = (
                self._current_energy_price >= self._energy_price_threshold
            )
            if self._price_setback_active:
                _LOGGER.info(
                    "[%s] Energieprijs %.3f ≥ %.3f → setback %.1f°C actief",
                    self.name, self._current_energy_price,
                    self._energy_price_threshold, self._energy_price_setback,
                )
        except (ValueError, TypeError):
            pass

    def _update_vacation_calendar(self, state) -> None:
        """Sync vakantiestand met HA calendar entiteit."""
        if state.state == STATE_ON:
            # Kalender-event actief → vakantietemperatuur
            if not self._vacation_start:
                self._vacation_temp = self._preset_temps.get(PRESET_AWAY, self._vacation_temp)
                self._vacation_start = dt_util.now().date()
                self._vacation_end = dt_util.now().date()  # dagelijks vernieuwd
                _LOGGER.info("[%s] Vakantiekalender: vakantiestand actief", self.name)
                self.hass.async_create_task(self._async_control_heating())
        else:
            # Geen actief event → vakantie beëindigen
            if self._vacation_start:
                self._vacation_start = None
                self._vacation_end = None
                _LOGGER.info("[%s] Vakantiekalender: vakantiestand beëindigd", self.name)
                self.hass.async_create_task(self._async_control_heating())

    def _update_forecast_cool_block(self, state) -> None:
        """Lees weather forecast en bepaal of koelen geblokkeerd moet worden."""
        if self._forecast_cool_block_threshold is None or state is None:
            self._forecast_cool_blocked = False
            self._forecast_min_temp = None
            return
        forecast = state.attributes.get("forecast", [])
        if not forecast:
            self._forecast_cool_blocked = False
            self._forecast_min_temp = None
            return
        now = dt_util.utcnow()
        cutoff = now + timedelta(hours=self._forecast_cool_block_hours)
        temps = []
        for entry in forecast:
            try:
                dt_str = entry.get("datetime")
                temp = entry.get("temperature")
                if dt_str is None or temp is None:
                    continue
                entry_dt = dt_util.parse_datetime(dt_str)
                if entry_dt and now <= entry_dt <= cutoff:
                    temps.append(float(temp))
            except (ValueError, TypeError):
                continue
        if not temps:
            self._forecast_cool_blocked = False
            self._forecast_min_temp = None
            return
        self._forecast_min_temp = min(temps)
        self._forecast_cool_blocked = self._forecast_min_temp < self._forecast_cool_block_threshold

    @callback
    def _async_weather_changed(self, event) -> None:
        """Verwerk een statuswijziging van de weather entiteit."""
        new_state = event.data.get("new_state")
        self._update_forecast_cool_block(new_state)
        self.async_write_ha_state()

    def _update_presence(self) -> None:
        if not self._presence_sensors:
            self._presence_detected = True
            return
        for entity_id in self._presence_sensors:
            state = self.hass.states.get(entity_id)
            if state and state.state in (STATE_HOME, STATE_ON, "true", "True"):
                self._presence_detected = True
                return
        self._presence_detected = False

    # ------------------------------------------------------------------
    # Window detection
    # ------------------------------------------------------------------

    def _check_window_open(self) -> None:
        """Detect rapid temperature drop indicating an open window."""
        # Skip temperature-drop detection if a binary_sensor handles this directly
        if self._window_sensor:
            return
        if len(self._temp_history) < 2:
            return

        cutoff = dt_util.utcnow() - timedelta(minutes=self._window_temp_drop_time)
        recent = [(t, v) for t, v in self._temp_history if t >= cutoff]
        if len(recent) < 2:
            return

        drop = recent[0][1] - recent[-1][1]  # positive = cooling down

        if not self._window_open and drop >= self._window_temp_drop:
            self._window_open = True
            self._window_open_since = dt_util.utcnow()
            _LOGGER.info("[%s] Window OPEN detected (drop %.2f °C)", self.name, drop)
            self.hass.async_create_task(self._async_window_suspend())
        elif self._window_open and self._window_open_since:
            elapsed = (dt_util.utcnow() - self._window_open_since).total_seconds() / 60
            if elapsed >= self._window_open_duration or drop < 0.1:
                self._window_open = False
                self._window_open_since = None
                _LOGGER.info("[%s] Window CLOSED (resumed control)", self.name)

    async def _async_window_suspend(self) -> None:
        """Turn off heating/cooling while window is open."""
        if self._window_open:
            await self._async_turn_off_all()

    @callback
    def _async_humidity_changed(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        self._update_humidity(new_state)
        self.async_write_ha_state()

    @callback
    def _async_price_changed(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        was_active = self._price_setback_active
        self._update_energy_price(new_state)
        if self._price_setback_active != was_active:
            self.hass.async_create_task(self._async_control_heating())
        self.async_write_ha_state()

    @callback
    def _async_calendar_changed(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self._update_vacation_calendar(new_state)
        self.async_write_ha_state()

    @callback
    def _async_window_sensor_changed(self, event) -> None:
        """Handle state change of the window binary_sensor."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        is_open = new_state.state == STATE_ON
        if is_open and not self._window_open:
            self._window_open = True
            self._window_open_since = dt_util.utcnow()
            _LOGGER.info("[%s] Window OPEN (sensor)", self.name)
            self.hass.async_create_task(self._async_window_suspend())
        elif not is_open and self._window_open:
            self._window_open = False
            self._window_open_since = None
            _LOGGER.info("[%s] Window CLOSED (sensor) — resumed control", self.name)
            self.hass.async_create_task(self._async_control_heating())
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Temperature ramp (Feature 5)
    # ------------------------------------------------------------------

    def _async_cancel_ramp(self) -> None:
        """Annuleer een lopende ramp."""
        if self._ramp_cancel is not None:
            self._ramp_cancel()
            self._ramp_cancel = None
        self._ramp_target = None

    async def _async_start_ramp(self, final_target: float) -> None:
        """Start geleidelijke overgang naar final_target met stappen van ramp_step."""
        self._async_cancel_ramp()
        current = self._attr_target_temperature or final_target
        if abs(final_target - current) <= self._temp_ramp_step:
            # Klein verschil — direct instellen
            self._attr_target_temperature = final_target
            return
        self._ramp_target = final_target
        # Zet eerste stap
        direction = 1 if final_target > current else -1
        self._attr_target_temperature = round(current + direction * self._temp_ramp_step, 1)
        self._ramp_cancel = async_track_time_interval(
            self.hass,
            self._async_ramp_step,
            timedelta(minutes=self._temp_ramp_interval),
        )

    @callback
    def _async_ramp_step(self, _now=None) -> None:
        """Elke ramp-interval: één stap richting ramp_target."""
        if self._ramp_target is None:
            self._async_cancel_ramp()
            return
        current = self._attr_target_temperature or self._ramp_target
        remaining = self._ramp_target - current
        if abs(remaining) <= self._temp_ramp_step:
            # Doel bereikt
            self._attr_target_temperature = self._ramp_target
            self._async_cancel_ramp()
        else:
            direction = 1 if remaining > 0 else -1
            self._attr_target_temperature = round(current + direction * self._temp_ramp_step, 1)
        self.async_write_ha_state()
        self.hass.async_create_task(self._async_control_heating())

    # ------------------------------------------------------------------
    # Presence response
    # ------------------------------------------------------------------

    async def _async_presence_response(self) -> None:
        """Switch to Away preset when everyone leaves, restore when returning."""
        if self._hvac_mode == HVACMode.OFF:
            return
        if not self._presence_detected and self._attr_preset_mode != PRESET_AWAY:
            self._prev_preset = self._attr_preset_mode
            await self.async_set_preset_mode(PRESET_AWAY)
        elif self._presence_detected and self._attr_preset_mode == PRESET_AWAY:
            restore = self._prev_preset if self._prev_preset != PRESET_AWAY else PRESET_COMFORT
            await self.async_set_preset_mode(restore)

    # ------------------------------------------------------------------
    # Self-learning & early start
    # ------------------------------------------------------------------

    def _check_early_start(self, now: datetime) -> None:
        """Tado-style Early Start: begin heating before scheduled time.

        Looks ahead in the schedule and calculates whether to start heating
        now so the room reaches the next preset temperature exactly on time,
        based on the learned heating rate.
        """
        if self._learned_heating_rate is None or self._learned_heating_rate <= 0:
            return
        if self._attr_current_temperature is None:
            return

        next_preset, next_dt = self._schedule.get_next_change(now)
        if next_preset is None or next_dt is None:
            return
        if next_preset not in self._preset_temps:
            return

        next_temp = self._preset_temps[next_preset]
        current = self._attr_current_temperature
        temp_diff = next_temp - current

        if temp_diff <= 0:
            # Already warm enough for next slot — cancel any active early start
            if self._early_start_active:
                self._early_start_active = False
                self._early_start_target_preset = None
            return

        # Minutes needed to reach next_temp at learned rate
        needed_minutes = temp_diff / self._learned_heating_rate
        # Add 10 % safety margin
        needed_minutes *= 1.1

        minutes_until_change = (next_dt - now).total_seconds() / 60.0

        if minutes_until_change <= needed_minutes and not self._early_start_active:
            _LOGGER.info(
                "[%s] Early Start: need %.1f min to reach %.1f°C, change in %.1f min → starting now",
                self._attr_name, needed_minutes, next_temp, minutes_until_change,
            )
            self._early_start_active = True
            self._early_start_target_preset = next_preset
            self._attr_target_temperature = next_temp
            self.hass.async_create_task(self._async_control_heating())
            self.async_write_ha_state()
        elif self._early_start_active and self._early_start_target_preset == next_preset:
            # Already in early start for this slot — check if we arrived
            if current >= next_temp - self._cold_tolerance:
                _LOGGER.info("[%s] Early Start: target reached, maintaining", self._attr_name)
                self._early_start_active = False

    def _record_heating_session(self) -> None:
        """Called when heater turns off — learn from the completed session."""
        if not self._learning_enabled:
            return
        if self._session_start_temp is None or self._session_start_time is None:
            return
        if self._attr_current_temperature is None:
            return

        duration_min = (dt_util.utcnow() - self._session_start_time).total_seconds() / 60.0
        if duration_min < 2.0:
            # Too short to be meaningful
            self._session_start_temp = None
            self._session_start_time = None
            return

        temp_rise = self._attr_current_temperature - self._session_start_temp
        if temp_rise <= 0:
            self._session_start_temp = None
            self._session_start_time = None
            return

        measured_rate = temp_rise / duration_min

        # Update EMA: α=0.3 means new observations have 30 % weight
        if self._learned_heating_rate is None:
            self._learned_heating_rate = measured_rate
        else:
            self._learned_heating_rate = (
                EMA_ALPHA * measured_rate + (1 - EMA_ALPHA) * self._learned_heating_rate
            )

        _LOGGER.info(
            "[%s] Session learned: +%.2f°C in %.1f min → rate %.4f°C/min (EMA: %.4f)",
            self._attr_name, temp_rise, duration_min, measured_rate, self._learned_heating_rate,
        )

        # Persist
        if self._storage:
            self._storage.heating_rate = self._learned_heating_rate
            self._storage.add_heating_session({
                "start_temp": self._session_start_temp,
                "end_temp": self._attr_current_temperature,
                "duration_min": round(duration_min, 2),
                "rate_c_per_min": round(measured_rate, 5),
                "timestamp": dt_util.utcnow().isoformat(),
            })
            self.hass.async_create_task(self._storage.async_save())

        # Also save PID integral to survive restart
        if self._storage:
            self._storage.pid_integral = self._pid.integral
            self.hass.async_create_task(self._storage.async_save())

        self._session_start_temp = None
        self._session_start_time = None

    # ------------------------------------------------------------------
    # Multi-split groepscoördinatie
    # ------------------------------------------------------------------

    def _update_multisplit_mode(self) -> str | None:
        """Bepaal en sla de groepsmodus op. Retourneert 'heat', 'cool' of None."""
        heat_score = 0.0
        cool_score = 0.0
        max_heat_dev = 0.0
        max_cool_dev = 0.0

        for entry_data in self.hass.data.get(DOMAIN, {}).values():
            if not isinstance(entry_data, dict):
                continue
            entity = entry_data.get("entity")
            if entity is None or getattr(entity, "_multisplit_group", None) != self._multisplit_group:
                continue
            current = entity._attr_current_temperature
            if current is None:
                continue
            try:
                target = entity.effective_target_temperature
            except Exception:
                continue
            deviation = current - target
            if deviation > 0.5:                      # te warm → wil koelen
                cool_score += deviation
                max_cool_dev = max(max_cool_dev, deviation)
            elif deviation < -0.5:                   # te koud → wil verwarmen
                heat_score += abs(deviation)
                max_heat_dev = max(max_heat_dev, abs(deviation))

        groups = self.hass.data[DOMAIN].setdefault("_groups", {})
        group = groups.setdefault(self._multisplit_group, {"mode": None})
        old_mode = group["mode"]

        # Prioriteitsoverschrijving
        if max_heat_dev >= self._multisplit_priority_temp or max_cool_dev >= self._multisplit_priority_temp:
            new_mode = "heat" if max_heat_dev >= max_cool_dev else "cool"
        # Gewogen meerderheid
        elif heat_score > cool_score + self._multisplit_switch_margin:
            new_mode = "heat"
        elif cool_score > heat_score + self._multisplit_switch_margin:
            new_mode = "cool"
        else:
            new_mode = old_mode  # Gelijke stand → huidige modus handhaven

        group["mode"] = new_mode
        return new_mode

    # ------------------------------------------------------------------
    # Core control loop
    # ------------------------------------------------------------------

    async def _async_control_heating(self, _now=None) -> None:
        # Sensorfailsafe: als sensor te lang stil is, alles uitzetten
        if self._sensor_timeout_min is not None and self._last_sensor_update is not None:
            age_min = (dt_util.utcnow() - self._last_sensor_update).total_seconds() / 60
            if age_min > self._sensor_timeout_min:
                _LOGGER.warning(
                    "[%s] Sensorfailsafe: geen update in %.0f min → alles uit",
                    self.name, age_min,
                )
                await self._async_turn_off_all()
                return

        # Vorstbeveiliging: verwarmen als temp onder vorstgrens, ook bij HVAC OFF
        if self._frost_protection_temp is not None and self._attr_current_temperature is not None:
            if self._attr_current_temperature < self._frost_protection_temp:
                if not self._frost_active:
                    _LOGGER.info(
                        "[%s] Vorstbeveiliging actief: %.1f°C < %.1f°C",
                        self.name, self._attr_current_temperature, self._frost_protection_temp,
                    )
                    self._frost_active = True
                if self._heater_entity_id and not self._heater_on:
                    await self._async_turn_on_heater()
                elif self._cascade_primary_heater and not self._cascade_primary_heat_on:
                    await self._async_switch_primary(self._cascade_primary_heater, True, "heat")
                    self._cascade_primary_heat_on = True
                self.async_write_ha_state()
                return
            elif self._frost_active:
                _LOGGER.info("[%s] Vorstbeveiliging uit: temp hersteld", self.name)
                self._frost_active = False
                await self._async_turn_off_all()

        if self._hvac_mode == HVACMode.OFF:
            return
        if self._window_open:
            return  # suspended

        # Check boost expiry
        if self._boost_end and dt_util.utcnow() > self._boost_end:
            await self.async_clear_boost()
            return

        # Check hold expiry
        if self._hold_end and dt_util.utcnow() > self._hold_end:
            self._hold_temp = None
            self._hold_end = None
            _LOGGER.info("[%s] Hold-modus verlopen", self.name)
            self.async_write_ha_state()

        # Seizoensdetectie: auto-switch HEAT/COOL op basis van buitentemperatuur
        if self._auto_mode and self._outside_temp is not None:
            if (self._outside_temp >= self._auto_mode_cool_threshold
                    and self._hvac_mode == HVACMode.HEAT):
                _LOGGER.info(
                    "[%s] Seizoensdetectie: buiten %.1f°C ≥ %.1f°C → switch naar COOL",
                    self.name, self._outside_temp, self._auto_mode_cool_threshold,
                )
                self._hvac_mode = HVACMode.COOL
                self.async_write_ha_state()
            elif (self._outside_temp <= self._auto_mode_heat_threshold
                    and self._hvac_mode == HVACMode.COOL):
                _LOGGER.info(
                    "[%s] Seizoensdetectie: buiten %.1f°C ≤ %.1f°C → switch naar HEAT",
                    self.name, self._outside_temp, self._auto_mode_heat_threshold,
                )
                self._hvac_mode = HVACMode.HEAT
                self.async_write_ha_state()

        # Check vacation mode
        if self._vacation_start and self._vacation_end:
            today = dt_util.now().date()
            if self._vacation_start <= today <= self._vacation_end:
                self._attr_target_temperature = self._vacation_temp
            else:
                # Vacation ended — clear
                if today > self._vacation_end:
                    self._vacation_start = None
                    self._vacation_end = None

        if self._attr_current_temperature is None or self._attr_target_temperature is None:
            return

        current = self._attr_current_temperature
        target = self.effective_target_temperature

        # Feature 3: blokkeer koeling als buiten al koud genoeg is
        if self._cool_block_outside_temp is not None:
            outside = self._outside_temp
            if outside is not None and outside <= self._cool_block_outside_temp:
                wants_cool_now = self._hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL)
                if wants_cool_now:
                    if self._cooler_on or self._cascade_primary_cool_on:
                        _LOGGER.info(
                            "[%s] Koeling geblokkeerd: buiten %.1f°C ≤ %.1f°C drempel",
                            self.name, outside, self._cool_block_outside_temp,
                        )
                        if self._cooler_on:
                            await self._async_turn_off_cooler()
                        if self._cascade_primary_cool_on and self._cascade_primary_cooler:
                            await self._async_switch_primary(self._cascade_primary_cooler, False, "cool")
                            self._cascade_primary_cool_on = False
                            self._cascade_primary_start_time = None
                    return

        # Voorspellende koelblokkering op basis van weersverwachting
        if self._forecast_cool_blocked:
            wants_cool_now = self._hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL)
            if wants_cool_now:
                if self._cooler_on or self._cascade_primary_cool_on:
                    _LOGGER.info(
                        "[%s] Koeling geblokkeerd: verwachte min %.1f°C < drempel %.1f°C in komende %dh",
                        self.name,
                        self._forecast_min_temp if self._forecast_min_temp is not None else 0.0,
                        self._forecast_cool_block_threshold,
                        self._forecast_cool_block_hours,
                    )
                    if self._cooler_on:
                        await self._async_turn_off_cooler()
                    if self._cascade_primary_cool_on and self._cascade_primary_cooler:
                        await self._async_switch_primary(self._cascade_primary_cooler, False, "cool")
                        self._cascade_primary_cool_on = False
                return

        # Multi-split groepscoördinatie
        if self._multisplit_group:
            group_mode = self._update_multisplit_mode()
            self._multisplit_allowed_mode = group_mode
            # Zet actuatoren uit die de verkeerde richting op zijn
            if group_mode == "heat":
                if self._cooler_on:
                    await self._async_turn_off_cooler()
                if self._cascade_primary_cool_on and self._cascade_primary_cooler:
                    await self._async_switch_primary(self._cascade_primary_cooler, False, "cool")
                    self._cascade_primary_cool_on = False
            elif group_mode == "cool":
                if self._heater_on:
                    await self._async_turn_off_heater()
                if self._cascade_primary_heat_on and self._cascade_primary_heater:
                    await self._async_switch_primary(self._cascade_primary_heater, False, "heat")
                    self._cascade_primary_heat_on = False
        else:
            self._multisplit_allowed_mode = None

        if self._cascade_enabled and (
            self._cascade_primary_heater or self._cascade_primary_cooler
        ):
            await self._control_cascade(current, target)
        elif self._algorithm == ALGORITHM_HYSTERESIS:
            await self._control_hysteresis(current, target)
        elif self._algorithm == ALGORITHM_PID:
            await self._control_pid(current, target)
        elif self._algorithm == ALGORITHM_PREDICTIVE:
            await self._control_predictive(current, target)

        # Sync doeltemperatuur naar actieve climate-entiteiten NA het algoritme.
        # Zo wordt set_temperature alleen gestuurd als de actuator nog aan is — niet
        # vlak voor een OFF-opdracht, wat sommige integraties (Daikin, Tuya, …) ertoe
        # brengt de entity te heractiveren waarna de OFF niet goed landt.
        if self._heater_on and self._heater_entity_id:
            await self._async_update_primary_temperature(self._heater_entity_id)
        if self._cooler_on and self._cooler_entity_id:
            await self._async_update_primary_temperature(self._cooler_entity_id)

        # Feature 7: persistent notification als ruimte doel niet haalt
        if self._notify_on_delay:
            active = self._heater_on or self._cooler_on or self._cascade_primary_heat_on or self._cascade_primary_cool_on
            at_target = not (current < (target - self._cold_tolerance) or current > (target + self._hot_tolerance))
            if active and not at_target:
                if self._heat_cool_start_time is None:
                    self._heat_cool_start_time = dt_util.utcnow()
                elif not self._notify_sent:
                    elapsed_min = (dt_util.utcnow() - self._heat_cool_start_time).total_seconds() / 60
                    if elapsed_min >= self._notify_delay_min:
                        await self._async_send_delay_notification()
                        self._notify_sent = True
            elif at_target and self._notify_sent:
                await self._async_dismiss_notification()
                self._notify_sent = False
                self._heat_cool_start_time = None

    # ------------------------------------------------------------------
    # Cascade besturing
    # ------------------------------------------------------------------

    async def _control_cascade(self, current: float, target: float) -> None:
        """Cascade: primaire bron (airco) eerst, secundaire (vloerverwarming) als back-up.

        Verwarmingsstrategie:
          1. Te koud  → zet primaire verwarming aan
          2. Primaire al X min aan maar temp nog Y°C te laag → secundaire erbij
          3. Doel bereikt → secundaire eerst uit (na vertraging), dan primaire

        Koelstrategie: zelfde logica omgekeerd.
        """
        wants_heat = self._hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL)
        wants_cool = self._hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL)
        if self._multisplit_allowed_mode == "cool":
            wants_heat = False
        elif self._multisplit_allowed_mode == "heat":
            wants_cool = False

        too_cold = current < (target - self._cold_tolerance)
        too_hot  = current > (target + self._hot_tolerance)
        at_target = not too_cold and not too_hot

        now = dt_util.utcnow()

        # ---- Verwarming ----
        if wants_heat and self._cascade_primary_heater:
            if too_cold:
                # Stap 1: primaire aan
                if not self._cascade_primary_heat_on:
                    await self._async_switch_primary(self._cascade_primary_heater, True, "heat")
                    self._cascade_primary_heat_on = True
                    self._cascade_primary_start_time = now
                    self._cascade_reason = "primaire verwarming actief"
                    _LOGGER.info("[%s] Cascade HEAT: primaire (airco) aan", self.name)
                else:
                    # Primaire al aan — stuur bijgewerkte doeltemperatuur door
                    await self._async_update_primary_temperature(self._cascade_primary_heater)

                # Stap 2: secundaire nodig?
                if self._cascade_primary_heat_on and self._cascade_primary_start_time:
                    elapsed = (now - self._cascade_primary_start_time).total_seconds() / 60
                    shortfall = target - current
                    instant = (
                        self._cascade_instant_threshold is not None
                        and shortfall > self._cascade_instant_threshold
                    )
                    if ((instant or (elapsed >= self._cascade_timeout_min and shortfall > self._cascade_temp_threshold))
                            and not self._cascade_secondary_active):
                        if self._heater_entity_id:
                            await self._async_turn_on_heater()
                            self._cascade_secondary_active = True
                            self._cascade_secondary_start_time = now
                            self._cascade_reason = (
                                f"secundaire aan na {elapsed:.0f} min, "
                                f"nog {shortfall:.1f}°C tekort"
                            )
                            _LOGGER.info(
                                "[%s] Cascade HEAT: primaire onvoldoende na %.0f min "
                                "(tekort %.1f°C) → secundaire (vloer) aan",
                                self.name, elapsed, shortfall,
                            )
                        else:
                            self._cascade_reason = (
                                f"primaire onvoldoende na {elapsed:.0f} min, "
                                "geen secundaire geconfigureerd"
                            )
                            _LOGGER.debug(
                                "[%s] Cascade HEAT: primaire onvoldoende maar geen "
                                "secundaire geconfigureerd — primary-only modus",
                                self.name,
                            )

            elif at_target or current >= target:
                # Stap 3: doel bereikt
                if self._cascade_secondary_active:
                    # Secundaire uit, na korte vertraging
                    if self._cascade_secondary_start_time:
                        sec_elapsed = (now - self._cascade_secondary_start_time).total_seconds() / 60
                        if sec_elapsed >= self._cascade_deactivate_delay_min:
                            await self._async_turn_off_heater()
                            self._cascade_secondary_active = False
                            self._cascade_secondary_start_time = None
                            self._cascade_reason = "doel bereikt, secundaire uit"
                            _LOGGER.info("[%s] Cascade HEAT: doel bereikt, secundaire uit", self.name)
                    else:
                        await self._async_turn_off_heater()
                        self._cascade_secondary_active = False

                # Primaire uit
                if not self._cascade_secondary_active and self._cascade_primary_heat_on:
                    await self._async_switch_primary(self._cascade_primary_heater, False, "heat")
                    self._cascade_primary_heat_on = False
                    self._cascade_primary_start_time = None
                    self._cascade_reason = "doel bereikt, primaire uit"
                    _LOGGER.info("[%s] Cascade HEAT: doel bereikt, primaire (airco) uit", self.name)

        # ---- Koeling ----
        if wants_cool and self._cascade_primary_cooler:
            if too_hot:
                if not self._cascade_primary_cool_on:
                    await self._async_switch_primary(self._cascade_primary_cooler, True, "cool")
                    self._cascade_primary_cool_on = True
                    self._cascade_primary_start_time = now
                    self._cascade_reason = "primaire koeling actief"
                    _LOGGER.info("[%s] Cascade COOL: primaire (airco) aan", self.name)
                else:
                    # Primaire al aan — stuur bijgewerkte doeltemperatuur door
                    await self._async_update_primary_temperature(self._cascade_primary_cooler)

                if self._cascade_primary_cool_on and self._cascade_primary_start_time:
                    elapsed = (now - self._cascade_primary_start_time).total_seconds() / 60
                    shortfall = current - target
                    instant = (
                        self._cascade_instant_threshold is not None
                        and shortfall > self._cascade_instant_threshold
                    )
                    if ((instant or (elapsed >= self._cascade_timeout_min and shortfall > self._cascade_temp_threshold))
                            and not self._cascade_secondary_active):
                        if self._cooler_entity_id:
                            await self._async_turn_on_cooler()
                            self._cascade_secondary_active = True
                            self._cascade_secondary_start_time = now
                            self._cascade_reason = (
                                f"secundaire koeling aan na {elapsed:.0f} min, "
                                f"nog {shortfall:.1f}°C te warm"
                            )
                            _LOGGER.info(
                                "[%s] Cascade COOL: primaire onvoldoende na %.0f min → secundaire aan",
                                self.name, elapsed,
                            )
                        else:
                            self._cascade_reason = (
                                f"primaire onvoldoende na {elapsed:.0f} min, "
                                "geen secundaire geconfigureerd"
                            )
                            _LOGGER.debug(
                                "[%s] Cascade COOL: primaire onvoldoende maar geen "
                                "secundaire geconfigureerd — primary-only modus",
                                self.name,
                            )

            elif at_target or current <= target:
                if self._cascade_secondary_active:
                    if self._cascade_secondary_start_time:
                        sec_elapsed = (now - self._cascade_secondary_start_time).total_seconds() / 60
                        if sec_elapsed >= self._cascade_deactivate_delay_min:
                            await self._async_turn_off_cooler()
                            self._cascade_secondary_active = False
                            self._cascade_secondary_start_time = None
                    else:
                        await self._async_turn_off_cooler()
                        self._cascade_secondary_active = False

                if not self._cascade_secondary_active and self._cascade_primary_cool_on:
                    await self._async_switch_primary(self._cascade_primary_cooler, False, "cool")
                    self._cascade_primary_cool_on = False
                    self._cascade_primary_start_time = None
                    self._cascade_reason = "doel bereikt, primaire koeling uit"

    async def _async_update_primary_temperature(self, entity_id: str) -> None:
        """Stuur de huidige doeltemperatuur naar de primaire entiteit (airco) als die al aan is."""
        domain = entity_id.split(".")[0]
        if domain == "climate" and self._attr_target_temperature:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": entity_id,
                    "temperature": self.effective_target_temperature,
                },
                blocking=True,
            )

    async def _async_switch_primary(
        self, entity_id: str, turn_on: bool, mode: str
    ) -> None:
        """Schakel de primaire entiteit (airco) in/uit.

        Ondersteunt climate-entiteiten (hvac_mode) en switch-entiteiten.
        """
        domain = entity_id.split(".")[0]
        if domain == "climate":
            if turn_on:
                if mode == "cool":
                    state = self.hass.states.get(entity_id)
                    supported = state.attributes.get("hvac_modes", []) if state else []
                    if HVACMode.COOL in supported:
                        hvac = HVACMode.COOL
                    elif HVACMode.HEAT_COOL in supported:
                        hvac = HVACMode.HEAT_COOL
                    elif HVACMode.AUTO in supported:
                        hvac = HVACMode.AUTO
                    else:
                        hvac = HVACMode.COOL
                else:
                    hvac = HVACMode.HEAT
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": entity_id, "hvac_mode": hvac},
                    blocking=True,
                )
                # Stel ook de doeltemperatuur in op de airco
                if self._attr_target_temperature:
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {
                            "entity_id": entity_id,
                            "temperature": self.effective_target_temperature,
                        },
                        blocking=True,
                    )
            else:
                idle_hvac = HVACMode.FAN_ONLY if self._ac_idle_mode == AC_IDLE_FAN_ONLY else HVACMode.OFF
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": entity_id, "hvac_mode": idle_hvac},
                    blocking=True,
                )
        elif domain in ("switch", "input_boolean"):
            service = "turn_on" if turn_on else "turn_off"
            await self.hass.services.async_call(
                domain, service, {"entity_id": entity_id}, blocking=True
            )

    # ------------------------------------------------------------------
    # Algorithm 1: Hysteresis
    # ------------------------------------------------------------------

    async def _control_hysteresis(self, current: float, target: float) -> None:
        wants_heat = self._hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL)
        wants_cool = self._hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL)
        if self._multisplit_allowed_mode == "cool":
            wants_heat = False
        elif self._multisplit_allowed_mode == "heat":
            wants_cool = False
        can_sw = self._can_switch()  # alleen bewaken bij aanzetten

        if wants_heat:
            if current < (target - self._cold_tolerance) and not self._heater_on:
                if can_sw:
                    await self._async_turn_on_heater()
            elif current >= target and self._heater_on:
                await self._async_turn_off_heater()      # altijd toegestaan

        if wants_cool:
            if current > (target + self._hot_tolerance) and not self._cooler_on:
                if can_sw:
                    await self._async_turn_on_cooler()
            elif current <= target and self._cooler_on:
                await self._async_turn_off_cooler()      # altijd toegestaan

    # ------------------------------------------------------------------
    # Algorithm 2: PID
    # ------------------------------------------------------------------

    async def _control_pid(self, current: float, target: float) -> None:
        self._pid_output = self._pid.compute(target, current)
        on_thresh, off_thresh = 60.0, 40.0
        wants_heat = self._hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL)
        wants_cool = self._hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL)
        if self._multisplit_allowed_mode == "cool":
            wants_heat = False
        elif self._multisplit_allowed_mode == "heat":
            wants_cool = False
        can_sw = self._can_switch()  # alleen bewaken bij aanzetten

        if wants_heat:
            if self._pid_output >= on_thresh and not self._heater_on:
                if can_sw:
                    await self._async_turn_on_heater()
            elif self._pid_output <= off_thresh and self._heater_on:
                await self._async_turn_off_heater()      # altijd toegestaan

        if wants_cool:
            cool_out = PID_OUTPUT_MAX - self._pid_output
            if cool_out >= on_thresh and not self._cooler_on:
                if can_sw:
                    await self._async_turn_on_cooler()
            elif cool_out <= off_thresh and self._cooler_on:
                await self._async_turn_off_cooler()      # altijd toegestaan

    # ------------------------------------------------------------------
    # Algorithm 3: Predictive
    # ------------------------------------------------------------------

    async def _control_predictive(self, current: float, target: float) -> None:
        if self._heater_on:
            self._hist_heat.add(current)
        elif self._cooler_on:
            self._hist_cool.add(current)
        else:
            self._hist_idle.add(current)

        wants_heat = self._hvac_mode in (HVACMode.HEAT, HVACMode.HEAT_COOL)
        wants_cool = self._hvac_mode in (HVACMode.COOL, HVACMode.HEAT_COOL)
        if self._multisplit_allowed_mode == "cool":
            wants_heat = False
        elif self._multisplit_allowed_mode == "heat":
            wants_cool = False
        # Geen vroege return op _can_switch() — uitzetten moet altijd kunnen

        if wants_heat:
            await self._predictive_heat(current, target)
        if wants_cool:
            await self._predictive_cool(current, target)

    async def _predictive_heat(self, current: float, target: float) -> None:
        eta_idle = self._hist_idle.minutes_to_reach(current, target)
        eta_heat = self._hist_heat.minutes_to_reach(current, target)
        if not self._heater_on:
            if current < (target - self._cold_tolerance):
                if self._can_switch():               # aanzetten bewaken
                    if eta_idle is None or eta_idle > 30:
                        await self._async_turn_on_heater()
        else:
            if current >= target:
                await self._async_turn_off_heater()  # altijd toegestaan
            elif eta_heat is not None and eta_heat <= 2.0:
                await self._async_turn_off_heater()  # altijd toegestaan

    async def _predictive_cool(self, current: float, target: float) -> None:
        eta_idle = self._hist_idle.minutes_to_reach(current, target)
        eta_cool = self._hist_cool.minutes_to_reach(current, target)
        if not self._cooler_on:
            if current > (target + self._hot_tolerance):
                if self._can_switch():               # aanzetten bewaken
                    if eta_idle is None or eta_idle > 30:
                        await self._async_turn_on_cooler()
        else:
            if current <= target:
                await self._async_turn_off_cooler()  # altijd toegestaan
            elif eta_cool is not None and eta_cool <= 2.0:
                await self._async_turn_off_cooler()  # altijd toegestaan

    # ------------------------------------------------------------------
    # Actuator helpers
    # ------------------------------------------------------------------

    def _can_switch(self) -> bool:
        if self._last_switch_time is None:
            return True
        return (
            dt_util.utcnow() - self._last_switch_time
        ).total_seconds() >= self._min_cycle_duration.total_seconds()

    async def _async_turn_on_heater(self) -> None:
        if not self._heater_entity_id:
            return
        await self._async_switch(self._heater_entity_id, True, "heat")
        if not self._heater_on:
            self._heater_on_since = dt_util.utcnow()
            # Start session tracking for self-learning
            if self._learning_enabled and self._attr_current_temperature is not None:
                self._session_start_temp = self._attr_current_temperature
                self._session_start_time = dt_util.utcnow()
        self._heater_on = True
        self._last_switch_time = dt_util.utcnow()
        _LOGGER.debug("[%s] Heater ON (session_start=%.1f°C)", self.name, self._session_start_temp or 0)

    async def _async_turn_off_heater(self) -> None:
        if not self._heater_entity_id:
            return
        await self._async_switch(self._heater_entity_id, False, "heat")
        if self._heater_on and self._heater_on_since:
            self._heater_runtime_today += (
                dt_util.utcnow() - self._heater_on_since
            ).total_seconds() / 60
            self._heater_on_since = None
        self._heater_on = False
        self._last_switch_time = dt_util.utcnow()
        # Learn from completed session
        self._record_heating_session()
        _LOGGER.debug("[%s] Heater OFF", self.name)

    async def _async_turn_on_cooler(self) -> None:
        if not self._cooler_entity_id:
            return
        await self._async_switch(self._cooler_entity_id, True, "cool")
        if not self._cooler_on:
            self._cooler_on_since = dt_util.utcnow()
        self._cooler_on = True
        self._last_switch_time = dt_util.utcnow()
        _LOGGER.debug("[%s] Cooler ON", self.name)

    async def _async_turn_off_cooler(self) -> None:
        if not self._cooler_entity_id:
            return
        await self._async_switch(self._cooler_entity_id, False, "cool")
        if self._cooler_on and self._cooler_on_since:
            self._cooler_runtime_today += (
                dt_util.utcnow() - self._cooler_on_since
            ).total_seconds() / 60
            self._cooler_on_since = None
        self._cooler_on = False
        self._last_switch_time = dt_util.utcnow()
        _LOGGER.debug("[%s] Cooler OFF", self.name)

    async def _async_turn_off_all(self) -> None:
        await self._async_turn_off_heater()
        await self._async_turn_off_cooler()
        # Reset notification state
        self._notify_sent = False
        self._heat_cool_start_time = None

    # ------------------------------------------------------------------
    # Notification helpers (Feature 7)
    # ------------------------------------------------------------------

    async def _async_send_delay_notification(self) -> None:
        """Stuur een persistent notification (en optioneel mobiel) als het doel niet gehaald wordt."""
        title = f"Smart Climate — {self.name}"
        message = (
            f"De ruimte heeft na {self._notify_delay_min} minuten het "
            "ingestelde doel nog niet bereikt."
        )
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": NOTIFICATION_ID_PREFIX + (self._attr_unique_id or ""),
            },
        )
        if self._notify_service:
            domain, service = self._notify_service.split(".", 1)
            try:
                await self.hass.services.async_call(
                    domain, service, {"title": title, "message": message}
                )
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning("[%s] Mobiele notificatie mislukt: %s", self.name, exc)

    async def _async_dismiss_notification(self) -> None:
        """Verwijder de persistent notification."""
        await self.hass.services.async_call(
            "persistent_notification",
            "dismiss",
            {"notification_id": NOTIFICATION_ID_PREFIX + (self._attr_unique_id or "")},
        )

    async def _async_switch(self, entity_id: str, turn_on: bool, mode: str = "heat") -> None:
        domain = entity_id.split(".")[0]
        if domain in ("switch", "input_boolean"):
            service = "turn_on" if turn_on else "turn_off"
            await self.hass.services.async_call(
                domain, service, {"entity_id": entity_id}, blocking=True
            )
        elif domain == "climate":
            if turn_on:
                if mode == "cool":
                    state = self.hass.states.get(entity_id)
                    supported = state.attributes.get("hvac_modes", []) if state else []
                    if HVACMode.COOL in supported:
                        hvac_mode = HVACMode.COOL
                    elif HVACMode.HEAT_COOL in supported:
                        hvac_mode = HVACMode.HEAT_COOL
                    elif HVACMode.AUTO in supported:
                        hvac_mode = HVACMode.AUTO
                    else:
                        hvac_mode = HVACMode.COOL
                else:
                    hvac_mode = HVACMode.HEAT
            elif self._ac_idle_mode == AC_IDLE_FAN_ONLY:
                hvac_mode = HVACMode.FAN_ONLY
            else:
                hvac_mode = HVACMode.OFF
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": hvac_mode},
                blocking=True,
            )
            if turn_on and self._attr_target_temperature:
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": entity_id,
                        "temperature": self.effective_target_temperature,
                    },
                    blocking=True,
                )
