"""Table headers: how many rows are headers, and the full name of every column.

Report tables use multi-row headers (``Prognosis Depth`` over ``m MDDF`` and ``m TVDSS``),
header cells spanning several columns (a depth interval over its start and end) and caption
rows (``Total No. of People: 140``). Reading the header rows as plain rows misaligns them with
the data, so each column is named from the header cells above it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from wellscope.ingestion.pdf.geometry import Box

EDGE_TOLERANCE = 2.0
DATA_SHARE = 0.5
_NUMERIC = re.compile(r"[-+]?\d[\d.,/-]*")
_CAPTION = re.compile(r":\s*\S")

TextOf = Callable[[Box], str]


@dataclass(frozen=True, slots=True)
class Header:
    """How many leading rows of a table are headers, and one full name per column."""

    rows: int
    columns: tuple[str, ...]


def table_header(rows: Sequence[Sequence[Box]], max_rows: int, text_of: TextOf) -> Header:
    """Header of a table given as rows of cells (top to bottom, each left to right).

    Up to ``max_rows`` header rows are read, stopping at the first row that looks like data
    (as many cells as the widest row, mostly numbers); templates may over-count them.
    """
    filled = [row for row in rows if any(text_of(cell) for cell in row)]
    if not filled:
        return Header(0, ())
    widest = max(len(row) for row in filled)
    header: list[Sequence[Box]] = []
    for row in filled[:max_rows]:
        if len(row) == widest and _numeric_share([text_of(cell) for cell in row]) >= DATA_SHARE:
            break
        header.append(row)
    if not header:
        return Header(0, ())
    names = [_column_name(header, column, text_of) for column in _leaf_columns(filled)]
    return Header(len(header), _number_repeats(names))


def _column_name(header: Sequence[Sequence[Box]], column: Box, text_of: TextOf) -> str:
    """Texts of the header cells over ``column``, top to bottom; captions are skipped."""
    centre = (column.x0 + column.x1) / 2
    parts: list[str] = []
    for row in header:
        cell = next(
            (c for c in row if c.x0 - EDGE_TOLERANCE <= centre <= c.x1 + EDGE_TOLERANCE), None
        )
        text = text_of(cell) if cell is not None else ""
        if text and not _CAPTION.search(text) and (not parts or parts[-1] != text):
            parts.append(text)
    return " ".join(parts)


def _leaf_columns(rows: Sequence[Sequence[Box]]) -> list[Box]:
    """One cell per column: cells with no narrower cell under or over them, left to right.

    A header cell over sub-columns is not a column itself; a header cell spanning both header
    rows (``Lithology`` beside ``Direct Fluorescence``) is, even when there is no data row.
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
