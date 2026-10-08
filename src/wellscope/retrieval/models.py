"""What retrieval receives from question analysis and what it hands to answering."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from wellscope.domain.catalog import ConflictRecord

RetrievalMode = Literal["full", "search", "glossary", "catalog", "none"]


class Intent(StrEnum):
    """The kind of answer a question needs; it decides which sources are gathered."""

    GLOSSARY = "glossary"
    REPORT_FACT = "report_fact"
    OPERATIONS = "operations"
    COMPARISON = "comparison"
    AGGREGATION = "aggregation"
    CATALOG = "catalog"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class DocumentFilter:
    """Reports a question refers to; empty fields do not constrain."""

    doc_types: tuple[str, ...] = ()
    report_numbers: tuple[int, ...] = ()
    dates: tuple[dt.date, ...] = ()
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    latest: bool = False

    @property
    def constrained(self) -> bool:
        """Whether any filter is set."""
        return bool(
            self.doc_types
            or self.report_numbers
            or self.dates
            or self.date_from
            or self.date_to
            or self.latest
        )


@dataclass(frozen=True, slots=True)
class RetrievalQuery:
    """A self-contained question plus what analysis extracted from it."""

    question: str
    intent: Intent
    filters: DocumentFilter = field(default_factory=DocumentFilter)
    glossary_terms: tuple[str, ...] = ()
    search_queries: tuple[str, ...] = ()

    @property
    def texts(self) -> tuple[str, ...]:
        """The question and its keyword queries, for search."""
        return (self.question, *self.search_queries)


@dataclass(frozen=True, slots=True)
class Evidence:
    """A passage chosen for the model, before it is numbered; ``period`` is what it covers."""

    doc_id: str
    label: str
    section: str
    page: int | None
    text: str
    period: str = ""


@dataclass(frozen=True, slots=True)
class Source:
    """One numbered piece of evidence shown to the model and cited as ``[S1]``."""

    id: str
    doc_id: str
    label: str
    section: str
    page: int | None
    text: str
    period: str = ""


@dataclass(frozen=True, slots=True)
class Retrieval:
    """Sources for one question; ``unmatched_filter`` means it named reports that do not exist."""

    sources: tuple[Source, ...]
    doc_ids: tuple[str, ...]
    glossary_ids: tuple[str, ...]
    mode: RetrievalMode
    unmatched_filter: bool = False
    conflicts: tuple[ConflictRecord, ...] = ()
