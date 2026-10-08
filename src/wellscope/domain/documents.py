"""Parsed report documents: the JSON contract written by ``wellscope ingest``."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"
Severity = Literal["info", "warning", "error"]


class DocumentType(StrEnum):
    """Report families recognised by content signature."""

    DDR = "DDR"
    DGOS = "DGOS"
    GENERIC = "GENERIC"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParserInfo(_Model):
    """Which parser and form template produced the document."""

    name: str
    version: str
    template: str | None = None


class SourceInfo(_Model):
    """Provenance of the source file."""

    file_name: str
    relative_path: str
    sha256: str
    page_count: int
    parser: ParserInfo


class WellInfo(_Model):
    """Identity of the well and rig the report is about."""

    name: str | None = None
    wellbore: str | None = None
    field: str | None = None
    block: str | None = None
    region: str | None = None
    rig: str | None = None
    operator: str | None = None


class ReportInfo(_Model):
    """Report number, date and the operational period it covers."""

    number: int | None = None
    date: dt.date | None = None
    period_start: dt.datetime | None = None
    period_end: dt.datetime | None = None


class FieldValue(_Model):
    """One labelled value; ``raw`` is the verbatim source text."""

    label: str
    section: str
    raw: str
    value: float | None = None
    unit: str | None = None
    date: dt.date | None = None
    page: int


class Operation(_Model):
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


class TimedNote(_Model):
    """A narrative entry with an optional time range (next-day operations)."""

    start: str | None = None
    end: str | None = None
    description: str
    page: int


class NextDayOperations(_Model):
    """Early-morning operations of the following day, appended to the last table row."""

    date: dt.date | None = None
    entries: list[TimedNote] = Field(default_factory=list)


class Remark(_Model):
    """A numbered remark."""

    number: int
    text: str


class Table(_Model):
    """A ruled table read cell by cell; the first ``header_rows`` rows are headers."""

    section: str
    page: int
    header_rows: int = 0
    rows: list[list[str]] = Field(default_factory=list)


class SectionText(_Model):
    """Visible text of a key-value section, line by line."""

    section: str
    page: int
    text: str


class PageText(_Model):
    """Visible text of a page and the share of characters that were visible."""

    number: int
    text: str
    visible_ratio: float


class QualityCheck(_Model):
    """Outcome of one data-quality check."""

    id: str
    ok: bool
    severity: Severity
    detail: str


class ReportDocument(_Model):
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
