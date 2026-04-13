"""Smart Climate — Pump Controller (switch platform).

Manages a floor-heating circulation pump with:

* Zone following  — on when any monitored zone/valve entity is active
* Post-heat delay — stays on N minutes after last zone closes
                    (ensures residual heat reaches the floor)
* Minimum run time — protects pump from rapid cycling
* Anti-seize exercise — forced run every X hours for Y minutes
                        (prevents pump from seizing when idle)
* Preferred exercise window — chooses a quiet time of day
* Manual trigger service — trigger exercise via automation or dashboard
* Persistent history — total runtime and last exercise time survive restart

Kincony KC868-A6-V1 notes
--------------------------
Each relay on the board becomes a `switch` entity in Home Assistant
after integration via ESPHome (recommended) or MQTT.

Typical setup for 10 zones with 2 × KC868-A6 boards:
  Board 1 relays 1-6  → zones 1-6   (switch.zone_1 … switch.zone_6)
  Board 2 relays 1-4  → zones 7-10  (switch.zone_7 … switch.zone_10)
  Board 2 relay  5    → pump         (switch.floor_pump)
  Board 2 relay  6    → spare

Configure this entity by pointing:
  pump_entity  → switch.floor_pump
  zone_entities → [switch.zone_1, switch.zone_2, … switch.zone_10]
"""
from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTime,
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
    CONF_PUMP_ENTITY,
    CONF_PUMP_ZONE_ENTITIES,
    CONF_PUMP_ANTI_SEIZE_INTERVAL,
    CONF_PUMP_ANTI_SEIZE_DURATION,
    CONF_PUMP_POST_HEAT_DELAY,
    CONF_PUMP_MIN_RUN_TIME,
    CONF_PUMP_EXERCISE_TIME,
    DEFAULT_PUMP_ANTI_SEIZE_INTERVAL,
    DEFAULT_PUMP_ANTI_SEIZE_DURATION,
    DEFAULT_PUMP_POST_HEAT_DELAY,
    DEFAULT_PUMP_MIN_RUN_TIME,
    DEFAULT_PUMP_EXERCISE_TIME,
    DOMAIN,
    SUFFIX_PUMP,
)
from .storage import SmartClimateStorage

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up pump controller if configured."""
    d = {**config_entry.data, **config_entry.options}
    pump_entity_id = d.get(CONF_PUMP_ENTITY)
    if not pump_entity_id:
        return  # No pump configured for this entry

    pump = FloorHeatingPump(
        hass=hass,
        config_entry=config_entry,
        unique_id=config_entry.entry_id + SUFFIX_PUMP,
        name=f"{config_entry.title} pomp",
        pump_entity_id=pump_entity_id,
        zone_entity_ids=list(d.get(CONF_PUMP_ZONE_ENTITIES) or []),
        anti_seize_interval_h=int(d.get(CONF_PUMP_ANTI_SEIZE_INTERVAL, DEFAULT_PUMP_ANTI_SEIZE_INTERVAL)),
        anti_seize_duration_min=int(d.get(CONF_PUMP_ANTI_SEIZE_DURATION, DEFAULT_PUMP_ANTI_SEIZE_DURATION)),
        post_heat_delay_min=int(d.get(CONF_PUMP_POST_HEAT_DELAY, DEFAULT_PUMP_POST_HEAT_DELAY)),
        min_run_time_sec=int(d.get(CONF_PUMP_MIN_RUN_TIME, DEFAULT_PUMP_MIN_RUN_TIME)),
        exercise_time=str(d.get(CONF_PUMP_EXERCISE_TIME, DEFAULT_PUMP_EXERCISE_TIME)),
    )

    # Load persistent storage
    storage = SmartClimateStorage(hass, config_entry.entry_id + "_pump")
    await storage.async_load()
    pump.set_storage(storage)

    # Make pump accessible for services
    hass.data[DOMAIN][config_entry.entry_id]["pump"] = pump

    async_add_entities([pump])


# ---------------------------------------------------------------------------

class FloorHeatingPump(SwitchEntity, RestoreEntity):
    """Floor heating circulation pump with anti-seize protection."""

    _attr_should_poll = False
    _attr_icon = "mdi:pump"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        unique_id: str,
        name: str,
        pump_entity_id: str,
        zone_entity_ids: list[str],
        anti_seize_interval_h: int,
        anti_seize_duration_min: int,
        post_heat_delay_min: int,
        min_run_time_sec: int,
        exercise_time: str,
    ) -> None:
        self.hass = hass
        self._config_entry = config_entry
        self._attr_unique_id = unique_id
        self._attr_name = name

        self._pump_entity_id = pump_entity_id
        self._zone_entity_ids = zone_entity_ids
        self._anti_seize_interval_h = anti_seize_interval_h
        self._anti_seize_duration_min = anti_seize_duration_min
        self._post_heat_delay_min = post_heat_delay_min
        self._min_run_time_sec = min_run_time_sec

        # Parse preferred exercise time (e.g. "02:00")
        try:
            parts = exercise_time.split(":")
            self._exercise_hour = int(parts[0])
            self._exercise_minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            self._exercise_hour = 2
            self._exercise_minute = 0

        # State
        self._is_on: bool = False
        self._manual_override: bool = False
        self._zone_demand: bool = False
        self._exercise_active: bool = False
        self._post_heat_timer: asyncio.TimerHandle | None = None
        self._exercise_task: asyncio.Task | None = None

        # Timestamps
        self._pump_on_since: datetime | None = None
        self._last_exercise: datetime | None = None
        self._runtime_today_min: float = 0.0
        self._total_runtime_h: float = 0.0

        self._storage: SmartClimateStorage | None = None

    def set_storage(self, storage: SmartClimateStorage) -> None:
        self._storage = storage
        # Restore last exercise time
        iso = storage.last_pump_exercise
        if iso:
            try:
                self._last_exercise = datetime.fromisoformat(iso)
            except ValueError:
                pass
        self._total_runtime_h = storage.pump_total_runtime_h

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Restore switch state
        last = await self.async_get_last_state()
        if last is not None:
            self._is_on = last.state == STATE_ON

        # Track zone entities
        if self._zone_entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, self._zone_entity_ids, self._async_zone_changed
                )
            )

        # Check demand every 30 s (keep-alive)
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_evaluate, timedelta(seconds=30)
            )
        )

        # Daily runtime reset
        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_midnight_reset, hour=0, minute=0, second=0
            )
        )

        # Exercise at preferred time
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._async_exercise_tick,
                hour=self._exercise_hour,
                minute=self._exercise_minute,
                second=0,
            )
        )

        # Initial evaluation
        self._update_zone_demand()
        await self._async_evaluate()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        attrs: dict[str, Any] = {
            "zone_demand": self._zone_demand,
            "exercise_active": self._exercise_active,
            "manual_override": self._manual_override,
            "anti_seize_interval_h": self._anti_seize_interval_h,
            "anti_seize_duration_min": self._anti_seize_duration_min,
            "post_heat_delay_min": self._post_heat_delay_min,
            "runtime_today_min": round(self.runtime_today_min, 1),
            "total_runtime_h": round(self._total_runtime_h, 2),
            "preferred_exercise_time": f"{self._exercise_hour:02d}:{self._exercise_minute:02d}",
        }
        if self._last_exercise:
            attrs["last_exercise"] = self._last_exercise.isoformat()
            hours_since = (now - self._last_exercise).total_seconds() / 3600
            attrs["hours_since_exercise"] = round(hours_since, 1)
            next_h = max(0, self._anti_seize_interval_h - hours_since)
            attrs["next_exercise_due_h"] = round(next_h, 1)
        else:
            attrs["last_exercise"] = None
            attrs["next_exercise_due_h"] = 0
        return attrs

    @property
    def runtime_today_min(self) -> float:
        total = self._runtime_today_min
        if self._is_on and self._pump_on_since:
            total += (dt_util.utcnow() - self._pump_on_since).total_seconds() / 60
        return total

    # ------------------------------------------------------------------
    # Manual switch control
    # ------------------------------------------------------------------

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn pump on manually (sets override)."""
        self._manual_override = True
        await self._async_set_pump(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn pump off manually. Override cleared after min_run_time."""
        if self._exercise_active:
            _LOGGER.warning("[%s] Cannot turn off — exercise in progress", self.name)
            return
        self._manual_override = False
        if not self._zone_demand:
            await self._async_set_pump(False)

    # ------------------------------------------------------------------
    # Exercise (anti-seize)
    # ------------------------------------------------------------------

    async def async_trigger_exercise(self, duration_min: int | None = None) -> None:
        """Manually trigger a pump exercise run."""
        dur = duration_min or self._anti_seize_duration_min
        _LOGGER.info("[%s] Exercise triggered: %d min", self.name, dur)
        await self._async_run_exercise(dur)

    async def _async_run_exercise(self, duration_min: int) -> None:
        """Run the pump for `duration_min` minutes regardless of zone demand."""
        if self._exercise_active:
            _LOGGER.debug("[%s] Exercise already active", self.name)
            return
        self._exercise_active = True
        await self._async_set_pump(True)
        self.async_write_ha_state()

        await asyncio.sleep(duration_min * 60)

        self._exercise_active = False
        self._last_exercise = dt_util.utcnow()
        if self._storage:
            self._storage.last_pump_exercise = self._last_exercise.isoformat()
            await self._storage.async_save()

        # Turn off if no zone demand
        if not self._zone_demand and not self._manual_override:
            await self._async_set_pump(False)
        self.async_write_ha_state()
        _LOGGER.info("[%s] Exercise complete", self.name)

    @callback
    def _async_exercise_tick(self, _now: datetime) -> None:
        """Called at the preferred exercise time — run if overdue."""
        if self._exercise_active:
            return
        if self._is_exercise_due():
            _LOGGER.info("[%s] Scheduled exercise due — starting", self.name)
            self._exercise_task = self.hass.async_create_task(
                self._async_run_exercise(self._anti_seize_duration_min)
            )

    def _is_exercise_due(self) -> bool:
        """Return True if more than anti_seize_interval_h have passed."""
        if self._last_exercise is None:
            return True
        elapsed_h = (dt_util.utcnow() - self._last_exercise).total_seconds() / 3600
        return elapsed_h >= self._anti_seize_interval_h

    # ------------------------------------------------------------------
    # Zone monitoring
    # ------------------------------------------------------------------

    @callback
    def _async_zone_changed(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self._update_zone_demand()
        self.hass.async_create_task(self._async_evaluate())

    def _update_zone_demand(self) -> None:
        """Check if any zone is calling for heat."""
        for entity_id in self._zone_entity_ids:
            state = self.hass.states.get(entity_id)
            if state and state.state not in (
                STATE_UNKNOWN, STATE_UNAVAILABLE, "off", "idle", "cool"
            ):
                self._zone_demand = True
                return
        self._zone_demand = False

    # ------------------------------------------------------------------
    # Core evaluation
    # ------------------------------------------------------------------

    async def _async_evaluate(self, _now=None) -> None:
        """Decide whether pump should run."""
        if self._exercise_active or self._manual_override:
            return  # Don't interfere with exercise or manual override

        should_run = self._zone_demand

        if should_run and not self._is_on:
            # Cancel any pending post-heat timer
            if self._post_heat_timer:
                self._post_heat_timer.cancel()
                self._post_heat_timer = None
            await self._async_set_pump(True)

        elif not should_run and self._is_on:
            # Start post-heat delay before turning off
            if self._post_heat_timer is None and self._post_heat_delay_min > 0:
                _LOGGER.debug(
                    "[%s] No zone demand — post-heat delay %.1f min",
                    self.name, self._post_heat_delay_min,
                )
                delay_sec = self._post_heat_delay_min * 60
                self._post_heat_timer = self.hass.loop.call_later(
                    delay_sec, lambda: self.hass.async_create_task(self._async_post_heat_expired())
                )
            elif self._post_heat_delay_min == 0:
                await self._async_set_pump(False)

        self.async_write_ha_state()

    async def _async_post_heat_expired(self) -> None:
        """Called when post-heat delay timer fires."""
        self._post_heat_timer = None
        if not self._zone_demand and not self._manual_override and not self._exercise_active:
            await self._async_set_pump(False)
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Physical pump control
    # ------------------------------------------------------------------

    async def _async_set_pump(self, turn_on: bool) -> None:
        """Switch the physical pump relay."""
        if turn_on == self._is_on:
            return

        # Enforce minimum run time — don't turn off too quickly
        if not turn_on and self._pump_on_since:
            elapsed = (dt_util.utcnow() - self._pump_on_since).total_seconds()
            if elapsed < self._min_run_time_sec:
                _LOGGER.debug(
                    "[%s] Min run time not reached (%.0f s < %d s) — keeping on",
                    self.name, elapsed, self._min_run_time_sec,
                )
                return

        domain = self._pump_entity_id.split(".")[0]
        service = "turn_on" if turn_on else "turn_off"

        try:
            await self.hass.services.async_call(
                domain, service, {"entity_id": self._pump_entity_id}, blocking=True
            )
        except Exception as err:
            _LOGGER.error("[%s] Failed to %s pump: %s", self.name, service, err)
            return

        if turn_on and not self._is_on:
            self._pump_on_since = dt_util.utcnow()
        elif not turn_on and self._is_on and self._pump_on_since:
            elapsed_min = (dt_util.utcnow() - self._pump_on_since).total_seconds() / 60
            self._runtime_today_min += elapsed_min
            self._total_runtime_h += elapsed_min / 60
            self._pump_on_since = None
            # Persist total runtime
            if self._storage:
                self._storage.pump_total_runtime_h = self._total_runtime_h
                self.hass.async_create_task(self._storage.async_save())

        self._is_on = turn_on
        _LOGGER.info("[%s] Pump %s", self.name, "ON" if turn_on else "OFF")

    # ------------------------------------------------------------------
    # Midnight reset
    # ------------------------------------------------------------------

    @callback
    def _async_midnight_reset(self, _now: datetime) -> None:
        self._runtime_today_min = 0.0
        self.async_write_ha_state()
