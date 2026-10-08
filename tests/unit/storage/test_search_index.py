from __future__ import annotations

from datetime import date
from pathlib import Path

from tests.support.documents import make_document, make_glossary
from wellscope.domain.catalog import ConflictValue, CrossDocumentFinding
from wellscope.domain.chunks import document_chunks, glossary_chunks
from wellscope.domain.documents import FieldValue, ReportDocument
from wellscope.domain.glossary import Glossary, GlossaryEntry
from wellscope.domain.text import search_terms
from wellscope.llm.fakes import HashEmbedder
from wellscope.storage.index_reader import SearchIndex
from wellscope.storage.index_writer import IndexInput, build_index

NPT = GlossaryEntry(
    id="gl-npt",
    term="NPT",
    aliases=("NPT", "N.P.T."),
    expansion="Non-Productive Time",
    source_row=1,
)
FIRST, SECOND = "ddr-well-a-1-0012", "ddr-well-a-1-0013"


def corpus() -> list[ReportDocument]:
    first = make_document()
    hole = FieldValue(label="Hole size", section="depth_days", raw='17½"', page=1)
    second = first.model_copy(
        update={
            "doc_id": SECOND,
            "report": first.report.model_copy(update={"number": 13, "date": date(2026, 1, 15)}),
            "fields": {**first.fields, "hole_size": hole},
        }
    )
    return [first, second]


def build(
    path: Path, *, version: str = "v1", embed: bool = True, glossary: Glossary | None = None
) -> SearchIndex:
    documents = corpus()
    glossary = glossary or make_glossary(NPT)
    chunks = [chunk for document in documents for chunk in document_chunks(document)]
    chunks += glossary_chunks(glossary)
    embedder = HashEmbedder()
    vectors = embedder.embed([chunk.text for chunk in chunks]) if embed else []
    conflict = CrossDocumentFinding(
        id="spud_date",
        severity="warning",
        detail="Spud date differs",
        values=[ConflictValue(doc_id=FIRST, value="1"), ConflictValue(doc_id=SECOND, value="2")],
    )
    data = IndexInput(
        documents=documents,
        glossary=glossary,
        chunks=chunks,
        vectors=dict(zip((chunk.chunk_id for chunk in chunks), vectors, strict=False)),
        embedding_model=embedder.model,
        index_version=version,
        conflicts=[conflict],
        quality_status={FIRST: "warning"},
    )
    build_index(path, data)
    return SearchIndex(path)


def test_a_missing_index_is_unavailable(tmp_path: Path) -> None:
    index = SearchIndex(tmp_path / "missing.db")
    assert not index.available()
    assert index.version() is None


def test_catalog_lists_reports_with_labels_summaries_and_quality(tmp_path: Path) -> None:
    catalog = build(tmp_path / "index.db").catalog()
    assert [entry.doc_id for entry in catalog] == [FIRST, SECOND]
    first = catalog[0]
    assert first.label == "DDR #12 (2026-01-14)"
    assert first.report_date == date(2026, 1, 14)
    assert "Daily Cost: 250,000.00" in first.summary
    assert [entry.quality_status for entry in catalog] == ["warning", "ok"]


def test_rendered_reports_and_chunks_come_back_in_request_order(tmp_path: Path) -> None:
    index = build(tmp_path / "index.db")
    assert index.rendered([FIRST])[FIRST].startswith("# DDR #12 (2026-01-14)")
    wanted = [f"{SECOND}:fields:depth_days", "missing", "glossary:gl-npt"]
    assert [chunk.chunk_id for chunk in index.chunks(wanted)] == [wanted[0], wanted[2]]


def test_keyword_search_keeps_fractional_hole_sizes_whole(tmp_path: Path) -> None:
    hits = build(tmp_path / "index.db").keyword_search(search_terms('17½" hole'), None, 5)
    assert hits[0][0] == f"{SECOND}:fields:depth_days"


def test_keyword_search_filters_documents_and_quotes_query_syntax(tmp_path: Path) -> None:
    index = build(tmp_path / "index.db")
    hits = index.keyword_search(['cost"', "OR", "reamer*"], [FIRST], 10)
    assert hits
    assert all(chunk_id.startswith(FIRST) for chunk_id, _ in hits)
    assert index.keyword_search([], None, 10) == []


def test_vector_search_ranks_the_closest_chunk_first(tmp_path: Path) -> None:
    index = build(tmp_path / "index.db")
    query = HashEmbedder().embed(["attempt to open reamer"])[0]
    best_id, best_score = index.vector_search(query, [SECOND], 3)[0]
    assert best_id.startswith(f"{SECOND}:operation")
    assert 0 < best_score <= 1
    assert index.vector_search([1.0, 0.0], None, 3) == []
    assert index.embedding_model() == "hash-256"


def test_an_index_without_vectors_supports_keyword_search_only(tmp_path: Path) -> None:
    index = build(tmp_path / "index.db", embed=False)
    assert index.embedding_model() is None
    assert index.vector_search(HashEmbedder().embed(["reamer"])[0], None, 3) == []
    assert index.keyword_search(["reamer"], None, 3)


def test_glossary_and_conflicts_round_trip(tmp_path: Path) -> None:
    index = build(tmp_path / "index.db")
    assert index.glossary() == [NPT]
    conflict = index.conflicts()[0]
    assert conflict.detail == "Spud date differs"
    assert conflict.values == ((FIRST, "1"), (SECOND, "2"))


def test_rebuilding_swaps_the_file_and_refreshes_cached_data(tmp_path: Path) -> None:
    path = tmp_path / "index.db"
    index = build(path, version="v1")
    assert index.glossary() == [NPT]
    other = NPT.model_copy(update={"id": "gl-rop", "term": "ROP", "aliases": ("ROP",)})
    build(path, version="v2", glossary=make_glossary(other))
    assert index.version() == "v2"
    assert index.glossary() == [other]
    assert [p.name for p in tmp_path.iterdir()] == ["index.db"]


def test_document_chunks_come_in_reading_order(tmp_path: Path) -> None:
    chunks = build(tmp_path / "index.db").document_chunks([SECOND])
    assert chunks
    assert {chunk.doc_id for chunk in chunks} == {SECOND}
    assert chunks[0].chunk_id == f"{SECOND}:fields:costs"
