"""Retrieval orchestration: resolve the reports, then gather glossary, catalog and report sources.

Order in the context: glossary entries, the report catalog, cross-report conflicts, then report
passages. Reports that fit the token budget are given in full (no retrieval miss is possible),
with the best search matches moved to the front; larger sets fall back to hybrid search within
the resolved reports.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from wellscope.domain.catalog import CatalogEntry, ChunkRecord, ConflictRecord
from wellscope.domain.chunks import GLOSSARY_DOC_ID
from wellscope.domain.rendering import glossary_passage
from wellscope.domain.text import search_terms
from wellscope.retrieval.cards import catalog_card, conflict_card
from wellscope.retrieval.context import SourceBuilder, estimate_tokens
from wellscope.retrieval.glossary_index import GlossaryHit, GlossaryIndex
from wellscope.retrieval.models import (
    Evidence,
    Intent,
    Retrieval,
    RetrievalMode,
    RetrievalQuery,
)
from wellscope.retrieval.ports import ReportIndex
from wellscope.retrieval.search import HybridSearch
from wellscope.retrieval.temporal import resolve

GLOSSARY_LIMIT = 8
SEARCH_LIMIT = 16
USAGE_EXAMPLES = 3
FOCUS_LIMIT = 8
CATALOG_INTENTS = frozenset({Intent.COMPARISON, Intent.AGGREGATION, Intent.CATALOG})
CATALOG_DOC_ID = "catalog"
CONFLICTS_DOC_ID = "conflicts"
GLOSSARY_LABEL = "Glossary"
CATALOG_LABEL = "Report catalog"
CONFLICTS_LABEL = "Data conflicts"

# Code-like names as reports write them: PLATFORM-C, K-28, RIG-2, D18. Plain capitalised
# words are not enough (a question typed in capitals would otherwise count as a domain signal).
_NAME = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b|\b[A-Z]+\d[A-Z0-9]*\b")

Reports = Mapping[str, CatalogEntry]


class Retriever:
    """Gathers the sources a question needs, within the context token budget."""

    def __init__(self, index: ReportIndex, search: HybridSearch, budget_tokens: int) -> None:
        self._index = index
        self._search = search
        self._budget = budget_tokens
        self._glossary: tuple[str | None, GlossaryIndex] | None = None

    def glossary_hits(self, text: str, terms: Sequence[str] = ()) -> list[GlossaryHit]:
        """Glossary entries mentioned in ``text`` or named in ``terms``, without duplicates."""
        glossary = self._glossary_index()
        hits = {hit.entry.id: hit for hit in glossary.mentions(text)}
        for term in terms:
            hit = glossary.lookup(term)
            if hit is not None:
                hits.setdefault(hit.entry.id, hit)
        return list(hits.values())

    def names_corpus_entity(self, text: str) -> bool:
        """Whether ``text`` names something written in the reports (``PLATFORM-C``, ``K-28``)."""
        names = list(dict.fromkeys(_NAME.findall(text)))
        if not names:
            return False
        report_ids = [entry.doc_id for entry in self._index.catalog()]
        return bool(self._index.keyword_search(search_terms(" ".join(names)), report_ids, 1))

    def retrieve(self, query: RetrievalQuery) -> Retrieval:
        """Sources for ``query``."""
        catalog = self._index.catalog()
        resolution = resolve(catalog, query.filters)
        builder = SourceBuilder(self._budget)
        hits = self.glossary_hits(query.question, query.glossary_terms)[:GLOSSARY_LIMIT]
        for hit in hits:
            body = glossary_passage(hit.entry).body
            builder.add(Evidence(GLOSSARY_DOC_ID, GLOSSARY_LABEL, hit.entry.term, None, body))
        glossary_ids = tuple(hit.entry.id for hit in hits)
        if resolution.unmatched:
            return Retrieval(builder.sources, (), glossary_ids, "none", unmatched_filter=True)
        reports = {entry.doc_id: entry for entry in catalog}
        unconstrained = not query.filters.constrained and query.intent is not Intent.GLOSSARY
        if query.intent in CATALOG_INTENTS or unconstrained:
            card = catalog_card(catalog)
            builder.add(Evidence(CATALOG_DOC_ID, CATALOG_LABEL, "All reports", None, card))
        conflicts: tuple[ConflictRecord, ...] = ()
        if query.intent is not Intent.GLOSSARY:
            conflicts = self._add_conflicts(builder, resolution.entries, reports)
        mode = self._add_evidence(builder, query, resolution.entries, reports, bool(hits))
        doc_ids = tuple(entry.doc_id for entry in resolution.entries)
        return Retrieval(builder.sources, doc_ids, glossary_ids, mode, conflicts=conflicts)

    def _add_evidence(
        self,
        builder: SourceBuilder,
        query: RetrievalQuery,
        entries: Sequence[CatalogEntry],
        reports: Reports,
        has_glossary: bool,
    ) -> RetrievalMode:
        doc_ids = [entry.doc_id for entry in entries]
        if query.intent is Intent.CATALOG:
            found = self._search.search(query.texts, doc_ids, FOCUS_LIMIT)
            _add_chunks(builder, self._index.chunks(found), reports)
            return "catalog"
        if query.intent is Intent.GLOSSARY:
            if not has_glossary:
                found = self._search.search(query.texts, [GLOSSARY_DOC_ID], GLOSSARY_LIMIT)
                _add_chunks(builder, self._index.chunks(found), reports)
            examples = self._search.search(query.texts, doc_ids, USAGE_EXAMPLES)
            _add_chunks(builder, self._index.chunks(examples), reports)
            return "glossary"
        position = {doc_id: rank for rank, doc_id in enumerate(doc_ids)}
        chunks = sorted(self._index.document_chunks(doc_ids), key=lambda c: position[c.doc_id])
        if sum(estimate_tokens(chunk.text) for chunk in chunks) <= builder.remaining:
            # The best matches go first so they are not lost in the middle of a long context;
            # the builder skips them when the full reports follow.
            focus = self._index.chunks(self._search.search(query.texts, doc_ids, FOCUS_LIMIT))
            _add_chunks(builder, [*focus, *chunks], reports)
            return "full"
        ranked = self._search.search(query.texts, doc_ids, SEARCH_LIMIT)
        _add_chunks(builder, self._index.chunks(ranked), reports)
        return "search"

    def _add_conflicts(
        self, builder: SourceBuilder, entries: Sequence[CatalogEntry], reports: Reports
    ) -> tuple[ConflictRecord, ...]:
        """Add the conflicts that involve ``entries`` as a source and return them."""
        doc_ids = {entry.doc_id for entry in entries}
        relevant = tuple(
            conflict
            for conflict in self._index.conflicts()
            if any(doc_id in doc_ids for doc_id, _ in conflict.values)
        )
        if relevant:
            labels = {doc_id: entry.label for doc_id, entry in reports.items()}
            card = conflict_card(relevant, labels)
            evidence = Evidence(
                CONFLICTS_DOC_ID, CONFLICTS_LABEL, "Cross-report checks", None, card
            )
            builder.add(evidence)
        return relevant

    def _glossary_index(self) -> GlossaryIndex:
        version = self._index.version()
        if self._glossary is None or self._glossary[0] != version:
            self._glossary = (version, GlossaryIndex(self._index.glossary()))
        return self._glossary[1]


def _add_chunks(builder: SourceBuilder, chunks: Sequence[ChunkRecord], reports: Reports) -> None:
    for chunk in chunks:
        report = reports.get(chunk.doc_id)
        if report is None:
            label = GLOSSARY_LABEL if chunk.doc_id == GLOSSARY_DOC_ID else chunk.doc_id
            evidence = Evidence(chunk.doc_id, label, chunk.title, chunk.page, chunk.text)
        else:
            evidence = Evidence(
                chunk.doc_id, report.label, chunk.title, chunk.page, chunk.text, report.period
            )
        builder.add(evidence)
