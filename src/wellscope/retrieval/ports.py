"""Port for the search index; ``wellscope.storage.index_reader.SearchIndex`` implements it."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Protocol

from wellscope.domain.catalog import CatalogEntry, ChunkRecord, ConflictRecord
from wellscope.domain.glossary import GlossaryEntry

Hit = tuple[str, float]


class ReportIndex(Protocol):
    """Read-only queries over the reports, glossary and their chunks."""

    def available(self) -> bool:
        """Whether an index has been built."""
        ...

    def version(self) -> str | None:
        """Changes whenever ingest rebuilds the index."""
        ...

    def catalog(self) -> list[CatalogEntry]:
        """Every report, oldest first."""
        ...

    def glossary(self) -> list[GlossaryEntry]:
        """Every glossary entry."""
        ...

    def conflicts(self) -> list[ConflictRecord]:
        """Facts that reports state differently."""
        ...

    def embedding_model(self) -> str | None:
        """Model of the stored chunk vectors, or ``None`` without vectors."""
        ...

    def rendered(self, doc_ids: Collection[str]) -> dict[str, str]:
        """Full markdown of reports."""
        ...

    def chunks(self, chunk_ids: Sequence[str]) -> list[ChunkRecord]:
        """Chunks by id, in request order."""
        ...

    def document_chunks(self, doc_ids: Collection[str]) -> list[ChunkRecord]:
        """Every chunk of the given reports, in reading order."""
        ...

    def keyword_search(
        self, terms: Sequence[str], doc_ids: Collection[str] | None, limit: int
    ) -> list[Hit]:
        """BM25 ranking of chunks containing any term."""
        ...

    def vector_search(
        self, vector: Sequence[float], doc_ids: Collection[str] | None, limit: int
    ) -> list[Hit]:
        """Cosine ranking of chunks against a query vector."""
        ...
