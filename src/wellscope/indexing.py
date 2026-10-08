"""Project parsed reports into the search index: chunks, embeddings (cached) and SQLite."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from wellscope.domain.chunks import Chunk, document_chunks, glossary_chunks
from wellscope.errors import ModelError
from wellscope.llm.ports import Embedder
from wellscope.pipeline import ParsedCorpus
from wellscope.storage.index_writer import IndexInput, build_index
from wellscope.storage.vector_cache import VectorCache, text_hash

logger = logging.getLogger(__name__)
EMBEDDING_MAX_CHARS = 8000


class IndexProjector:
    """Builds the search index; without a working embedder it supports keyword search only."""

    def __init__(self, path: Path, embedder: Embedder | None, cache: VectorCache) -> None:
        self._path = path
        self._embedder = embedder
        self._cache = cache

    def __call__(self, corpus: ParsedCorpus) -> list[str]:
        """Build the index for ``corpus``; returns notes for the ingest summary."""
        chunks = [chunk for document in corpus.documents for chunk in document_chunks(document)]
        if corpus.glossary is not None:
            chunks.extend(glossary_chunks(corpus.glossary))
        notes: list[str] = []
        vectors = self._vectors(chunks, notes)
        data = IndexInput(
            documents=corpus.documents,
            glossary=corpus.glossary,
            chunks=chunks,
            vectors=vectors,
            embedding_model=self._embedder.model if self._embedder else None,
            index_version=corpus.index_version,
            conflicts=corpus.quality.cross_document,
            quality_status={item.doc_id: item.status for item in corpus.quality.documents},
        )
        build_index(self._path, data)
        mode = "keyword + semantic" if vectors else "keyword only"
        notes.append(f"search index: {len(chunks)} chunks, {mode} search")
        return notes

    def _vectors(self, chunks: Sequence[Chunk], notes: list[str]) -> dict[str, list[float]]:
        """Vector per chunk id, embedding only texts the cache has not seen."""
        if self._embedder is None:
            notes.append("OPENAI_API_KEY is not set: semantic search disabled, keyword search only")
            return {}
        model = self._embedder.model
        texts = {chunk.chunk_id: chunk.text[:EMBEDDING_MAX_CHARS] for chunk in chunks}
        keys = {chunk_id: text_hash(text) for chunk_id, text in texts.items()}
        known = self._cache.get_many(model, sorted(set(keys.values())))
        missing = {
            keys[chunk_id]: text for chunk_id, text in texts.items() if keys[chunk_id] not in known
        }
        if missing:
            try:
                fresh = self._embedder.embed(list(missing.values()))
            except ModelError as error:
                logger.warning("embedding failed (%s); building a keyword-only index", error.code)
                notes.append(f"embeddings unavailable ({error.code}): keyword search only")
                return {}
            added = dict(zip(missing, fresh, strict=True))
            self._cache.put_many(model, added)
            known |= added
        return {chunk_id: known[key] for chunk_id, key in keys.items()}
