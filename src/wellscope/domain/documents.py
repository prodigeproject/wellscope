"""Parsed report documents: the JSON contract written by ``wellscope ingest``."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Literal

from pydantic import Field

from wellscope.domain.base import StrictModel

SCHEMA_VERSION = "1.0"
Severity = Literal["info", "warning", "error"]


class DocumentType(StrEnum):
    """Report families recognised by content signature."""

    DDR = "DDR"
    DGOS = "DGOS"
    GENERIC = "GENERIC"


class ParserInfo(StrictModel):
    """Which parser and form template produced the document."""

    name: str
    version: str
    template: str | None = None


class SourceInfo(StrictModel):
    """Provenance of the source file."""

    file_name: str
    relative_path: str
    sha256: str
    page_count: int
    parser: ParserInfo


class WellInfo(StrictModel):
    """Identity of the well and rig the report is about."""

    name: str | None = None
    wellbore: str | None = None
    field: str | None = None
    block: str | None = None
    region: str | None = None
    rig: str | None = None
    operator: str | None = None


class ReportInfo(StrictModel):
    """Report number, date and the operational period it covers."""

    number: int | None = None
    date: dt.date | None = None
    period_start: dt.datetime | None = None
    period_end: dt.datetime | None = None


class FieldValue(StrictModel):
    """One labelled value; ``raw`` is the verbatim source text."""

    label: str
    section: str
    raw: str
    value: float | None = None
    unit: str | None = None
    date: dt.date | None = None
    page: int


class Operation(StrictModel):
    """One row of the daily operations table."""

    seq: int
    date: dt.date | None = None
    start: str
    end: str
    hours: float | None = None
    phase_code: str | None = None
    activity_code: str | None = None
    productive_code: str | None = None
    npt: bool = False
    rig_status: str | None = None
    md_from_m: float | None = None
    description: str
    page: int


class TimedNote(StrictModel):
    """A narrative entry with an optional time range (next-day operations)."""

    start: str | None = None
    end: str | None = None
    description: str
    page: int


class NextDayOperations(StrictModel):
    """Early-morning operations of the following day, appended to the last table row."""

    date: dt.date | None = None
    entries: list[TimedNote] = Field(default_factory=list)


class Remark(StrictModel):
    """A numbered remark."""

    number: int
    text: str


class Table(StrictModel):
    """A ruled table read cell by cell; the first ``header_rows`` rows are headers.

    ``columns`` names every column with its full header (``Prognosis Depth m TVDSS``), combining
    multi-row headers and cells that span several columns; it is empty without a header.
    """

    section: str
    page: int
    header_rows: int = 0
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class SectionText(StrictModel):
    """Visible text of a key-value section, line by line."""

    section: str
    page: int
    text: str


class PageText(StrictModel):
    """Visible text of a page and the share of characters that were visible."""

    number: int
    text: str
    visible_ratio: float


class QualityCheck(StrictModel):
    """Outcome of one data-quality check."""

    id: str
    ok: bool
    severity: Severity
    detail: str


class ReportDocument(StrictModel):
    """A parsed report: typed fields, operations, tables, page text and quality checks."""

    schema_version: str = SCHEMA_VERSION
    doc_id: str
    doc_type: DocumentType
    title: str
    source: SourceInfo
    well: WellInfo = Field(default_factory=WellInfo)
    report: ReportInfo = Field(default_factory=ReportInfo)
    fields: dict[str, FieldValue] = Field(default_factory=dict)
    operations: list[Operation] = Field(default_factory=list)
    next_day: NextDayOperations | None = None
    remarks: list[Remark] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    sections: list[SectionText] = Field(default_factory=list)
    pages: list[PageText] = Field(default_factory=list)
    quality: list[QualityCheck] = Field(default_factory=list)

    def field_raw(self, key: str) -> str | None:
        """Raw text of a typed field, or ``None`` when absent."""
        field = self.fields.get(key)
        return field.raw if field is not None else None
