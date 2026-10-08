"""``wellscope ingest``: parse every source file and write the JSON outputs.

This is a composition root: it wires ingestion (parsing) to storage (JSON and the search index).
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import perf_counter

from wellscope.config import Settings
from wellscope.domain.catalog import (
    DocumentQuality,
    GlossarySummary,
    Manifest,
    ManifestDocument,
    QualityReport,
    QuarantinedFile,
)
from wellscope.domain.documents import ReportDocument
from wellscope.domain.glossary import Glossary
from wellscope.errors import WellScopeError
from wellscope.ingestion.discover import Rejected, SourceFile, discover
from wellscope.ingestion.parse import PARSER_VERSION, parse_glossary, parse_pdf
from wellscope.ingestion.quality import cross_document_findings, document_status
from wellscope.storage.json_store import JsonStore

logger = logging.getLogger(__name__)
INDEX_VERSION_LENGTH = 12
PARSE_ERROR = "parse_error"


@dataclass
class IngestResult:
    """What one ingest run produced."""

    manifest: Manifest
    quality: QualityReport
    duration_s: float
    notes: list[str] = field(default_factory=list)


@dataclass
class _Collected:
    documents: list[ReportDocument] = field(default_factory=list)
    glossary: Glossary | None = None
    quarantined: list[QuarantinedFile] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedCorpus:
    """Parse results handed to the index projector."""

    documents: Sequence[ReportDocument]
    glossary: Glossary | None
    quality: QualityReport
    index_version: str


Projector = Callable[[ParsedCorpus], list[str]]


def run_ingest(settings: Settings, project: Projector | None = None) -> IngestResult:
    """Parse ``settings.data_dir`` into ``settings.output_dir``; optionally build the index."""
    started = perf_counter()
    collected = _collect(settings)
    documents = _unique_ids(collected.documents)
    store = JsonStore(settings.output_dir)
    paths = {document.doc_id: store.write_document(document) for document in documents}
    for removed in store.prune_documents(set(paths)):
        collected.notes.append(f"removed stale output {removed}")
    now = datetime.now(UTC)
    quality = QualityReport(
        generated_at=now,
        documents=[_document_quality(document) for document in documents],
        cross_document=cross_document_findings(documents),
    )
    manifest = Manifest(
        generated_at=now,
        parser_version=PARSER_VERSION,
        index_version=_index_version(documents, collected.glossary),
        documents=[_manifest_entry(document, paths[document.doc_id]) for document in documents],
        glossary=_glossary_summary(store, collected.glossary),
        quarantined=collected.quarantined,
    )
    store.write_quality_report(quality)
    store.write_manifest(manifest)
    if project is not None:
        corpus = ParsedCorpus(documents, collected.glossary, quality, manifest.index_version)
        collected.notes.extend(project(corpus))
    return IngestResult(manifest, quality, perf_counter() - started, collected.notes)


def _collect(settings: Settings) -> _Collected:
    collected = _Collected()
    for item in discover(settings.data_dir):
        if isinstance(item, Rejected):
            collected.quarantined.append(QuarantinedFile(**_asdict(item)))
            continue
        try:
            _parse_into(item, collected)
        except Exception as error:  # isolation boundary: one bad file must not stop the run
            code = error.code if isinstance(error, WellScopeError) else PARSE_ERROR
            logger.warning("quarantined %s: %s", item.relative_path, code, exc_info=error)
            detail = str(error).splitlines()[0][:200] if str(error) else type(error).__name__
            collected.quarantined.append(
                QuarantinedFile(source_file=item.relative_path, reason=code, detail=detail)
            )
    return collected


def _parse_into(item: SourceFile, collected: _Collected) -> None:
    if item.is_pdf:
        collected.documents.append(parse_pdf(item.path, item.relative_path, item.sha256))
        return
    glossary = parse_glossary(item.path, item.relative_path, item.sha256)
    if collected.glossary is None:
        collected.glossary = glossary
    else:
        collected.notes.append(f"ignored additional glossary {item.relative_path}")


def _unique_ids(documents: Sequence[ReportDocument]) -> list[ReportDocument]:
    """Drop exact duplicates; disambiguate different files that share a report id."""
    unique: dict[str, ReportDocument] = {}
    for document in documents:
        existing = unique.get(document.doc_id)
        if existing is None:
            unique[document.doc_id] = document
        elif existing.source.sha256 != document.source.sha256:
            doc_id = f"{document.doc_id}-{document.source.sha256[:8]}"
            unique[doc_id] = document.model_copy(update={"doc_id": doc_id})
    return sorted(
        unique.values(), key=lambda doc: (doc.doc_type.value, doc.report.date or doc.doc_id)
    )


def _document_quality(document: ReportDocument) -> DocumentQuality:
    failed = [check.id for check in document.quality if not check.ok]
    return DocumentQuality(
        doc_id=document.doc_id, status=document_status(document.quality), failed_checks=failed
    )


def _manifest_entry(document: ReportDocument, json_path: str) -> ManifestDocument:
    return ManifestDocument(
        doc_id=document.doc_id,
        doc_type=document.doc_type,
        title=document.title,
        well=document.well.name,
        report_number=document.report.number,
        report_date=document.report.date,
        source_file=document.source.relative_path,
        sha256=document.source.sha256,
        page_count=document.source.page_count,
        quality_status=document_status(document.quality),
        json_path=json_path,
    )


def _glossary_summary(store: JsonStore, glossary: Glossary | None) -> GlossarySummary | None:
    if glossary is None:
        return None
    return GlossarySummary(
        source_file=glossary.source.relative_path,
        sha256=glossary.source.sha256,
        entries=len(glossary.entries),
        json_path=store.write_glossary(glossary),
    )


def _index_version(documents: Sequence[ReportDocument], glossary: Glossary | None) -> str:
    parts = sorted(f"{document.doc_id}:{document.source.sha256}" for document in documents)
    parts += [glossary.source.sha256 if glossary else "", PARSER_VERSION]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:INDEX_VERSION_LENGTH]


def _asdict(item: Rejected) -> dict[str, str]:
    return {"source_file": item.relative_path, "reason": item.reason, "detail": item.detail}
