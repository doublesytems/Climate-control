"""Weekly schedule helper for Smart Climate."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any

import homeassistant.util.dt as dt_util

from .const import (
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_SLEEP,
    SCHED_DAYS,
    SCHED_PRESET,
    SCHED_START,
)

# Presets that are valid inside a schedule entry
VALID_SCHEDULE_PRESETS = {PRESET_COMFORT, PRESET_ECO, PRESET_SLEEP, PRESET_AWAY}


class ScheduleEntry:
    """A single time-block within the weekly schedule."""

    def __init__(self, days: list[int], start: str, preset: str) -> None:
        """
        Args:
            days:   List of weekday ints (0 = Monday … 6 = Sunday).
            start:  Start time in "HH:MM" format.
            preset: One of comfort / eco / sleep / away.
        """
        self.days: list[int] = days
        self.start: time = time.fromisoformat(start)
        self.preset: str = preset

    def to_dict(self) -> dict[str, Any]:
        return {
            SCHED_DAYS: self.days,
            SCHED_START: self.start.strftime("%H:%M"),
            SCHED_PRESET: self.preset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleEntry":
        return cls(
            days=data[SCHED_DAYS],
            start=data[SCHED_START],
            preset=data[SCHED_PRESET],
        )


class WeekSchedule:
    """Full weekly schedule with multiple time blocks."""

    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self._entries: list[ScheduleEntry] = []
        if entries:
            for raw in entries:
                try:
                    self._entries.append(ScheduleEntry.from_dict(raw))
                except (KeyError, ValueError):
                    pass

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_active_preset(self, now: datetime | None = None) -> str | None:
        """Return the preset that should be active right now.

        Returns None when no schedule entry covers the current moment.
        """
        if not self._entries:
            return None

        if now is None:
            now = dt_util.now()

        today = now.weekday()          # 0 = Monday
        current_time = now.time().replace(second=0, microsecond=0)

        # Collect entries that started at or before now for today
        candidates = [
            e for e in self._entries
            if today in e.days and e.start <= current_time
        ]

        if not candidates:
            # Fall back to yesterday's last entry that runs past midnight
            yesterday = (today - 1) % 7
            candidates = [
                e for e in self._entries
                if yesterday in e.days
            ]
            if candidates:
                return max(candidates, key=lambda e: e.start).preset
            return None

        # Return the last entry that started before now
        return max(candidates, key=lambda e: e.start).preset

    def get_next_change(self, now: datetime | None = None) -> tuple[str | None, datetime | None]:
        """Return (next_preset, datetime_of_change) or (None, None)."""
        if not self._entries:
            return None, None

        if now is None:
            now = dt_util.now()

        # Look ahead up to 8 days
        import datetime as _dt
        for offset in range(8 * 24 * 60):
            candidate_dt = now + _dt.timedelta(minutes=offset + 1)
            candidate_day = candidate_dt.weekday()
            candidate_time = candidate_dt.time().replace(second=0, microsecond=0)

            for entry in self._entries:
                if candidate_day in entry.days and entry.start == candidate_time:
                    return entry.preset, candidate_dt

        return None, None

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def set_entries(self, entries: list[dict[str, Any]]) -> None:
        new_entries = []
        for raw in entries:
            try:
                new_entries.append(ScheduleEntry.from_dict(raw))
            except (KeyError, ValueError):
                pass
        self._entries = new_entries

    def clear(self) -> None:
        self._entries = []

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._entries]

    def __bool__(self) -> bool:
        return bool(self._entries)

    def __repr__(self) -> str:
        return f"WeekSchedule({len(self._entries)} entries)"


# ---------------------------------------------------------------------------
# Text parser / formatter (voor UI-invoer in options flow)
# ---------------------------------------------------------------------------

_DAY_MAP: dict[str, int] = {
    # Nederlands
    "ma": 0, "di": 1, "wo": 2, "do": 3, "vr": 4, "za": 5, "zo": 6,
    # English
    "mo": 0, "tu": 1, "we": 2, "th": 3, "fr": 4, "sa": 5, "su": 6,
}
_DAY_NAMES: list[str] = ["ma", "di", "wo", "do", "vr", "za", "zo"]


def parse_schedule_text(text: str) -> list[dict[str, Any]]:
    """Parseert UI-tekst naar een lijst van schedule-entry dicts.

    Formaat per regel:  <dagen> <HH:MM> <preset>
    Dagen: enkelvoudig (ma), bereik (ma-vr), kommalijst (ma,wo,vr).
    Regels die beginnen met '#' of leeg zijn worden genegeerd.

    Raises:
        ValueError: bij een ongeldige regel.
    """
    entries: list[dict[str, Any]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 3:
            raise ValueError(
                f"Regel {lineno}: verwacht '<dagen> <HH:MM> <preset>', "
                f"maar kreeg '{line}'"
            )
        day_str, time_str, preset = parts
        days: set[int] = set()
        for segment in day_str.split(","):
            segment = segment.strip()
            if "-" in segment:
                a, b = segment.split("-", 1)
                start_d = _DAY_MAP.get(a.strip())
                end_d = _DAY_MAP.get(b.strip())
                if start_d is None or end_d is None:
                    raise ValueError(
                        f"Regel {lineno}: onbekende dag in bereik '{segment}'"
                    )
                for d in range(start_d, end_d + 1):
                    days.add(d)
            else:
                d = _DAY_MAP.get(segment)
                if d is None:
                    raise ValueError(
                        f"Regel {lineno}: onbekende dag '{segment}'"
                    )
                days.add(d)
        entries.append({
            SCHED_DAYS: sorted(days),
            SCHED_START: time_str,
            SCHED_PRESET: preset,
        })
    return entries


def format_schedule_text(entries: list[dict[str, Any]]) -> str:
    """Formatteert een lijst van entry-dicts terug naar leesbare tekst."""
    lines: list[str] = []
    for e in entries:
        days_str = ",".join(_DAY_NAMES[d] for d in sorted(e.get(SCHED_DAYS, [])))
        lines.append(f"{days_str} {e.get(SCHED_START, '')} {e.get(SCHED_PRESET, '')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_schedule_entries(entries: list[dict[str, Any]]) -> list[str]:
    """Return list of error messages for invalid entries. Empty = all OK."""
    errors = []
    for i, entry in enumerate(entries):
        prefix = f"Entry {i + 1}: "
        days = entry.get(SCHED_DAYS)
        if not isinstance(days, list) or not all(isinstance(d, int) and 0 <= d <= 6 for d in days):
            errors.append(prefix + "days must be a list of ints 0–6")
        start = entry.get(SCHED_START)
        if not isinstance(start, str):
            errors.append(prefix + "start must be a string like 'HH:MM'")
        else:
            try:
                time.fromisoformat(start)
            except ValueError:
                errors.append(prefix + f"start '{start}' is not a valid time")
        preset = entry.get(SCHED_PRESET)
        if preset not in VALID_SCHEDULE_PRESETS:
            errors.append(prefix + f"preset '{preset}' must be one of {sorted(VALID_SCHEDULE_PRESETS)}")
    return errors
