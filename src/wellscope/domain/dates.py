"""Date parsing for report fields (day-first numerics) and questions (English/Indonesian)."""

from __future__ import annotations

import re
from datetime import date

MONTHS: dict[str, int] = {
    "jan": 1, "january": 1, "januari": 1,
    "feb": 2, "february": 2, "februari": 2,
    "mar": 3, "march": 3, "maret": 3,
    "apr": 4, "april": 4,
    "may": 5, "mei": 5,
    "jun": 6, "june": 6, "juni": 6,
    "jul": 7, "july": 7, "juli": 7,
    "aug": 8, "august": 8, "agu": 8, "agt": 8, "agustus": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "okt": 10, "oktober": 10,
    "nov": 11, "november": 11, "nopember": 11,
    "dec": 12, "december": 12, "des": 12, "desember": 12,
}  # fmt: skip

_ISO = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
_DAY_FIRST = re.compile(r"\b(?P<d>\d{1,2})[/-](?P<m>\d{1,2})[/-](?P<y>\d{4})\b")
_DAY_MONTH = re.compile(
    r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?\s+(?P<mon>[A-Za-z]{3,9})\.?(?:\s+(?P<y>\d{4}))?\b"
)
_MONTH_DAY = re.compile(
    r"\b(?P<mon>[A-Za-z]{3,9})\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?,?\s+(?P<y>\d{4})\b"
)


def find_dates(text: str, default_year: int | None = None) -> list[date]:
    """Every valid date in ``text`` in reading order; partial dates need ``default_year``."""
    found: dict[int, date] = {}
    taken: list[range] = []
    for pattern in (_ISO, _DAY_FIRST, _MONTH_DAY, _DAY_MONTH):
        for match in pattern.finditer(text):
            span = range(match.start(), match.end())
            if any(span.start in other or other.start in span for other in taken):
                continue
            parsed = _to_date(match.groupdict(), default_year)
            if parsed is not None:
                found[match.start()] = parsed
                taken.append(span)
    return [found[position] for position in sorted(found)]


def parse_date(text: str) -> date | None:
    """The first date in a field value such as ``19/07/2026 / IN``, or ``None``."""
    dates = find_dates(text)
    return dates[0] if dates else None


def _to_date(parts: dict[str, str | None], default_year: int | None) -> date | None:
    month_name = parts.get("mon")
    month = MONTHS.get(month_name.lower()) if month_name else _int(parts.get("m"))
    year = _int(parts.get("y")) or default_year
    day = _int(parts.get("d"))
    if month is None or year is None or day is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    return int(value) if value else None
