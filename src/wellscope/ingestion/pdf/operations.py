"""The daily operations table: rows spanning pages, wrapped descriptions, next-day narrative.

Columns come from the vertical rulings under the header (headers are centred, values are not);
a row starts where the first column holds a time range, and lines without one continue the
description of the previous row, including across page breaks.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from wellscope.domain.dates import parse_date
from wellscope.domain.documents import NextDayOperations, Operation, TimedNote
from wellscope.domain.numbers import parse_number
from wellscope.domain.timeranges import parse_time_range
from wellscope.ingestion.pdf.geometry import Box, Line, column_bounds, split_into_columns
from wellscope.ingestion.pdf.grid import Section
from wellscope.ingestion.pdf.layout import PageLayout
from wellscope.ingestion.pdf.templates import OperationsSpec

OPERATIONS_KIND = "operations"
HEADER_PROBE = 4.0
DEFAULT_HEADER_DEPTH = 30.0
RULE_TOLERANCE = 3.0
FOOTER_ZONE = 0.9
DATE_LINE_MAX_LENGTH = 30
_NEXT_DAY_TIME = re.compile(r"(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2})\s*hrs?", re.IGNORECASE)


@dataclass
class _Row:
    cells: dict[str, str]
    page: int
    lines: list[str] = field(default_factory=list)


def parse_operations(
    sections: Sequence[Section], spec: OperationsSpec, report_date: date | None
) -> tuple[list[Operation], NextDayOperations | None]:
    """Operations of the report day and the next-day narrative appended to the last row."""
    rows: list[_Row] = []
    for section in sections:
        if section.spec.kind == OPERATIONS_KIND:
            _read_section(section, spec, rows)
    if not rows:
        return [], None
    rows[-1].lines, next_day_lines = split_next_day(rows[-1].lines, spec.next_day_separator)
    operations = [_operation(seq, row, report_date, spec) for seq, row in enumerate(rows, 1)]
    next_day = (
        parse_next_day(next_day_lines, report_date, rows[-1].page) if next_day_lines else None
    )
    return operations, next_day


def split_next_day(lines: Sequence[str], separator: str) -> tuple[list[str], list[str]]:
    """Split a description at the separator line that introduces the next day."""
    pattern = re.compile(separator)
    for index, line in enumerate(lines):
        if pattern.fullmatch(line.strip()):
            return list(lines[:index]), list(lines[index + 1 :])
    return list(lines), []


def parse_next_day(lines: Sequence[str], report_date: date | None, page: int) -> NextDayOperations:
    """Read ``20th July 2026`` followed by ``HH:MM - HH:MM hrs`` blocks of text."""
    day: date | None = None
    entries: list[tuple[str | None, str | None, list[str]]] = []
    for line in (text.strip() for text in lines):
        if not line:
            continue
        if day is None and not entries and len(line) <= DATE_LINE_MAX_LENGTH:
            day = parse_date(line)
            if day is not None:
                continue
        timed = _NEXT_DAY_TIME.fullmatch(line)
        span = parse_time_range(timed[1]) if timed else None
        if span is not None:
            entries.append((span.start, span.end, []))
        elif entries:
            entries[-1][2].append(line)
        else:
            entries.append((None, None, [line]))
    if day is None and report_date is not None:
        day = report_date + timedelta(days=1)
    notes = [
        TimedNote(start=start, end=end, description="\n".join(text), page=page)
        for start, end, text in entries
    ]
    return NextDayOperations(date=day, entries=notes)


def _read_section(section: Section, spec: OperationsSpec, rows: list[_Row]) -> None:
    page, region = section.page, section.region
    header = _header_line(page, region, spec.anchor)
    if header is None:
        return
    bounds = column_bounds(
        page.vertical_rules, header.top, header.top + HEADER_PROBE, region.x0, region.x1
    )
    if not bounds:
        return
    body_top = _header_bottom(page, header.top, bounds)
    names = _column_names(page, bounds, header.top, body_top, spec.columns)
    body = Box(region.x0, body_top, region.x1, _footer_top(page, spec.footer_pattern, region))
    for line in page.lines(body):
        values = split_into_columns(line, bounds)
        cells = {name: value for name, value in zip(names, values, strict=True) if name}
        if parse_time_range(cells.get("time_range", "")) is not None:
            rows.append(_Row(cells, page.number, [cells.get("description", "")]))
        elif rows and cells.get("description"):
            rows[-1].lines.append(cells["description"])


def _header_line(page: PageLayout, region: Box, anchor: str) -> Line | None:
    expected = " ".join(anchor.split()).casefold()
    return next(
        (line for line in page.lines(region) if line.text.casefold().startswith(expected)), None
    )


def _header_bottom(page: PageLayout, top: float, bounds: Sequence[tuple[float, float]]) -> float:
    left, right = bounds[0][0], bounds[-1][1]
    rules = [
        rule.top
        for rule in page.horizontal_rules
        if rule.top > top + RULE_TOLERANCE
        and rule.x0 <= left + RULE_TOLERANCE
        and rule.x1 >= right - RULE_TOLERANCE
    ]
    return min(rules, default=top + DEFAULT_HEADER_DEPTH)


def _column_names(
    page: PageLayout,
    bounds: Sequence[tuple[float, float]],
    top: float,
    bottom: float,
    columns: dict[str, str],
) -> list[str | None]:
    header = Box(bounds[0][0], top - RULE_TOLERANCE, bounds[-1][1], bottom)
    labels = [""] * len(bounds)
    for line in page.lines(header):
        for index, text in enumerate(split_into_columns(line, bounds)):
            labels[index] = f"{labels[index]} {text}".strip()
    return [
        next((name for prefix, name in columns.items() if label.startswith(prefix)), None)
        for label in labels
    ]


def _footer_top(page: PageLayout, pattern: str, region: Box) -> float:
    footer = re.compile(pattern)
    tops = [
        word.top
        for word in page.words
        if word.top > page.height * FOOTER_ZONE and footer.fullmatch(word.text)
    ]
    return min([*tops, region.bottom])


def _operation(seq: int, row: _Row, report_date: date | None, spec: OperationsSpec) -> Operation:
    span = parse_time_range(row.cells["time_range"])
    if span is None:  # rows are only created for valid ranges
        raise ValueError(f"row {seq} has no time range")
    hours = parse_number(row.cells.get("hours", ""))
    return Operation(
        seq=seq,
        date=report_date,
        start=span.start,
        end=span.end,
        hours=hours if hours is not None else span.hours,
        phase_code=row.cells.get("phase_code") or None,
        activity_code=row.cells.get("activity_code") or None,
        productive_code=row.cells.get("productive_code") or None,
        npt=row.cells.get("npt", "").strip().casefold() == spec.npt_flag.casefold(),
        rig_status=row.cells.get("rig_status") or None,
        md_from_m=parse_number(row.cells.get("md_from_m", "")),
        description="\n".join(line for line in row.lines if line).strip(),
        page=row.page,
    )
