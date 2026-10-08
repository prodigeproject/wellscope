"""Painter's-algorithm visibility: keep only characters a reader can actually see.

Some exported reports carry hidden layers: white text on white paper, and labels painted over by
shapes drawn later. Plain extractors interleave that text with the visible text. A character is
kept only when no later opaque fill covers it and its colour contrasts with the fill beneath it.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from pdfminer.layout import LTChar, LTComponent, LTCurve
from pdfplumber.page import Page

CONTRAST_THRESHOLD = 0.35
CONTAINMENT_TOLERANCE = 0.5
PAPER_LUMINANCE = 1.0
DEFAULT_INK_LUMINANCE = 0.0
_GRAY, _RGB, _CMYK = 1, 3, 4


@dataclass(frozen=True, slots=True)
class VisibilityStats:
    """How many characters on a page survived the visibility filter."""

    total_chars: int
    visible_chars: int
    aligned: bool

    @property
    def ratio(self) -> float:
        """Share of characters kept; 1.0 for pages without text."""
        return self.visible_chars / self.total_chars if self.total_chars else 1.0


@dataclass(frozen=True, slots=True)
class _Fill:
    order: int
    x0: float
    y0: float
    x1: float
    y1: float
    luminance: float

    def contains(self, x: float, y: float) -> bool:
        tolerance = CONTAINMENT_TOLERANCE
        return (
            self.x0 - tolerance <= x <= self.x1 + tolerance
            and self.y0 - tolerance <= y <= self.y1 + tolerance
        )


def visible_page(page: Page) -> tuple[Page, VisibilityStats]:
    """Return ``page`` restricted to visible characters, plus visibility statistics."""
    layout_chars, fills = _scan(page.layout)
    plumber_chars = page.chars
    if len(layout_chars) != len(plumber_chars):
        # Cannot align layout objects with pdfplumber's characters; keep everything and say so.
        return page, VisibilityStats(len(plumber_chars), len(plumber_chars), aligned=False)
    visible_ids = {
        id(plumber_char)
        for (order, char), plumber_char in zip(layout_chars, plumber_chars, strict=True)
        if _is_visible(order, char, fills)
    }
    filtered = page.filter(lambda obj: obj.get("object_type") != "char" or id(obj) in visible_ids)
    return filtered, VisibilityStats(len(plumber_chars), len(visible_ids), aligned=True)


def _scan(objects: Iterable[LTComponent]) -> tuple[list[tuple[int, LTChar]], list[_Fill]]:
    chars: list[tuple[int, LTChar]] = []
    fills: list[_Fill] = []
    for order, obj in enumerate(_walk(objects)):
        if isinstance(obj, LTChar):
            chars.append((order, obj))
        elif isinstance(obj, LTCurve) and obj.fill:
            luminance = _luminance(obj.non_stroking_color)
            fills.append(_Fill(order, obj.x0, obj.y0, obj.x1, obj.y1, luminance))
    return chars, fills


def _walk(objects: Iterable[LTComponent]) -> Iterator[LTComponent]:
    """Depth-first in content-stream order, mirroring pdfplumber's own traversal."""
    for obj in objects:
        children = getattr(obj, "_objs", None)
        if children is not None:
            yield from _walk(children)
        else:
            yield obj


def _is_visible(order: int, char: LTChar, fills: list[_Fill]) -> bool:
    centre_x = (char.x0 + char.x1) / 2
    centre_y = (char.y0 + char.y1) / 2
    background = PAPER_LUMINANCE
    for fill in fills:
        if not fill.contains(centre_x, centre_y):
            continue
        if fill.order > order:
            return False
        background = fill.luminance
    ink = _luminance(getattr(char.graphicstate, "ncolor", None))
    return abs(ink - background) >= CONTRAST_THRESHOLD


def _luminance(color: object) -> float:
    """Relative luminance of a PDF colour (Gray, RGB or CMYK); unknown colours count as ink."""
    if isinstance(color, int | float):
        return float(color)
    if not isinstance(color, tuple | list) or not all(
        isinstance(part, int | float) for part in color
    ):
        return DEFAULT_INK_LUMINANCE
    if len(color) == _GRAY:
        return float(color[0])
    if len(color) == _RGB:
        red, green, blue = (float(part) for part in color)
    elif len(color) == _CMYK:
        cyan, magenta, yellow, black = (float(part) for part in color)
        red, green, blue = ((1 - c) * (1 - black) for c in (cyan, magenta, yellow))
    else:
        return DEFAULT_INK_LUMINANCE
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue
