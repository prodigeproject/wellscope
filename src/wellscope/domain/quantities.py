"""Measured values that keep their original text, and inch sizes written with fractions."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

_QUANTITY = re.compile(
    r"(?P<number>[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?P<rest>.*)", re.DOTALL
)
_UNIT = re.compile(r"(?:%|°[CF]?|[A-Za-z][A-Za-z0-9/%°.\-]*)")
_UNICODE_FRACTIONS = {
    "½": 0.5,
    "¼": 0.25,
    "¾": 0.75,
    "⅛": 0.125,
    "⅜": 0.375,
    "⅝": 0.625,
    "⅞": 0.875,
}
_INCHES = re.compile(
    r"(?P<whole>\d+(?:\.\d+)?)"
    r"(?:\s*(?P<unicode>[½¼¾⅛⅜⅝⅞])|[\s-]+(?P<numerator>\d+)/(?P<denominator>\d+))?"
)


class Quantity(BaseModel):
    """A value extracted from a report: number, unit and the verbatim source text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: float | None = None
    unit: str | None = None
    raw: str


def parse_quantity(raw: str) -> Quantity:
    """Split ``"1,200.00 m"`` into ``1200.0`` and ``"m"``; non-numeric text keeps only ``raw``."""
    text = raw.strip()
    match = _QUANTITY.fullmatch(text)
    if match is None:
        return Quantity(raw=text)
    rest = match["rest"].strip()
    unit = rest if rest and _UNIT.fullmatch(rest) else None
    return Quantity(value=float(match["number"].replace(",", "")), unit=unit, raw=text)


def parse_inches(raw: str) -> float | None:
    """Convert sizes such as ``17½"``, ``12-1/4`` or ``6 5/8"`` into decimal inches."""
    match = _INCHES.match(raw.strip())
    if match is None:
        return None
    value = float(match["whole"])
    if match["unicode"]:
        value += _UNICODE_FRACTIONS[match["unicode"]]
    elif match["numerator"]:
        denominator = int(match["denominator"])
        if denominator == 0:
            return None
        value += int(match["numerator"]) / denominator
    return value
