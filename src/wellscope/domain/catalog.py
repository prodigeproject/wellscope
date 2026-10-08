"""Corpus-level ingest outputs: the manifest and the data-quality report."""

from __future__ import annotations

import datetime as dt

from pydantic import Field

from wellscope.domain.base import StrictModel
from wellscope.domain.documents import SCHEMA_VERSION, DocumentType, Severity


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
