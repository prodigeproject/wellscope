from __future__ import annotations

from datetime import date

import pytest

from wellscope.domain.dates import find_dates, parse_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("19/07/2026", date(2026, 7, 19)),
        ("29-08-2026", date(2026, 8, 29)),
        ("2026-08-29", date(2026, 8, 29)),
        ("20th July 2026", date(2026, 7, 20)),
        ("10th August 2026", date(2026, 8, 10)),
        ("19 Juli 2026", date(2026, 7, 19)),
        ("9 Agustus 2026", date(2026, 8, 9)),
        ("July 19, 2026", date(2026, 7, 19)),
        ("1st Sep 2026", date(2026, 9, 1)),
        ("19/07/2026 / IN", date(2026, 7, 19)),
    ],
)
def test_parse_date_supports_report_and_question_formats(raw: str, expected: date) -> None:
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", "32/13/2026", "31/02/2026", "not a date", "10 days"])
def test_parse_date_rejects_invalid_or_missing_dates(raw: str) -> None:
    assert parse_date(raw) is None


def test_find_dates_returns_all_dates_in_order() -> None:
    text = "Compare 19/07/2026 with 9 Agustus 2026 and 2026-09-10."
    assert find_dates(text) == [date(2026, 7, 19), date(2026, 8, 9), date(2026, 9, 10)]


def test_find_dates_uses_default_year_for_partial_dates() -> None:
    assert find_dates("apa yang terjadi 20 Juli jam 03:00", default_year=2026) == [
        date(2026, 7, 20)
    ]


def test_find_dates_skips_partial_dates_without_default_year() -> None:
    assert find_dates("20 Juli") == []
