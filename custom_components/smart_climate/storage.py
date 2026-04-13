"""Persistent storage for Smart Climate learned data.

Stores learned heating/cooling rates, PID state, and pump history
across Home Assistant restarts so the self-learning algorithm starts
informed instead of from scratch every time.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = "smart_climate"

# Maximum number of heating sessions to remember
MAX_SESSIONS = 50


class SmartClimateStorage:
    """Thin wrapper around HA's Store for learned climate data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}_{entry_id}",
            private=True,
        )
        self._data: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_load(self) -> None:
        """Load data from disk. Call once on integration startup."""
        data = await self._store.async_load()
        self._data = data or {}
        _LOGGER.debug("SmartClimateStorage loaded: %s", list(self._data.keys()))

    async def async_save(self) -> None:
        """Persist data to disk."""
        await self._store.async_save(self._data)

    async def async_remove(self) -> None:
        """Delete stored data (called on integration removal)."""
        await self._store.async_remove()

    # ------------------------------------------------------------------
    # Heating / cooling rates  (°C per minute)
    # ------------------------------------------------------------------

    @property
    def heating_rate(self) -> float | None:
        return self._data.get("heating_rate")

    @heating_rate.setter
    def heating_rate(self, value: float) -> None:
        self._data["heating_rate"] = round(value, 5)

    @property
    def cooling_rate(self) -> float | None:
        return self._data.get("cooling_rate")

    @cooling_rate.setter
    def cooling_rate(self, value: float) -> None:
        self._data["cooling_rate"] = round(value, 5)

    @property
    def idle_heating_rate(self) -> float | None:
        """Rate at which the room heats up without the heater (residual heat)."""
        return self._data.get("idle_heating_rate")

    @idle_heating_rate.setter
    def idle_heating_rate(self, value: float) -> None:
        self._data["idle_heating_rate"] = round(value, 5)

    # ------------------------------------------------------------------
    # Heating sessions  (for EMA learning)
    # ------------------------------------------------------------------

    def add_heating_session(self, session: dict[str, Any]) -> None:
        """Record a completed heating session.

        session keys:
            start_temp   : float
            end_temp     : float
            duration_min : float
            rate_c_per_min: float
            timestamp    : ISO string
        """
        sessions: list = self._data.setdefault("heating_sessions", [])
        sessions.append(session)
        # Keep only the most recent sessions
        if len(sessions) > MAX_SESSIONS:
            self._data["heating_sessions"] = sessions[-MAX_SESSIONS:]

    def add_cooling_session(self, session: dict[str, Any]) -> None:
        sessions: list = self._data.setdefault("cooling_sessions", [])
        sessions.append(session)
        if len(sessions) > MAX_SESSIONS:
            self._data["cooling_sessions"] = sessions[-MAX_SESSIONS:]

    @property
    def heating_sessions(self) -> list[dict]:
        return self._data.get("heating_sessions", [])

    @property
    def cooling_sessions(self) -> list[dict]:
        return self._data.get("cooling_sessions", [])

    # ------------------------------------------------------------------
    # PID state
    # ------------------------------------------------------------------

    @property
    def pid_integral(self) -> float:
        return self._data.get("pid_integral", 0.0)

    @pid_integral.setter
    def pid_integral(self, value: float) -> None:
        self._data["pid_integral"] = round(value, 4)

    # ------------------------------------------------------------------
    # Pump state
    # ------------------------------------------------------------------

    @property
    def last_pump_exercise(self) -> str | None:
        """ISO timestamp of the last pump exercise run."""
        return self._data.get("last_pump_exercise")

    @last_pump_exercise.setter
    def last_pump_exercise(self, iso: str) -> None:
        self._data["last_pump_exercise"] = iso

    @property
    def pump_total_runtime_h(self) -> float:
        """Cumulative pump runtime in hours (lifetime)."""
        return self._data.get("pump_total_runtime_h", 0.0)

    @pump_total_runtime_h.setter
    def pump_total_runtime_h(self, value: float) -> None:
        self._data["pump_total_runtime_h"] = round(value, 3)

    # ------------------------------------------------------------------
    # Early start lead times (learned per preset transition)
    # ------------------------------------------------------------------

    def get_early_start_minutes(self, from_preset: str, to_preset: str) -> float | None:
        """Return learned lead time in minutes for a preset transition."""
        key = f"early_start_{from_preset}_to_{to_preset}"
        return self._data.get(key)

    def set_early_start_minutes(self, from_preset: str, to_preset: str, minutes: float) -> None:
        key = f"early_start_{from_preset}_to_{to_preset}"
        self._data[key] = round(minutes, 1)
