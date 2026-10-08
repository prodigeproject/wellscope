from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from tests.support.documents import make_document, make_glossary
from tests.support.index import build_test_index
from wellscope.domain.catalog import ConflictValue, CrossDocumentFinding
from wellscope.domain.documents import DocumentType, ReportDocument
from wellscope.domain.glossary import GlossaryEntry
from wellscope.llm.fakes import HashEmbedder
from wellscope.retrieval.models import DocumentFilter, Intent, RetrievalQuery
from wellscope.retrieval.retriever import Retriever
from wellscope.retrieval.search import HybridSearch

DDR_ID, DGOS_ID = "ddr-well-a-1-0012", "dgos-well-a-1-0013"
NPT = GlossaryEntry(
    id="gl-npt", term="NPT", aliases=("NPT",), expansion="Non-Productive Time", source_row=1
)


def reports() -> list[ReportDocument]:
    ddr = make_document()
    period = {"period_start": datetime(2026, 1, 14), "period_end": datetime(2026, 1, 15, 6)}
    ddr = ddr.model_copy(update={"report": ddr.report.model_copy(update=period)})
    dgos_report = ddr.report.model_copy(
        update={
            "number": 13,
            "date": date(2026, 1, 16),
            "period_start": datetime(2026, 1, 15, 6),
            "period_end": datetime(2026, 1, 16, 6),
        }
    )
    dgos = ddr.model_copy(
        update={"doc_id": DGOS_ID, "doc_type": DocumentType.DGOS, "report": dgos_report}
    )
    return [ddr, dgos]


def retriever(tmp_path: Path, budget: int = 16000) -> Retriever:
    conflict = CrossDocumentFinding(
        id="conflict.spud_date",
        severity="warning",
        detail="Spud date differs between documents.",
        values=[
            ConflictValue(doc_id=DDR_ID, value="2026-01-02"),
            ConflictValue(doc_id=DGOS_ID, value="2025-01-02"),
        ],
    )
    embedder = HashEmbedder()
    index = build_test_index(
        tmp_path / "i.db", reports(), make_glossary(NPT), embedder=embedder, conflicts=[conflict]
    )
    return Retriever(index, HybridSearch(index, embedder), budget_tokens=budget)


def query(
    question: str, intent: Intent = Intent.REPORT_FACT, filters: DocumentFilter | None = None
) -> RetrievalQuery:
    return RetrievalQuery(question=question, intent=intent, filters=filters or DocumentFilter())


def test_a_resolved_report_that_fits_the_budget_is_given_in_full(tmp_path: Path) -> None:
    result = retriever(tmp_path).retrieve(
        query("daily cost?", filters=DocumentFilter(report_numbers=(12,)))
    )
    assert result.doc_ids == (DDR_ID,)
    assert result.mode == "full"
    assert any(source.section == "Costs (USD)" for source in result.sources)
    assert all(source.doc_id != DGOS_ID for source in result.sources)


def test_glossary_mentions_come_first(tmp_path: Path) -> None:
    result = retriever(tmp_path).retrieve(query("What is NPT?", Intent.GLOSSARY))
    assert result.sources[0].label == "Glossary"
    assert result.glossary_ids == ("gl-npt",)
    assert result.mode == "glossary"


def test_unknown_reports_are_flagged_without_document_sources(tmp_path: Path) -> None:
    result = retriever(tmp_path).retrieve(
        query("depth?", filters=DocumentFilter(report_numbers=(99,)))
    )
    assert result.unmatched_filter
    assert result.doc_ids == ()
    assert all(source.doc_id not in (DDR_ID, DGOS_ID) for source in result.sources)


def test_comparisons_get_the_catalog_and_conflicts(tmp_path: Path) -> None:
    result = retriever(tmp_path).retrieve(query("compare spud dates", Intent.COMPARISON))
    labels = [source.label for source in result.sources]
    assert "Report catalog" in labels
    conflict = next(source for source in result.sources if source.label == "Data conflicts")
    assert "DGOS #13 (2026-01-16) = 2025-01-02" in conflict.text


def test_reports_over_budget_fall_back_to_search(tmp_path: Path) -> None:
    result = retriever(tmp_path, budget=400).retrieve(query("reamer", Intent.OPERATIONS))
    assert result.mode == "search"
    assert any("reamer" in source.text for source in result.sources)


def test_report_sources_state_the_period_they_cover(tmp_path: Path) -> None:
    result = retriever(tmp_path).retrieve(
        query("daily cost?", filters=DocumentFilter(report_numbers=(12,)))
    )
    costs = next(source for source in result.sources if source.section == "Costs (USD)")
    assert costs.period == "2026-01-14 00:00 to 2026-01-15 06:00"


def test_capitalised_names_found_in_the_reports_are_recognised(tmp_path: Path) -> None:
    found = retriever(tmp_path)
    assert found.names_corpus_entity("What is the MAASP value?")
    assert not found.names_corpus_entity("Who is the PRESIDENT?")
    assert not found.names_corpus_entity("no capitals here")


def test_the_most_relevant_passages_come_first_when_reports_are_given_in_full(
    tmp_path: Path,
) -> None:
    result = retriever(tmp_path).retrieve(
        query("reamer", filters=DocumentFilter(report_numbers=(12,)))
    )
    assert result.mode == "full"
    first_report_source = next(source for source in result.sources if source.doc_id == DDR_ID)
    assert "reamer" in first_report_source.text


def test_catalog_questions_also_get_the_best_matching_passages(tmp_path: Path) -> None:
    result = retriever(tmp_path).retrieve(query("Which reports mention a reamer?", Intent.CATALOG))
    assert result.mode == "catalog"
    assert any("reamer" in source.text for source in result.sources)
