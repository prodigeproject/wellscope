from __future__ import annotations

from wellscope.qa.answerer import AnswerStatus, Draft
from wellscope.qa.verifier import verify
from wellscope.retrieval.models import Source

SOURCES = (
    Source("S1", "ddr-32", "DDR #32", "Costs (USD)", 1, "- Daily Cost: 250,000.00\n- AFE: 50.00"),
    Source("S2", "ddr-53", "DDR #53", "Costs (USD)", 1, "- Daily Cost: 410,500.50\n- Cost: 40.00"),
)


def draft(
    markdown: str, citations: tuple[str, ...] = ("S1",), status: AnswerStatus = "answered"
) -> Draft:
    return Draft(status=status, markdown=markdown, citations=citations, caveats=())


def test_supported_numbers_and_citations_pass() -> None:
    assert verify(draft("Daily cost was 250,000.00 USD [S1]."), SOURCES, "DDR 32?").ok


def test_indonesian_number_formatting_matches_the_source() -> None:
    assert verify(draft("Biaya harian 250.000,00 USD [S1]."), SOURCES, "DDR 32?").ok


def test_citations_must_exist_and_answers_must_cite() -> None:
    unknown = verify(draft("250,000.00 [S9]", citations=("S9",)), SOURCES, "q")
    assert unknown.unknown_citations == ("S9",)
    assert not unknown.ok
    assert verify(draft("250,000.00", citations=()), SOURCES, "q").missing_citation


def test_inline_citations_count_even_when_the_list_omits_them() -> None:
    assert verify(draft("250,000.00 [S1]", citations=()), SOURCES, "q").ok


def test_numbers_must_come_from_cited_sources() -> None:
    invented = verify(draft("Daily cost was 999,999.99 [S1]"), SOURCES, "q")
    assert invented.unsupported_numbers == ("999,999.99",)
    uncited = verify(draft("Daily cost was 410,500.50 [S1]"), SOURCES, "q")
    assert uncited.unsupported_numbers == ("410,500.50",)


def test_values_calculated_from_cited_numbers_pass() -> None:
    difference = draft(
        "250,000.00 [S1] vs 410,500.50 [S2]: a difference of 160,500.50.", ("S1", "S2")
    )
    assert verify(difference, SOURCES, "q").ok
    share = draft("Cost 40.00 [S2] of AFE 50.00 [S1] is 80.0%.", ("S1", "S2"))
    assert verify(share, SOURCES, "q").ok
    shown = draft("40.00 / 50.00 x 100 = 80.00% [S1, S2]", ("S1", "S2"))
    assert verify(shown, SOURCES, "q").ok


def test_question_numbers_small_counts_codes_and_citations_are_exempt() -> None:
    answer = draft("Report 32 in phase D18 needed 3 attempts; daily cost 250,000.00 [S1].")
    assert verify(answer, SOURCES, "DDR 32?").ok


def test_refusals_are_not_checked() -> None:
    assert verify(draft("", citations=(), status="not_found"), SOURCES, "q").ok


def test_feedback_names_every_problem() -> None:
    result = verify(draft("999.5 [S7]", citations=("S7",)), SOURCES, "q")
    feedback = result.feedback()
    assert "S7" in feedback
    assert "999.5" in feedback


def test_times_and_dates_must_appear_in_cited_sources() -> None:
    sources = (Source("S1", "d", "DDR", "Ops", 1, "17:00 - 24:00 STDBY on 09/08/2026"),)
    good = draft("Standby 17:00-24:00 on 9 August 2026 [S1].")
    assert verify(good, sources, "q").ok
    bad = verify(draft("Standby from 16:00 on 10/08/2026 [S1]."), sources, "q")
    assert bad.unsupported_numbers == ("16:00", "10/08/2026")


def test_midnight_may_be_written_either_way() -> None:
    sources = (Source("S1", "d", "DDR", "Ops", 1, "23:15 - 0:00"),)
    assert verify(draft("From 23:15 to 24:00 [S1]."), sources, "q").ok
