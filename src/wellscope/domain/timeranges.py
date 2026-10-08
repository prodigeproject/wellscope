"""Operation time ranges such as ``23:15 - 0:00``, which end at midnight of the report day."""

from __future__ import annotations

import re
from dataclasses import dataclass

MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR
_RANGE = re.compile(r"\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})(?:\s*hrs?)?\s*")


@dataclass(frozen=True, slots=True)
class TimeRange:
    """A span within one report day; ``end`` is ``"24:00"`` when it closes at midnight."""

    start: str
    end: str
    hours: float


def parse_time_range(text: str) -> TimeRange | None:
    """Parse ``H:MM - H:MM``; an end at or before the start means it closes at midnight."""
    match = _RANGE.fullmatch(text)
    if match is None:
        return None
    start = _minutes(match[1], match[2])
    end = _minutes(match[3], match[4])
    if start is None or end is None or start >= MINUTES_PER_DAY:
        return None
    if end <= start:
        end += MINUTES_PER_DAY
    if end > MINUTES_PER_DAY:
        return None
    return TimeRange(_format(start), _format(end), (end - start) / MINUTES_PER_HOUR)


def _minutes(hours: str, minutes: str) -> int | None:
    hour, minute = int(hours), int(minutes)
    if minute >= MINUTES_PER_HOUR or hour > MINUTES_PER_DAY // MINUTES_PER_HOUR:
        return None
    return hour * MINUTES_PER_HOUR + minute


def _format(total_minutes: int) -> str:
    return f"{total_minutes // MINUTES_PER_HOUR:02d}:{total_minutes % MINUTES_PER_HOUR:02d}"
