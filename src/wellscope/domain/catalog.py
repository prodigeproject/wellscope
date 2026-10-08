"""Corpus-level ingest outputs: the manifest and the data-quality report."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from pydantic import Field

from wellscope.domain.base import StrictModel
from wellscope.domain.documents import SCHEMA_VERSION, DocumentType, Severity

PERIOD_FORMAT = "%Y-%m-%d %H:%M"


class ManifestDocument(StrictModel):
    """One parsed report as listed in the manifest."""

    doc_id: str
    doc_type: DocumentType
    title: str
    well: str | None = None
    report_number: int | None = None
    report_date: dt.date | None = None
    source_file: str
    sha256: str
    page_count: int
    quality_status: str
    json_path: str


class GlossarySummary(StrictModel):
    """Where the glossary came from and how many entries it holds."""

    source_file: str
    sha256: str
    entries: int
    json_path: str


class QuarantinedFile(StrictModel):
    """A source file that could not be ingested, with a machine-readable reason."""

    source_file: str
    reason: str
    detail: str


class Manifest(StrictModel):
    """Catalog of everything one ingest run produced."""

    schema_version: str = SCHEMA_VERSION
    generated_at: dt.datetime
    parser_version: str
    index_version: str
    documents: list[ManifestDocument] = Field(default_factory=list)
    glossary: GlossarySummary | None = None
    quarantined: list[QuarantinedFile] = Field(default_factory=list)


class ConflictValue(StrictModel):
    """The value one document reports for a conflicting fact."""

    doc_id: str
    value: str


class CrossDocumentFinding(StrictModel):
    """Documents that disagree about the same fact."""

    id: str
    severity: Severity
    detail: str
    values: list[ConflictValue]


class DocumentQuality(StrictModel):
    """Summary of one document's quality checks."""

    doc_id: str
    status: str
    failed_checks: list[str] = Field(default_factory=list)


class QualityReport(StrictModel):
    """Findings within and across documents; source values are never altered."""

    schema_version: str = SCHEMA_VERSION
    generated_at: dt.datetime
    documents: list[DocumentQuality] = Field(default_factory=list)
    cross_document: list[CrossDocumentFinding] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """A report as listed in the search index, with a one-line summary of key facts."""

    doc_id: str
    doc_type: str
    label: str
    title: str
    well: str | None
    rig: str | None
    report_number: int | None
    report_date: dt.date | None
    period_start: dt.datetime | None
    period_end: dt.datetime | None
    quality_status: str
    summary: str

    @property
    def period(self) -> str:
        """The covered period, such as ``2026-07-19 00:00 to 2026-07-20 06:00``, or ``""``."""
        if self.period_start is None or self.period_end is None:
            return ""
        return f"{self.period_start:{PERIOD_FORMAT}} to {self.period_end:{PERIOD_FORMAT}}"


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    """An indexed passage as stored in the search index."""

    chunk_id: str
    doc_id: str
    kind: str
    title: str
    page: int | None
    text: str


@dataclass(frozen=True, slots=True)
class ConflictRecord:
    """A cross-document conflict and the value each document reports."""

    finding_id: str
    detail: str
    values: tuple[tuple[str, str], ...]
