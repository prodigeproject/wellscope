"""Resolve which reports a question refers to from report numbers, types, dates and recency.

A report covers more than its date: a DDR runs from 00:00 to 06:00 the next day and a DGOS
from 06:00 the previous day, so a day matches the report dated that day first and then every
report whose period overlaps it.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from wellscope.domain.catalog import CatalogEntry
from wellscope.retrieval.models import DocumentFilter


@dataclass(frozen=True, slots=True)
class Resolution:
    """Reports matching a filter; ``unmatched`` means the filter named reports that do not exist."""

    entries: tuple[CatalogEntry, ...]
    unmatched: bool


def resolve(catalog: Sequence[CatalogEntry], filters: DocumentFilter) -> Resolution:
    """Reports matching every given filter."""
    if not filters.constrained:
        return Resolution(tuple(catalog), unmatched=False)
    selected = [entry for entry in catalog if _matches(entry, filters)]
    if filters.latest:
        selected = _latest(selected, filters.doc_types)
    if filters.dates:
        selected.sort(key=lambda entry: entry.report_date not in filters.dates)
    return Resolution(tuple(selected), unmatched=not selected)


def _matches(entry: CatalogEntry, filters: DocumentFilter) -> bool:
    if filters.doc_types and entry.doc_type not in filters.doc_types:
        return False
    if filters.report_numbers and entry.report_number not in filters.report_numbers:
        return False
    if filters.dates and not any(_overlaps(entry, day, day) for day in filters.dates):
        return False
    if filters.date_from or filters.date_to:
        return _overlaps(entry, filters.date_from or dt.date.min, filters.date_to or dt.date.max)
    return True


def _overlaps(entry: CatalogEntry, first: dt.date, last: dt.date) -> bool:
    """Whether the report's date or its covered period touches the days ``first..last``."""
    if entry.report_date is not None and first <= entry.report_date <= last:
        return True
    if entry.period_start is None or entry.period_end is None:
        return False
    start = dt.datetime.combine(first, dt.time.min)
    end = dt.datetime.combine(last, dt.time.max)
    return entry.period_start <= end and start < entry.period_end


def _latest(entries: Sequence[CatalogEntry], doc_types: Sequence[str]) -> list[CatalogEntry]:
    """The newest report overall, or the newest of each requested type."""
    newest = []
    for doc_type in doc_types or (None,):
        candidates = [
            entry
            for entry in entries
            if entry.report_date is not None and doc_type in (None, entry.doc_type)
        ]
        if candidates:
            newest.append(max(candidates, key=_recency))
    return newest


def _recency(entry: CatalogEntry) -> tuple[dt.date, int]:
    return entry.report_date or dt.date.min, entry.report_number or 0
