"""Visible page layout of a PDF: words, table cells and ruling lines for every page."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pdfplumber
from pdfplumber.page import Page

from wellscope.errors import DocumentParseError
from wellscope.ingestion.pdf.geometry import Box, Line, Rule, Word, cluster_lines, words_in
from wellscope.ingestion.pdf.visibility import VisibilityStats, visible_page

MAX_PAGES = 200
WORD_X_TOLERANCE = 1.5
WORD_Y_TOLERANCE = 2.5
DEDUPE_TOLERANCE = 1.0
RUN_GAP = 1.0
SAME_BASELINE = 1.0
VERTICAL_SLACK = 0.5
MIN_RULE_LENGTH = 2.0
TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}


@dataclass(frozen=True, slots=True)
class PageLayout:
    """What form parsers need from one page, restricted to visible content."""

    number: int
    width: float
    height: float
    words: tuple[Word, ...]
    cells: tuple[Box, ...]
    vertical_rules: tuple[Rule, ...]
    horizontal_rules: tuple[Rule, ...]
    visibility: VisibilityStats

    def lines(self, box: Box | None = None) -> list[Line]:
        """Visual lines of the page, or of the words centred inside ``box``."""
        return cluster_lines(self.words if box is None else words_in(self.words, box))

    def text(self, box: Box | None = None) -> str:
        """Visible text of the page (or of ``box``), one visual line per text line."""
        return "\n".join(line.text for line in self.lines(box))


def load_layout(path: Path, max_pages: int = MAX_PAGES) -> list[PageLayout]:
    """Read every page of ``path`` into a :class:`PageLayout`."""
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) > max_pages:
            message = f"{path.name} has {len(pdf.pages)} pages (limit {max_pages})"
            raise DocumentParseError(message, code="too_many_pages")
        return [_page_layout(number, page) for number, page in enumerate(pdf.pages, start=1)]


def _page_layout(number: int, page: Page) -> PageLayout:
    visible, stats = visible_page(page)
    border_lines = [_rule(line) for line in page.lines if _is_vertical(line)]
    overflow = _overflow_char_ids(visible.chars, border_lines)
    visible = visible.filter(lambda obj: id(obj) not in overflow).dedupe_chars(
        tolerance=DEDUPE_TOLERANCE
    )
    words = visible.extract_words(
        x_tolerance=WORD_X_TOLERANCE, y_tolerance=WORD_Y_TOLERANCE, return_chars=True
    )
    edges = [edge for edge in page.edges if _length(edge) >= MIN_RULE_LENGTH]
    cells = {Box(*cell) for table in visible.find_tables(TABLE_SETTINGS) for cell in table.cells}
    return PageLayout(
        number=number,
        width=float(page.width),
        height=float(page.height),
        words=tuple(part for word in words for part in _split_at_borders(word, border_lines)),
        cells=tuple(sorted(cells, key=lambda box: (box.top, box.x0))),
        vertical_rules=tuple(_rule(edge) for edge in edges if edge["orientation"] == "v"),
        horizontal_rules=tuple(_rule(edge) for edge in edges if edge["orientation"] == "h"),
        visibility=stats,
    )


def _overflow_char_ids(chars: Iterable[dict[str, Any]], borders: Sequence[Rule]) -> set[int]:
    """Characters of a text run that spill past the first cell border to the run's right.

    Reports clip cell content at the border, so the spilled glyphs are invisible on the page,
    yet extractors read them and glue them to the next cell's value (``…REAMER1``).
    """
    dropped: set[int] = set()
    run: list[dict[str, Any]] = []
    for char in [*chars, None]:
        if char is not None and run and _continues(run[-1], char):
            run.append(char)
            continue
        if run:
            dropped.update(_clipped(run, borders))
        run = [char] if char is not None else []
    return dropped


def _continues(previous: dict[str, Any], char: dict[str, Any]) -> bool:
    return (
        abs(float(char["top"]) - float(previous["top"])) <= SAME_BASELINE
        and -RUN_GAP <= float(char["x0"]) - float(previous["x1"]) <= RUN_GAP
    )


def _clipped(run: Sequence[dict[str, Any]], borders: Sequence[Rule]) -> set[int]:
    start = _centre_x(run[0])
    middle = (float(run[0]["top"]) + float(run[0]["bottom"])) / 2
    limits = [
        rule.x0
        for rule in borders
        if rule.x0 > start and rule.top - VERTICAL_SLACK <= middle <= rule.bottom + VERTICAL_SLACK
    ]
    if not limits:
        return set()
    limit = min(limits)
    return {id(char) for char in run if _centre_x(char) > limit}


def _split_at_borders(word: dict[str, Any], borders: Sequence[Rule]) -> list[Word]:
    """Split a word whose characters sit on both sides of a cell border into one word per side."""
    middle = (float(word["top"]) + float(word["bottom"])) / 2
    cuts = sorted(
        rule.x0
        for rule in borders
        if float(word["x0"]) < rule.x0 < float(word["x1"])
        and rule.top - VERTICAL_SLACK <= middle <= rule.bottom + VERTICAL_SLACK
    )
    chars = word.get("chars") or []
    if not cuts or not chars:
        return [_word(word)]
    groups: list[list[dict[str, Any]]] = [[] for _ in range(len(cuts) + 1)]
    for char in chars:
        groups[bisect_left(cuts, _centre_x(char))].append(char)
    return [_word(_merge_chars(group)) for group in groups if group]


def _merge_chars(chars: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "text": "".join(str(char["text"]) for char in chars),
        "x0": min(float(char["x0"]) for char in chars),
        "x1": max(float(char["x1"]) for char in chars),
        "top": min(float(char["top"]) for char in chars),
        "bottom": max(float(char["bottom"]) for char in chars),
    }


def _centre_x(char: dict[str, Any]) -> float:
    return (float(char["x0"]) + float(char["x1"])) / 2


def _is_vertical(obj: dict[str, Any]) -> bool:
    return abs(float(obj["x0"]) - float(obj["x1"])) < VERTICAL_SLACK and _length(obj) > 0


def _length(obj: dict[str, Any]) -> float:
    return max(float(obj["x1"]) - float(obj["x0"]), float(obj["bottom"]) - float(obj["top"]))


def _rule(obj: dict[str, Any]) -> Rule:
    return Rule(float(obj["x0"]), float(obj["x1"]), float(obj["top"]), float(obj["bottom"]))


def _word(word: dict[str, Any]) -> Word:
    return Word(
        text=str(word["text"]),
        x0=float(word["x0"]),
        x1=float(word["x1"]),
        top=float(word["top"]),
        bottom=float(word["bottom"]),
    )
