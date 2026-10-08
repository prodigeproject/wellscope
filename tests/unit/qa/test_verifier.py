from __future__ import annotations

import pytest

from wellscope.qa.answerer import AnswerStatus, Draft
from wellscope.qa.verifier import verify
from wellscope.retrieval.models import Source

SOURCES = (
    Source("S1", "ddr-32", "DDR #32", "Costs (USD)", 1, "- Daily Cost: 250,000.00\n- AFE: 50.00"),
    Source("S2", "ddr-53", "DDR #53", "Costs (USD)", 1, "- Daily Cost: 410,500.50\n- Cost: 40.00"),
)
DEPTHS = (Source("S1", "ddr-9", "DDR #9", "Depth", 1, "MD 2,354 m, MW 9.6 ppg, NPT 3.5 hrs"),)
HOURS = (Source("S1", "ddr-9", "DDR #9", "Ops", 2, "1.00 h, 2.50 h, 0.25 h, 0.25 h, 3.00 h"),)


def draft(
    markdown: str, citations: tuple[str, ...] = ("S1",), status: AnswerStatus = "answered"
) -> Draft:
    return Draft(status=status, markdown=markdown, citations=citations, caveats=())


def test_supported_numbers_and_citations_pass() -> None:
    assert verify(draft("Daily cost was 250,000.00 USD [S1]."), SOURCES).ok


def test_indonesian_number_formatting_matches_the_source() -> None:
    assert verify(draft("Biaya harian 250.000,00 USD [S1]."), SOURCES).ok


def test_citations_must_exist_and_answers_must_cite() -> None:
    unknown = verify(draft("250,000.00 [S9]", citations=("S9",)), SOURCES)
    assert unknown.unknown_citations == ("S9",)
    assert not unknown.ok
    assert verify(draft("250,000.00", citations=()), SOURCES).missing_citation


def test_inline_citations_count_even_when_the_list_omits_them() -> None:
    assert verify(draft("250,000.00 [S1]", citations=()), SOURCES).ok


def test_numbers_must_come_from_cited_sources() -> None:
    invented = verify(draft("Daily cost was 999,999.99 [S1]"), SOURCES)
    assert invented.unsupported_numbers == ("999,999.99",)
    uncited = verify(draft("Daily cost was 410,500.50 [S1]"), SOURCES)
    assert uncited.unsupported_numbers == ("410,500.50",)


@pytest.mark.parametrize("wrong", ["2,345 m", "9,999 m", "9.9 ppg", "7.25 hrs", "8,000 m"])
def test_wrong_figures_close_to_true_ones_fail(wrong: str) -> None:
    result = verify(draft(f"The value was {wrong} [S1]."), DEPTHS)
    assert result.unsupported_numbers == (wrong.split(maxsplit=1)[0],)


def test_numbers_from_the_question_are_not_evidence() -> None:
    assert not verify(draft("Yes, the depth was 4321 m [S1]."), DEPTHS).ok


def test_values_calculated_from_cited_numbers_in_the_same_sentence_pass() -> None:
    difference = draft(
        "250,000.00 [S1] vs 410,500.50 [S2]: a difference of 160,500.50.", ("S1", "S2")
    )
    assert verify(difference, SOURCES).ok
    share = draft("Cost 40.00 [S2] of AFE 50.00 [S1] is 80.0%.", ("S1", "S2"))
    assert verify(share, SOURCES).ok
    shown = draft("40.00 / 50.00 x 100 = 80.00% [S1, S2]", ("S1", "S2"))
    assert verify(shown, SOURCES).ok


def test_a_total_of_the_values_listed_before_it_passes_and_a_wrong_one_fails() -> None:
    assert verify(draft("Total = 1 + 2.5 + 0.25 + 0.25 + 3 = 7.00 h [S1]."), HOURS).ok
    wrong = verify(draft("Total = 1 + 2.5 + 0.25 + 0.25 + 3 = 7.75 h [S1]."), HOURS)
    assert wrong.unsupported_numbers == ("7.75",)


def test_values_derived_from_numbers_elsewhere_in_the_answer_fail() -> None:
    answer = draft(
        "Cost 40.00 [S2].\n\nAFE 50.00 [S1].\n\nSomething else.\n\nThe gap is 10.00.", ("S1", "S2")
    )
    assert verify(answer, SOURCES).unsupported_numbers == ("10.00",)


def test_small_counts_codes_and_report_labels_are_exempt() -> None:
    answer = draft("Report 32 in phase D18 needed 3 attempts; daily cost 250,000.00 [S1].")
    assert verify(answer, SOURCES).ok


def test_one_hundred_is_exempt_only_as_a_percentage_factor() -> None:
    assert verify(draft("The depth was 100 m [S1]."), DEPTHS).unsupported_numbers == ("100",)


def test_refusals_are_not_checked() -> None:
    assert verify(draft("", citations=(), status="not_found"), SOURCES).ok


def test_feedback_names_every_problem() -> None:
    result = verify(draft("999.5 [S7]", citations=("S7",)), SOURCES)
    feedback = result.feedback()
    assert "S7" in feedback
    assert "999.5" in feedback


def test_times_and_dates_must_appear_in_cited_sources() -> None:
    sources = (Source("S1", "d", "DDR", "Ops", 1, "17:00 - 24:00 STDBY on 09/08/2026"),)
    good = draft("Standby 17:00-24:00 on 9 August 2026 [S1].")
    assert verify(good, sources).ok
    bad = verify(draft("Standby from 16:00 on 10/08/2026 [S1]."), sources)
    assert bad.unsupported_numbers == ("16:00", "10/08/2026")


def test_midnight_may_be_written_either_way() -> None:
    sources = (Source("S1", "d", "DDR", "Ops", 1, "23:15 - 0:00"),)
    assert verify(draft("From 23:15 to 24:00 [S1]."), sources).ok


def test_the_report_period_is_evidence_for_dates() -> None:
    sources = (
        Source(
            "S1", "d", "DGOS #7", "Ops", 1, "Drilled ahead.", "2026-01-14 06:00 to 2026-01-15 06:00"
        ),
    )
    assert verify(draft("On 14 January 2026 they drilled ahead [S1]."), sources).ok
