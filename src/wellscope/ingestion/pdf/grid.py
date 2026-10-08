"""Reading ruled forms cell by cell: titled sections, key-value blocks, table rows and grids."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from wellscope.ingestion.pdf.geometry import Box, Word, cluster_lines, words_in
from wellscope.ingestion.pdf.kv import TextLine
from wellscope.ingestion.pdf.layout import PageLayout
from wellscope.ingestion.pdf.templates import GridSpec, SectionSpec

ROW_TOLERANCE = 2.0
EDGE_TOLERANCE = 2.0
GAP_SPLIT = 40.0
MIN_TABLE_CELLS = 2
DATA_SHARE = 0.5
_NUMERIC = re.compile(r"[-+]?\d[\d.,/-]*")
# "Total No. of People: 140" is a caption above the header, not a column name.
_CAPTION = re.compile(r":\s*\S")


@dataclass(frozen=True, slots=True)
class Header:
    """How many leading rows of a table are headers, and one full name per column."""

    rows: int
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Section:
    """A titled region on one page: the cells below a title band."""

    spec: SectionSpec
    page: PageLayout
    title: Box
    region: Box

    @property
    def name(self) -> str:
        """Canonical section name from the template."""
        return self.spec.name

    def text(self) -> str:
        """Visible text of the region, one visual line per line."""
        return self.page.text(self.region)

    def rows(self) -> list[list[str]]:
        """Cell texts of the region, grouped into rows and ordered left to right."""
        rows: list[list[str]] = []
        for row in self._cell_rows():
            if self.spec.split_lines:
                rows.extend(_line_rows(self.page, row))
            else:
                rows.append([cell_text(self.page, cell) for cell in row])
        return [row for row in rows if any(row)]

    def header(self) -> Header:
        """Header rows and the full name of every column.

        Up to the template's number of header rows are read, stopping at the first row that
        looks like data (as many cells as the widest row, mostly numbers). A column's name joins
        the texts of the header cells above it, top to bottom.
        """
        rows = [row for row in self._cell_rows() if any(self._texts(row))]
        if self.spec.split_lines or not rows:
            return Header(0, ())
        widest = max(rows, key=len)
        header: list[list[Box]] = []
        for row in rows[: self.spec.header_rows]:
            if len(row) == len(widest) and _numeric_share(self._texts(row)) >= DATA_SHARE:
                break
            header.append(row)
        if not header:
            return Header(0, ())
        names = [self._column_name(header, column) for column in _leaf_columns(rows)]
        return Header(len(header), _number_repeats(names))

    def _cell_rows(self) -> list[list[Box]]:
        return _group_rows([cell for cell in self.page.cells if _centre_in(cell, self.region)])

    def _texts(self, row: Sequence[Box]) -> list[str]:
        return [cell_text(self.page, cell) for cell in row]

    def _column_name(self, header: Sequence[Sequence[Box]], column: Box) -> str:
        centre = (column.x0 + column.x1) / 2
        parts: list[str] = []
        for row in header:
            cell = next(
                (c for c in row if c.x0 - EDGE_TOLERANCE <= centre <= c.x1 + EDGE_TOLERANCE), None
            )
            text = cell_text(self.page, cell) if cell is not None else ""
            if text and not _CAPTION.search(text) and (not parts or parts[-1] != text):
                parts.append(text)
        return " ".join(parts)


def _leaf_columns(rows: Sequence[Sequence[Box]]) -> list[Box]:
    """One cell per column: cells with no narrower cell under or over them, left to right.

    A header cell over sub-columns (``Prognosis Depth`` over ``m MDDF``/``m TVDSS``) is not a
    column itself; a header cell spanning both header rows (``Lithology``) is, even when the
    table has no data row.
    """
    cells = [cell for row in rows for cell in row]
    leaves: list[Box] = []
    for cell in cells:
        width = cell.x1 - cell.x0
        has_narrower = any(
            other.x1 - other.x0 < width - EDGE_TOLERANCE
            and cell.x0 <= (other.x0 + other.x1) / 2 <= cell.x1
            for other in cells
        )
        known = any(
            abs(cell.x0 - leaf.x0) <= EDGE_TOLERANCE and abs(cell.x1 - leaf.x1) <= EDGE_TOLERANCE
            for leaf in leaves
        )
        if not has_narrower and not known:
            leaves.append(cell)
    return sorted(leaves, key=lambda cell: cell.x0)


def _numeric_share(texts: Sequence[str]) -> float:
    filled = [text for text in texts if text]
    numeric = sum(1 for text in filled if _NUMERIC.fullmatch(text))
    return numeric / len(filled) if filled else 0.0


def _number_repeats(names: Sequence[str]) -> tuple[str, ...]:
    """Columns under one spanning header become ``Interval [1/2]`` and ``Interval [2/2]``."""
    totals = {name: names.count(name) for name in names}
    seen: dict[str, int] = {}
    numbered = []
    for name in names:
        if name and totals[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            numbered.append(f"{name} [{seen[name]}/{totals[name]}]")
        else:
            numbered.append(name)
    return tuple(numbered)


def cell_text(page: PageLayout, cell: Box) -> str:
    """Text of one cell with its visual lines joined by spaces."""
    return " ".join(line.text for line in page.cell_lines(cell))


def find_sections(pages: Sequence[PageLayout], specs: Sequence[SectionSpec]) -> list[Section]:
    """Every titled section on every page, in reading order."""
    found: list[Section] = []
    for page in pages:
        titles = [
            (cell, spec) for cell in page.cells for spec in specs if _is_title(page, cell, spec)
        ]
        boundaries = [cell for cell, _ in titles]
        for cell, spec in titles:
            found.append(Section(spec, page, cell, _region(page, cell, spec, boundaries)))
    return found


def text_blocks(page: PageLayout, merged_regions: Sequence[Box]) -> list[list[TextLine]]:
    """Line groups for key-value extraction, in reading order.

    Every cell is its own block, so a value never continues into a neighbouring cell. A merged
    region (a section whose labels and values sit in different cells) forms a single block.
    Words outside cells form one block per line. Lines are split at wide gaps so a title
    printed beside a label is not read as part of its value.
    """
    blocks: list[tuple[float, float, list[TextLine]]] = []
    for region in merged_regions:
        words = [
            word
            for cell, owned in page.cell_words.items()
            if _centre_in(cell, region)
            for word in owned
        ]
        words += [
            word for word in page.loose_words if region.contains(word.center_x, word.center_y)
        ]
        blocks.append((region.top, region.x0, _fragments(words)))
    for cell, owned in page.cell_words.items():
        if not any(_centre_in(cell, region) for region in merged_regions):
            blocks.append((cell.top, cell.x0, _fragments(owned)))
    loose = [
        word
        for word in page.loose_words
        if not any(region.contains(word.center_x, word.center_y) for region in merged_regions)
    ]
    blocks.extend(
        (line.top, line.words[0].x0, _fragments(line.words)) for line in cluster_lines(loose)
    )
    return [lines for _, _, lines in sorted(blocks, key=lambda block: block[:2]) if lines]


def _fragments(words: Sequence[Word]) -> list[TextLine]:
    fragments: list[TextLine] = []
    for line in cluster_lines(words):
        piece: list[Word] = []
        for word in line.words:
            if piece and _breaks(piece[-1], word):
                fragments.append(_text_line(piece))
                piece = []
            piece.append(word)
        fragments.append(_text_line(piece))
    return fragments


def _breaks(previous: Word, word: Word) -> bool:
    """A wide gap separates two texts, unless it is the gap between a label and its colon or
    between a colon and its (right-aligned) value."""
    if previous.text.endswith(":") or word.text.startswith(":"):
        return False
    return word.x0 - previous.x1 > GAP_SPLIT


def _text_line(words: Sequence[Word]) -> TextLine:
    return TextLine.from_words((word.text, word.x0, word.x1) for word in words)


def page_rows(page: PageLayout) -> list[list[str]]:
    """Every row of two or more non-empty cells on the page (tables of unknown forms)."""
    rows = []
    for row in _group_rows(list(page.cells)):
        texts = [cell_text(page, cell) for cell in row]
        if sum(1 for text in texts if text) >= MIN_TABLE_CELLS:
            rows.append(texts)
    return rows


def read_grid(page: PageLayout, spec: GridSpec) -> list[list[str]]:
    """Header cells followed by the value rows aligned under them (empty when absent)."""
    header = _header_row(page, spec)
    if not header:
        return []
    rows = [[cell_text(page, cell) for cell in header]]
    current = header
    while (below := _aligned_row_below(page, current)) is not None:
        rows.append([cell_text(page, cell) for cell in below])
        current = below
    return rows


def _is_title(page: PageLayout, cell: Box, spec: SectionSpec) -> bool:
    lines = page.lines(cell)
    return len(lines) == 1 and spec.matches(lines[0].text)


def _region(page: PageLayout, title: Box, spec: SectionSpec, boundaries: Sequence[Box]) -> Box:
    left, right = title.x0, title.x1
    if spec.full_row:
        row = [cell for cell in page.cells if abs(cell.top - title.top) <= EDGE_TOLERANCE]
        left, right = min(cell.x0 for cell in row), max(cell.x1 for cell in row)
    below = [
        other.top
        for other in boundaries
        if other.top >= title.bottom - EDGE_TOLERANCE and other.x0 < right and other.x1 > left
    ]
    bottom = min(below, default=page.height)
    if spec.merge_cells:
        bottom = min(bottom, _full_width_bottom(page, title.bottom, left, right))
    return Box(left, title.bottom, right, bottom)


def _full_width_bottom(page: PageLayout, top: float, left: float, right: float) -> float:
    """Bottom of the stack of full-width cells directly below ``top``."""
    bottom = top
    while True:
        below = next(
            (
                cell
                for cell in page.cells
                if abs(cell.top - bottom) <= EDGE_TOLERANCE
                and abs(cell.x0 - left) <= EDGE_TOLERANCE
                and abs(cell.x1 - right) <= EDGE_TOLERANCE
            ),
            None,
        )
        if below is None:
            return bottom
        bottom = below.bottom


def _centre_in(cell: Box, region: Box) -> bool:
    return region.contains((cell.x0 + cell.x1) / 2, (cell.top + cell.bottom) / 2)


def _group_rows(cells: Sequence[Box]) -> list[list[Box]]:
    rows: list[list[Box]] = []
    for cell in sorted(cells, key=lambda box: (box.top, box.x0)):
        if rows and abs(cell.top - rows[-1][0].top) <= ROW_TOLERANCE:
            rows[-1].append(cell)
        else:
            rows.append([cell])
    return rows


def _line_rows(page: PageLayout, row: Sequence[Box]) -> list[list[str]]:
    """Split a band of tall cells into one row per visual line.

    Used where rows have no ruling between them; a line whose first cell is empty continues the
    previous row (wrapped values such as ``Synthetic Based`` / ``Mud (SBM)``).
    """
    cell_lines = [page.cell_lines(cell) for cell in row]
    tops: list[float] = []
    for top in sorted(line.top for lines in cell_lines for line in lines):
        if not tops or top - tops[-1] > ROW_TOLERANCE:
            tops.append(top)
    result: list[list[str]] = []
    for top in tops:
        texts = [
            " ".join(line.text for line in lines if abs(line.top - top) <= ROW_TOLERANCE)
            for lines in cell_lines
        ]
        if result and not texts[0] and any(texts):
            result[-1] = [
                f"{old} {new}".strip() for old, new in zip(result[-1], texts, strict=True)
            ]
        else:
            result.append(texts)
    return result


def _header_row(page: PageLayout, spec: GridSpec) -> list[Box]:
    for row in _group_rows(page.cells):
        texts = [cell_text(page, cell).casefold() for cell in row]
        for start in range(len(row) - len(spec.header) + 1):
            window = texts[start : start + len(spec.header)]
            if all(
                text.startswith(label.casefold())
                for text, label in zip(window, spec.header, strict=True)
            ):
                return row[start : start + len(spec.header)]
    return []


def _aligned_row_below(page: PageLayout, row: Sequence[Box]) -> list[Box] | None:
    bottom = max(cell.bottom for cell in row)
    candidates = [cell for cell in page.cells if abs(cell.top - bottom) <= EDGE_TOLERANCE]
    aligned = []
    for column in row:
        match = next(
            (
                cell
                for cell in candidates
                if abs(cell.x0 - column.x0) <= EDGE_TOLERANCE
                and abs(cell.x1 - column.x1) <= EDGE_TOLERANCE
            ),
            None,
        )
        if match is None:
            return None
        aligned.append(match)
    return aligned


__all__ = [
    "Section",
    "cell_text",
    "find_sections",
    "page_rows",
    "read_grid",
    "text_blocks",
    "words_in",
]
