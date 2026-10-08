"""Search-index chunks: one per passage, plus normalised text for the keyword index."""

from __future__ import annotations

from dataclasses import dataclass

from wellscope.domain.documents import ReportDocument
from wellscope.domain.glossary import Glossary
from wellscope.domain.rendering import (
    Passage,
    document_passages,
    glossary_passage,
    passage_text,
)
from wellscope.domain.text import normalize_for_index

GLOSSARY_DOC_ID = "glossary"
# Bump when passage or chunk text changes, so indexes built from older text are replaced.
CHUNK_FORMAT_VERSION = "4"


@dataclass(frozen=True, slots=True)
class Chunk:
    """An indexed passage: ``text`` is what the model reads, ``index_text`` what FTS matches."""

    chunk_id: str
    doc_id: str
    kind: str
    title: str
    page: int | None
    text: str
    index_text: str


def document_chunks(document: ReportDocument) -> list[Chunk]:
    """One chunk per passage of a report."""
    return [
        _chunk(document.doc_id, passage, passage_text(document, passage))
        for passage in document_passages(document)
    ]


def glossary_chunks(glossary: Glossary) -> list[Chunk]:
    """One chunk per glossary entry."""
    chunks = []
    for entry in glossary.entries:
        passage = glossary_passage(entry)
        chunks.append(_chunk(GLOSSARY_DOC_ID, passage, f"[Glossary]\n{passage.body}"))
    return chunks


def _chunk(doc_id: str, passage: Passage, text: str) -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}:{passage.key}",
        doc_id=doc_id,
        kind=passage.kind,
        title=passage.title,
        page=passage.page,
        text=text,
        index_text=normalize_for_index(text),
    )
