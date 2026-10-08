from __future__ import annotations

from dataclasses import replace

from wellscope.domain.messages import Language
from wellscope.evals.golden import Expectation, GoldenItem
from wellscope.evals.scoring import contains, score
from wellscope.qa.service import Answer, Citation, ModelUsage


def item(**expect: object) -> GoldenItem:
    return GoldenItem(
        id="D01",
        lang=Language.EN,
        category="report_fact",
        question="Daily cost DDR 32?",
        expect=Expectation.model_validate(expect),
    )


def answer(
    markdown: str, status: str = "answered", doc_ids: tuple[str, ...] = ("ddr-32",)
) -> Answer:
    citations = tuple(
        Citation(f"S{n}", doc_id, "DDR #32", "Costs", 1, "excerpt")
        for n, doc_id in enumerate(doc_ids)
    )
    usage = (ModelUsage("m", 100, 20, 900),)
    return Answer(
        status=status,  # type: ignore[arg-type]
        language=Language.EN,
        markdown=markdown,
        html="",
        citations=citations,
        latency_ms=1234,
        usage=usage,
    )


def test_numbers_match_whatever_the_separators() -> None:
    assert contains("Biaya harian 348.640,02 USD", "348,640.02")
    assert contains("total 1355 days", "1,355")
    assert contains("7 jam", "7.00")
    assert not contains("348,640.12", "348,640.02")


def test_dates_match_in_any_written_form() -> None:
    assert contains("spudded on 27 Juni 2026", "27/06/2026")
    assert contains("2026-07-29", "29/07/2026")
    assert not contains("27/06/2027", "27/06/2026")


def test_text_matching_ignores_case_dashes_and_spacing() -> None:
    assert contains("Non–Productive   time", "Non-Productive Time")
    assert contains("code 1-2-CT-S-X-I-WT-TD", "1-2-CT-S-X-I-WT-TD")


def test_an_answer_passes_when_status_content_and_citations_match() -> None:
    result = score(
        item(must_include=["348,640.02"], must_cite_docs=["ddr-32"]), answer("348,640.02 USD")
    )
    assert result.passed
    assert result.latency_ms == 1234
    assert result.input_tokens == 100


def test_missing_facts_and_citations_fail_with_reasons() -> None:
    expectation = item(
        must_include=["348,640.02"],
        must_include_any=[["Tayalan", "Jordan"]],
        must_cite_docs=["ddr-53"],
    )
    result = score(expectation, answer("Lead DS was Jordan."))
    assert not result.passed
    assert result.missing == ("348,640.02",)
    assert not result.citations_ok


def test_refusal_expectations() -> None:
    refused = item(status="refused")
    assert score(refused, answer("Sorry", status="out_of_scope", doc_ids=())).passed
    assert score(refused, answer("Not found", status="not_found", doc_ids=())).passed
    assert not score(refused, answer("4", doc_ids=())).passed
    grounded = item(status="grounded")
    assert score(grounded, answer("Not recorded.")).passed
    assert not score(grounded, answer("Sorry", status="out_of_scope", doc_ids=())).passed


def test_facts_stated_in_caveats_count() -> None:
    conflict = item(must_include=["27/06/2026", "27/06/2027"])
    reply = replace(answer("Spudded on 27/06/2026."), caveats=("The DDR says 27/06/2027.",))
    assert score(conflict, reply).passed
