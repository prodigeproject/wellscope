"""Hybrid search: BM25 keyword ranking fused with vector similarity by reciprocal rank fusion."""

from __future__ import annotations

import logging
from collections.abc import Collection, Sequence

from wellscope.domain.text import search_terms
from wellscope.errors import ModelError
from wellscope.llm.ports import Embedder
from wellscope.retrieval.ports import Hit, ReportIndex

logger = logging.getLogger(__name__)
RRF_K = 60
CANDIDATES = 50


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = RRF_K
) -> list[tuple[str, float]]:
    """Fuse rankings by summing ``1 / (k + rank)``; ties keep first-seen order."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: -item[1])


class HybridSearch:
    """Keyword search, plus semantic search when the index holds vectors from the same model."""

    def __init__(self, index: ReportIndex, embedder: Embedder | None) -> None:
        self._index = index
        self._embedder = embedder

    def search(
        self, texts: Sequence[str], doc_ids: Collection[str] | None, limit: int
    ) -> list[str]:
        """Ids of the chunks most relevant to ``texts``, best first."""
        terms = list(dict.fromkeys(term for text in texts for term in search_terms(text)))
        lexical = self._index.keyword_search(terms, doc_ids, CANDIDATES)
        semantic = self._semantic(texts, doc_ids)
        rankings = [[chunk_id for chunk_id, _ in hits] for hits in (lexical, semantic)]
        return [chunk_id for chunk_id, _ in reciprocal_rank_fusion(rankings)[:limit]]

    def _semantic(self, texts: Sequence[str], doc_ids: Collection[str] | None) -> list[Hit]:
        embedder = self._embedder
        if embedder is None or self._index.embedding_model() != embedder.model:
            return []
        try:
            vector = embedder.embed(["\n".join(texts)])[0]
        except ModelError as error:
            logger.warning("query embedding failed (%s); keyword search only", error.code)
            return []
        return self._index.vector_search(vector, doc_ids, CANDIDATES)
