"""Build a real search index from domain objects for tests."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from wellscope.domain.catalog import CrossDocumentFinding
from wellscope.domain.chunks import document_chunks, glossary_chunks
from wellscope.domain.documents import ReportDocument
from wellscope.domain.glossary import Glossary
from wellscope.llm.fakes import HashEmbedder
from wellscope.storage.index_reader import SearchIndex
from wellscope.storage.index_writer import IndexInput, build_index


def build_test_index(
    path: Path,
    documents: Sequence[ReportDocument],
    glossary: Glossary | None = None,
    *,
    embedder: HashEmbedder | None = None,
    conflicts: Sequence[CrossDocumentFinding] = (),
    version: str = "v1",
) -> SearchIndex:
    chunks = [chunk for document in documents for chunk in document_chunks(document)]
    if glossary is not None:
        chunks += glossary_chunks(glossary)
    vectors = embedder.embed([chunk.text for chunk in chunks]) if embedder else []
    data = IndexInput(
        documents=documents,
        glossary=glossary,
        chunks=chunks,
        vectors=dict(zip((chunk.chunk_id for chunk in chunks), vectors, strict=False)),
        embedding_model=embedder.model if embedder else None,
        index_version=version,
        conflicts=conflicts,
        quality_status={},
    )
    build_index(path, data)
    return SearchIndex(path)
