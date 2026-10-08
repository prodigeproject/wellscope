"""Visible page layout of a PDF: words, table cells and ruling lines for every page."""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
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
# Glyphs of one string touch (gap ~0); text of the next cell starts after some padding.
RUN_MAX_GAP = 0.3
RUN_MAX_KERNING = 0.5
SAME_BASELINE = 1.0
VERTICAL_SLACK = 0.5
MIN_RULE_LENGTH = 2.0
POSITION_DIGITS = 2
TABLE_SETTINGS = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}


Position = tuple[float, float]


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
    cell_words: dict[Box, tuple[Word, ...]]
    loose_words: tuple[Word, ...]

    def lines(self, box: Box | None = None) -> list[Line]:
        """Visual lines of the page, or of the words centred inside ``box``."""
        return cluster_lines(self.words if box is None else words_in(self.words, box))

    def cell_lines(self, cell: Box) -> list[Line]:
        """Visual lines of the words owned by ``cell`` (its smallest enclosing cell)."""
        return cluster_lines(self.cell_words.get(cell, ()))

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
    cells = {Box(*cell) for table in visible.find_tables(TABLE_SETTINGS) for cell in table.cells}
    border_lines = [_rule(line) for line in page.lines if _is_vertical(line)]
    overflow, tails = _overflow(visible.chars, border_lines)
    visible = visible.filter(lambda obj: id(obj) not in overflow).dedupe_chars(
        tolerance=DEDUPE_TOLERANCE
    )
    words = visible.extract_words(
        x_tolerance=WORD_X_TOLERANCE, y_tolerance=WORD_Y_TOLERANCE, return_chars=True
    )
    edges = [edge for edge in page.edges if _length(edge) >= MIN_RULE_LENGTH]
    split_words = tuple(
        part for word in words for part in _split_at_borders(word, border_lines, tails)
    )
    cell_words, loose_words = _assign_words(split_words, cells)
    return PageLayout(
        number=number,
        width=float(page.width),
        height=float(page.height),
        words=split_words,
        cells=tuple(sorted(cells, key=lambda box: (box.top, box.x0))),
        vertical_rules=tuple(_rule(edge) for edge in edges if edge["orientation"] == "v"),
        horizontal_rules=tuple(_rule(edge) for edge in edges if edge["orientation"] == "h"),
        visibility=stats,
        cell_words=cell_words,
        loose_words=loose_words,
    )


def _assign_words(
    words: Sequence[Word], cells: set[Box]
) -> tuple[dict[Box, tuple[Word, ...]], tuple[Word, ...]]:
    """Give each word to the smallest cell containing its centre (tables may nest or overlap)."""
    owned: dict[Box, list[Word]] = {}
    loose: list[Word] = []
    for word in words:
        containing = [cell for cell in cells if cell.contains(word.center_x, word.center_y)]
        if containing:
            owner = min(containing, key=lambda cell: (cell.x1 - cell.x0) * (cell.bottom - cell.top))
            owned.setdefault(owner, []).append(word)
        else:
            loose.append(word)
    return {cell: tuple(items) for cell, items in owned.items()}, tuple(loose)


def _overflow(
    chars: Sequence[dict[str, Any]], borders: Sequence[Rule]
) -> tuple[set[int], dict[Position, str]]:
    """Characters of text runs that spill past a cell border into a neighbour's text.

    Reports clip cell content at inner borders (the page shows ``Fire and Aba``), yet the
    spilled glyphs are in the file and extractors glue them to the next cell (``…REAMER1``,
    ``AbandLoanst``). The spilled glyphs are removed from the page geometry and their text is
    returned keyed by the position of the run's last kept character, so the value keeps its full
    text in its own cell. A border only clips when other text sits beyond it on the same
    baseline; text running past an outer frame stays visible and is kept.
    """
    dropped: set[int] = set()
    tails: dict[Position, str] = {}
    run: list[dict[str, Any]] = []
    for char in [*chars, None]:
        if char is not None and run and _continues(run[-1], char):
            run.append(char)
            continue
        clipped = _clipped(run, borders, chars) if run else set()
        kept = [item for item in run if id(item) not in clipped]
        if clipped and kept:
            spilled = [item for item in run if id(item) in clipped]
            tails[_position(kept[-1])] = "".join(str(item["text"]) for item in spilled)
        dropped |= clipped
        run = [char] if char is not None else []
    return dropped, tails


def _with_tail(word: dict[str, Any], tails: dict[Position, str]) -> dict[str, Any]:
    """Re-attach clipped text to the word it continues (its geometry stays inside the cell)."""
    chars = word.get("chars") or []
    tail = tails.get(_position(chars[-1])) if chars else None
    return {**word, "text": f"{word['text']}{tail}"} if tail else word


def _position(char: dict[str, Any]) -> Position:
    return round(float(char["x0"]), POSITION_DIGITS), round(float(char["top"]), POSITION_DIGITS)


def _continues(previous: dict[str, Any], char: dict[str, Any]) -> bool:
    return (
        abs(float(char["top"]) - float(previous["top"])) <= SAME_BASELINE
        and -RUN_MAX_KERNING <= float(char["x0"]) - float(previous["x1"]) <= RUN_MAX_GAP
    )


def _clipped(
    run: Sequence[dict[str, Any]], borders: Sequence[Rule], chars: Sequence[dict[str, Any]]
) -> set[int]:
    start = _centre_x(run[0])
    top = float(run[0]["top"])
    middle = (top + float(run[0]["bottom"])) / 2
    members = {id(char) for char in run}
    neighbours = [
        float(char["x0"])
        for char in chars
        if id(char) not in members and abs(float(char["top"]) - top) <= SAME_BASELINE
    ]
    limits = sorted(
        rule.x0
        for rule in borders
        if rule.x0 > start and rule.top - VERTICAL_SLACK <= middle <= rule.bottom + VERTICAL_SLACK
    )
    for limit in limits:
        if any(x >= limit - VERTICAL_SLACK for x in neighbours):
            return {id(char) for char in run if _centre_x(char) > limit}
    return set()


def _split_at_borders(
    word: dict[str, Any], borders: Sequence[Rule], tails: dict[Position, str]
) -> list[Word]:
    """Split a word whose characters sit on both sides of a cell border into one word per side.

    Each part gets back any text that was clipped at the border after its last character.
    """
    middle = (float(word["top"]) + float(word["bottom"])) / 2
    cuts = sorted(
        rule.x0
        for rule in borders
        if float(word["x0"]) < rule.x0 < float(word["x1"])
        and rule.top - VERTICAL_SLACK <= middle <= rule.bottom + VERTICAL_SLACK
    )
    chars = word.get("chars") or []
    cuts = [cut for cut in cuts if _separates(chars, cut)]
    if not cuts or not chars:
        return [_word(_with_tail(word, tails))]
    groups: list[list[dict[str, Any]]] = [[] for _ in range(len(cuts) + 1)]
    for char in chars:
        groups[bisect_left(cuts, _centre_x(char))].append(char)
    return [_word(_with_tail(_merge_chars(group), tails)) for group in groups if group]


def _separates(chars: Sequence[dict[str, Any]], cut: float) -> bool:
    """Whether the glyphs on each side of ``cut`` belong to different strings (do not touch)."""
    left = [char for char in chars if _centre_x(char) <= cut]
    right = [char for char in chars if _centre_x(char) > cut]
    if not left or not right:
        return False
    return float(right[0]["x0"]) - float(left[-1]["x1"]) > RUN_MAX_GAP


def _merge_chars(chars: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "chars": list(chars),
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
