from __future__ import annotations

from datetime import date

import pytest

from wellscope.domain.messages import Language
from wellscope.qa.extractors import clean_question, detect_language, extract_references

FULL_WIDTH_DDR = "".join(map(chr, (0xFF24, 0xFF24, 0xFF32)))
NUL, TAB, ZERO_WIDTH_SPACE = chr(0), chr(9), chr(0x200B)


def test_clean_question_normalises_unicode_and_strips_control_characters() -> None:
    raw = f"  {FULL_WIDTH_DDR}{NUL} 32{TAB}{ZERO_WIDTH_SPACE}?\n\n\nok  "
    assert clean_question(raw) == "DDR 32 ?\n\nok"


@pytest.mark.parametrize(
    ("question", "numbers", "types"),
    [
        ("Berapa daily cost pada DDR report no. 32?", (32,), ("DDR",)),
        ("What was the cumulative cost as of report 53?", (53,), ()),
        ("Siapa Lead DS di DDR 53?", (53,), ("DDR",)),
        ("How much did depth increase between DGOS 72 and DGOS 84?", (72, 84), ("DGOS",)),
        ("Bandingkan daily cost DDR 32 dan 53", (32, 53), ("DDR",)),
        ("Apa isi laporan ke-72?", (72,), ()),
        ("Compare DDR #32 with DGOS #84", (32, 84), ("DDR", "DGOS")),
    ],
)
def test_report_references(question: str, numbers: tuple[int, ...], types: tuple[str, ...]) -> None:
    found = extract_references(question, default_year=2026)
    assert found.report_numbers == numbers
    assert found.doc_types == types


@pytest.mark.parametrize(
    "question",
    [
        "What is the length of BHA no. 8?",
        "Describe wireline Run #1",
        "Apa isi laporan 19 Juli 2026?",
        "laporan 2026-07-19",
        "Ringkas laporan 3 hari terakhir",
        "Summarize the reports 2 days before 9 August",
        "Bandingkan laporan 3 terakhir",
    ],
)
def test_numbers_that_are_not_report_numbers_are_ignored(question: str) -> None:
    assert extract_references(question, default_year=2026).report_numbers == ()


def test_dates_in_english_and_indonesian_with_the_catalog_year() -> None:
    found = extract_references("Apa yang terjadi pada 20 Juli pukul 04:00-06:00?", 2026)
    assert found.dates == (date(2026, 7, 20),)
    assert extract_references("on 19/07/2026 and Aug 9, 2026", None).dates == (
        date(2026, 7, 19),
        date(2026, 8, 9),
    )


def test_latest_only_for_unambiguous_wording() -> None:
    assert extract_references("What is the latest reported depth?", 2026).latest
    assert extract_references("Laporan terbaru apa?", 2026).latest
    assert not extract_references("Kapan BOP test terakhir?", 2026).latest


@pytest.mark.parametrize(
    ("question", "language"),
    [
        ("Berapa daily cost pada DDR 32?", Language.ID),
        ("Apa itu NPT?", Language.ID),
        ("Halo", Language.ID),
        ("What does BHA stand for?", Language.EN),
        ("NPT?", Language.EN),
    ],
)
def test_language_detection(question: str, language: Language) -> None:
    assert detect_language(question) is language
