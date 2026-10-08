"""Pure geometry over positioned words: boxes, ruling lines, line clustering and columns.

Coordinates follow pdfplumber: origin at the top-left corner, ``top`` grows downwards.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise

LINE_TOLERANCE = 3.0
RULE_TOLERANCE = 1.0
DOUBLE_RULE_GAP = 1.5


@dataclass(frozen=True, slots=True)
class Word:
    """A visible word and its bounding box."""

    text: str
    x0: float
    x1: float
    top: float
    bottom: float

    @property
    def center_x(self) -> float:
        """Horizontal centre, used to decide which column or cell owns the word."""
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        """Vertical centre, used to decide which cell owns the word."""
        return (self.top + self.bottom) / 2


@dataclass(frozen=True, slots=True)
class Box:
    """An axis-aligned rectangle such as a table cell or a section region."""

    x0: float
    top: float
    x1: float
    bottom: float

    def contains(self, x: float, y: float) -> bool:
        """Whether the point lies inside the box (edges included)."""
        return self.x0 <= x <= self.x1 and self.top <= y <= self.bottom


@dataclass(frozen=True, slots=True)
class Rule:
    """A ruling segment; vertical rules have ``x0 == x1`` and horizontal ones ``top == bottom``."""

    x0: float
    x1: float
    top: float
    bottom: float


@dataclass(frozen=True, slots=True)
class Line:
    """Words that share a baseline, ordered left to right."""

    words: tuple[Word, ...]

    @property
    def top(self) -> float:
        """Top edge of the highest word."""
        return min(word.top for word in self.words)

    @property
    def text(self) -> str:
        """Words joined by single spaces."""
        return " ".join(word.text for word in self.words)


def cluster_lines(words: Iterable[Word], tolerance: float = LINE_TOLERANCE) -> list[Line]:
    """Group words whose tops lie within ``tolerance`` of the first word of a line.

    Tolerance-based grouping avoids the classic bug of rounding ``top`` into buckets, which
    splits a single row whenever its words straddle a bucket boundary.
    """
    groups: list[list[Word]] = []
    for word in sorted(words, key=lambda item: (item.top, item.x0)):
        if groups and abs(word.top - groups[-1][0].top) <= tolerance:
            groups[-1].append(word)
        else:
            groups.append([word])
    return [Line(tuple(sorted(group, key=lambda item: item.x0))) for group in groups]


def words_in(words: Iterable[Word], box: Box) -> list[Word]:
    """Words whose centre lies inside ``box``; avoids clipped glyphs at cell borders."""
    return [word for word in words if box.contains(word.center_x, word.center_y)]


def column_bounds(
    rules: Sequence[Rule],
    top: float,
    bottom: float,
    left: float = -math.inf,
    right: float = math.inf,
) -> list[tuple[float, float]]:
    """Intervals between vertical rules that span the whole band from ``top`` to ``bottom``."""
    xs = sorted(
        rule.x0
        for rule in rules
        if rule.top <= top + RULE_TOLERANCE
        and rule.bottom >= bottom - RULE_TOLERANCE
        and left - RULE_TOLERANCE <= rule.x0 <= right + RULE_TOLERANCE
    )
    merged: list[float] = []
    for x in xs:
        if not merged or x - merged[-1] > DOUBLE_RULE_GAP:
            merged.append(x)
    return list(pairwise(merged))


def split_into_columns(line: Line, bounds: Sequence[tuple[float, float]]) -> list[str]:
    """Text of ``line`` per column; words outside every column are dropped."""
    cells = [""] * len(bounds)
    for word in line.words:
        for index, (left, right) in enumerate(bounds):
            if left <= word.center_x <= right:
                cells[index] = f"{cells[index]} {word.text}".strip()
                break
    return cells
