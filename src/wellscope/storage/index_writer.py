"""Build the SQLite search index from parsed documents.

The index is written to a temporary file and swapped in atomically, so a running server never
reads a half-built index; it notices the new ``index_version`` on its next request.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from array import array
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib.resources import files
from pathlib import Path

from wellscope.domain.catalog import CrossDocumentFinding
from wellscope.domain.chunks import Chunk
from wellscope.domain.documents import ReportDocument
from wellscope.domain.glossary import Glossary, GlossaryEntry
from wellscope.domain.rendering import catalog_summary, document_label, render_document

INDEX_SCHEMA_VERSION = "1"
REPLACE_ATTEMPTS = 10
REPLACE_DELAY_S = 0.3

Row = tuple[object, ...]


@dataclass(frozen=True)
class IndexInput:
    """Everything the index is built from."""

    documents: Sequence[ReportDocument]
    glossary: Glossary | None
    chunks: Sequence[Chunk]
    vectors: Mapping[str, Sequence[float]]
    embedding_model: str | None
    index_version: str
    conflicts: Sequence[CrossDocumentFinding]
    quality_status: Mapping[str, str]


def build_index(path: Path, data: IndexInput) -> None:
    """Write the index for ``data`` and atomically replace the file at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.unlink(missing_ok=True)
    connection = sqlite3.connect(temporary)
    try:
        schema = (files("wellscope.storage") / "schema.sql").read_text(encoding="utf-8")
        connection.executescript(schema)
        _insert_meta(connection, data)
        _insert_documents(connection, data)
        if data.glossary is not None:
            _insert_glossary(connection, data.glossary)
        _insert_chunks(connection, data.chunks, data.vectors)
        _insert_quality(connection, data)
        connection.execute("INSERT INTO chunks_fts (chunks_fts) VALUES ('rebuild')")
        connection.commit()
    finally:
        connection.close()
    _replace(temporary, path)


def _insert_meta(connection: sqlite3.Connection, data: IndexInput) -> None:
    dimensions = len(next(iter(data.vectors.values()))) if data.vectors else 0
    meta = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "index_version": data.index_version,
        "built_at": datetime.now(UTC).isoformat(),
        "embedding_model": data.embedding_model if data.vectors else "",
        "embedding_dimensions": str(dimensions),
    }
    connection.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", meta.items())


def _insert_documents(connection: sqlite3.Connection, data: IndexInput) -> None:
    for document in data.documents:
        status = data.quality_status.get(document.doc_id, "ok")
        connection.execute(
            "INSERT INTO documents (doc_id, doc_type, title, label, well, rig, report_number, "
            "report_date, period_start, period_end, source_file, page_count, quality_status, "
            "summary, rendered) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _document_row(document, status),
        )
        connection.executemany(
            "INSERT INTO fields (doc_id, key, label, section, raw, value, unit, date, page) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _field_rows(document),
        )
        connection.executemany(
            "INSERT INTO operations (doc_id, seq, op_date, start_time, end_time, hours, "
            "phase_code, activity_code, productive_code, npt, rig_status, md_from_m, "
            "description, page) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _operation_rows(document),
        )


def _insert_glossary(connection: sqlite3.Connection, glossary: Glossary) -> None:
    connection.executemany(
        "INSERT INTO glossary (id, term, aliases, expansion, description, status, senses, "
        "category, source_row) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [_glossary_row(entry) for entry in glossary.entries],
    )


def _insert_chunks(
    connection: sqlite3.Connection, chunks: Sequence[Chunk], vectors: Mapping[str, Sequence[float]]
) -> None:
    connection.executemany(
        "INSERT INTO chunks (chunk_id, doc_id, kind, title, page, text, index_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [_chunk_row(chunk) for chunk in chunks],
    )
    connection.executemany(
        "INSERT INTO chunk_vectors (chunk_id, vector) VALUES (?, ?)",
        [
            (chunk.chunk_id, array("f", vectors[chunk.chunk_id]).tobytes())
            for chunk in chunks
            if chunk.chunk_id in vectors
        ],
    )


def _insert_quality(connection: sqlite3.Connection, data: IndexInput) -> None:
    connection.executemany(
        "INSERT INTO quality_findings (doc_id, check_id, severity, ok, detail) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (document.doc_id, check.id, check.severity, int(check.ok), check.detail)
            for document in data.documents
            for check in document.quality
        ],
    )
    connection.executemany(
        "INSERT INTO conflicts (finding_id, detail, doc_id, value) VALUES (?, ?, ?, ?)",
        [
            (finding.id, finding.detail, value.doc_id, value.value)
            for finding in data.conflicts
            for value in finding.values
        ],
    )


def _document_row(document: ReportDocument, quality_status: str) -> Row:
    report = document.report
    return (
        document.doc_id,
        document.doc_type.value,
        document.title,
        document_label(document),
        document.well.name,
        document.well.rig,
        report.number,
        _iso(report.date),
        _iso(report.period_start),
        _iso(report.period_end),
        document.source.relative_path,
        document.source.page_count,
        quality_status,
        catalog_summary(document),
        render_document(document),
    )


def _field_rows(document: ReportDocument) -> list[Row]:
    return [
        (
            document.doc_id,
            key,
            field.label,
            field.section,
            field.raw,
            field.value,
            field.unit,
            _iso(field.date),
            field.page,
        )
        for key, field in document.fields.items()
    ]


def _operation_rows(document: ReportDocument) -> list[Row]:
    return [
        (
            document.doc_id,
            op.seq,
            _iso(op.date),
            op.start,
            op.end,
            op.hours,
            op.phase_code,
            op.activity_code,
            op.productive_code,
            int(op.npt),
            op.rig_status,
            op.md_from_m,
            op.description,
            op.page,
        )
        for op in document.operations
    ]


def _chunk_row(chunk: Chunk) -> Row:
    return (
        chunk.chunk_id,
        chunk.doc_id,
        chunk.kind,
        chunk.title,
        chunk.page,
        chunk.text,
        chunk.index_text,
    )


def _glossary_row(entry: GlossaryEntry) -> Row:
    return (
        entry.id,
        entry.term,
        json.dumps(list(entry.aliases)),
        entry.expansion,
        entry.description,
        entry.status.value,
        json.dumps(list(entry.senses)),
        entry.category,
        entry.source_row,
    )


def _iso(value: date | None) -> str | None:
    """ISO text for a date or datetime (``datetime`` is a ``date`` subclass)."""
    return value.isoformat() if value else None


def _replace(temporary: Path, target: Path) -> None:
    """Swap the new index in; on Windows a reader may briefly hold the old file open."""
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(temporary, target)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_DELAY_S)
