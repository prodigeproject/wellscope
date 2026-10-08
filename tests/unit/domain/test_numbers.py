from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wellscope.domain.numbers import extract_numbers, number_candidates, parse_number


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1,200.00", 1200.0),
        ("348,640.02", 348640.02),
        ("-0.2", -0.2),
        ("26.82%", 26.82),
        ("15.36", 15.36),
        ("0", 0.0),
        (" 2,955.49 ", 2955.49),
    ],
)
def test_parse_number_reads_english_formatted_numbers(text: str, expected: float) -> None:
    assert parse_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "-", "abc", "1,2,3.4.5", "N/A", "12-1/4"])
def test_parse_number_returns_none_for_non_numbers(text: str) -> None:
    assert parse_number(text) is None


def test_number_candidates_accept_english_and_indonesian_conventions() -> None:
    assert number_candidates("348,640.02") == {348640.02}
    assert number_candidates("348.640,02") == {348640.02}


def test_number_candidates_keep_every_reading_of_ambiguous_tokens() -> None:
    assert number_candidates("1.200") == {1.2, 1200.0}


def test_extract_numbers_finds_values_in_prose_and_ignores_trailing_punctuation() -> None:
    found = extract_numbers('Daily cost was USD 348,640.02 and NPT 1.50 hr in a 17½" hole.')
    assert {348640.02, 1.5, 17.0} <= found


@given(st.decimals(min_value=0, max_value=10**9, places=2, allow_nan=False, allow_infinity=False))
def test_parse_number_round_trips_thousands_formatting(value: Decimal) -> None:
    assert parse_number(f"{value:,.2f}") == pytest.approx(float(value))
