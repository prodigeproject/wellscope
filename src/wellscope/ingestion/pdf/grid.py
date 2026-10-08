"""Reading ruled forms cell by cell: titled sections, key-value blocks, table rows and grids."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from wellscope.ingestion.pdf.geometry import Box, cluster_lines, words_in
from wellscope.ingestion.pdf.layout import PageLayout
from wellscope.ingestion.pdf.templates import GridSpec, SectionSpec

ROW_TOLERANCE = 2.0
EDGE_TOLERANCE = 2.0


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
        cells = [cell for cell in self.page.cells if _centre_in(cell, self.region)]
        rows: list[list[str]] = []
        for row in _group_rows(cells):
            if self.spec.split_lines:
                rows.extend(_line_rows(self.page, row))
            else:
                rows.append([cell_text(self.page, cell) for cell in row])
        return [row for row in rows if any(row)]


def cell_text(page: PageLayout, cell: Box) -> str:
    """Text of one cell with its visual lines joined by spaces."""
    return " ".join(line.text for line in page.lines(cell))


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


def text_blocks(page: PageLayout, regions: Sequence[Box]) -> list[list[str]]:
    """Line groups for key-value extraction, in reading order.

    Key-value section regions form one block each; other cells form one block per cell, so a
    value never continues into a neighbouring cell; words outside cells form one block per line.
    """
    blocks: list[tuple[float, float, list[str]]] = []
    for region in regions:
        blocks.append((region.top, region.x0, [line.text for line in page.lines(region)]))
    for cell in page.cells:
        if not any(_centre_in(cell, region) for region in regions):
            blocks.append((cell.top, cell.x0, [line.text for line in page.lines(cell)]))
    loose = [
        word
        for word in page.words
        if not any(box.contains(word.center_x, word.center_y) for box in (*page.cells, *regions))
    ]
    blocks.extend((line.top, line.words[0].x0, [line.text]) for line in cluster_lines(loose))
    return [lines for _, _, lines in sorted(blocks, key=lambda block: block[:2]) if lines]


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
    return Box(left, title.bottom, right, min(below, default=page.height))


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
    cell_lines = [page.lines(cell) for cell in row]
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


__all__ = ["Section", "cell_text", "find_sections", "read_grid", "text_blocks", "words_in"]
