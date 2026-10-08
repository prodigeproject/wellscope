from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wellscope.domain.timeranges import parse_time_range

MINUTES_PER_DAY = 24 * 60


@pytest.mark.parametrize(
    ("raw", "start", "end", "hours"),
    [
        ("0:00 - 1:30", "00:00", "01:30", 1.5),
        ("8:00 - 16:15", "08:00", "16:15", 8.25),
        ("23:15 - 0:00", "23:15", "24:00", 0.75),
        ("21:00 - 0:00", "21:00", "24:00", 3.0),
        ("00:00 - 00:15 hrs", "00:00", "00:15", 0.25),
    ],
)
def test_parse_time_range_computes_hours_including_midnight_end(
    raw: str, start: str, end: str, hours: float
) -> None:
    parsed = parse_time_range(raw)
    assert parsed is not None
    assert (parsed.start, parsed.end) == (start, end)
    assert parsed.hours == pytest.approx(hours)


@pytest.mark.parametrize("raw", ["", "Operation", "25:00 - 26:00", "10:75 - 11:00", "23:00 - 1:00"])
def test_parse_time_range_rejects_invalid_ranges(raw: str) -> None:
    assert parse_time_range(raw) is None


@given(st.integers(0, MINUTES_PER_DAY - 1), st.integers(1, MINUTES_PER_DAY))
def test_parse_time_range_hours_match_minute_difference(start: int, end: int) -> None:
    if end <= start:
        return
    text = f"{start // 60}:{start % 60:02d} - {end // 60 % 24}:{end % 60:02d}"
    parsed = parse_time_range(text)
    assert parsed is not None
    assert parsed.hours == pytest.approx((end - start) / 60)
