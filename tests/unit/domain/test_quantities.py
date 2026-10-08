from __future__ import annotations

import pytest

from wellscope.domain.quantities import parse_inches, parse_quantity


@pytest.mark.parametrize(
    ("raw", "value", "unit"),
    [
        ("1,200.00 m", 1200.0, "m"),
        ("29.04 days", 29.04, "days"),
        ("26.82%", 26.82, "%"),
        ("17.500 in", 17.5, "in"),
        ("348,640.02", 348640.02, None),
        ("1.50 hr", 1.5, "hr"),
        ("0.00 m/hr", 0.0, "m/hr"),
        ("19.4 BMP", 19.4, "BMP"),
        ("0.00 /", 0.0, None),
    ],
)
def test_parse_quantity_splits_value_and_unit(raw: str, value: float, unit: str | None) -> None:
    quantity = parse_quantity(raw)
    assert quantity.value == pytest.approx(value)
    assert quantity.unit == unit
    assert quantity.raw == raw.strip()


def test_parse_quantity_keeps_text_when_value_is_not_numeric() -> None:
    quantity = parse_quantity("Synthetic Based Mud (SBM)")
    assert quantity.value is None
    assert quantity.raw == "Synthetic Based Mud (SBM)"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('17½"', 17.5),
        ("14¾", 14.75),
        ("12-1/4", 12.25),
        ("8-1/2 (PH)", 8.5),
        ('6 5/8"', 6.625),
        ('9-5/8"', 9.625),
        ("36", 36.0),
        ('30"', 30.0),
        ("17.500 in", 17.5),
    ],
)
def test_parse_inches_handles_unicode_and_hyphenated_fractions(raw: str, expected: float) -> None:
    assert parse_inches(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "Open Hole", "12-1/0"])
def test_parse_inches_returns_none_for_non_sizes(raw: str) -> None:
    assert parse_inches(raw) is None
