from __future__ import annotations

from wellscope.domain.catalog import ConflictRecord
from wellscope.domain.messages import Language
from wellscope.qa.conflicts import conflict_caveats, mentions_conflict

SPUD = ConflictRecord(
    "conflict.spud_date",
    "Spud date differs between documents.",
    (("ddr-1", "2027-01-02"), ("ddr-2", "2027-01-02"), ("dgos-1", "2026-01-02")),
)
DEPTH = ConflictRecord(
    "conflict.water_depth",
    "Water depth differs between documents.",
    (("ddr-1", "65.00"), ("dgos-1", "66.00")),
)
LABELS = {"ddr-1": "DDR #1", "ddr-2": "DDR #2", "dgos-1": "DGOS #1"}


def test_a_conflict_the_question_touches_lists_every_value_with_its_reports() -> None:
    notes = conflict_caveats([SPUD], LABELS, "When was the well spudded?", Language.EN)
    assert notes == [
        "The reports disagree on the spud date: 02/01/2027 (2027-01-02) in DDR #1, DDR #2; "
        "02/01/2026 (2026-01-02) in DGOS #1."
    ]


def test_the_note_follows_the_language_of_the_question() -> None:
    notes = conflict_caveats([SPUD], LABELS, "Kapan sumur di-spud?", Language.ID)
    assert notes == [
        "Laporan tidak sepakat soal spud date: 02/01/2027 (2027-01-02) di DDR #1, DDR #2; "
        "02/01/2026 (2026-01-02) di DGOS #1."
    ]


def test_values_that_are_not_dates_are_shown_as_written() -> None:
    notes = conflict_caveats([SPUD, DEPTH], LABELS, "What is the water depth?", Language.EN)
    assert notes == ["The reports disagree on the water depth: 65.00 in DDR #1; 66.00 in DGOS #1."]


def test_conflicts_the_text_does_not_touch_are_left_out() -> None:
    assert conflict_caveats([SPUD], LABELS, "What was the daily cost?", Language.EN) == []
    # "date" alone names no particular field
    assert conflict_caveats([SPUD], LABELS, "What is the report date?", Language.EN) == []


def test_a_model_caveat_about_the_same_conflict_is_recognised() -> None:
    assert mentions_conflict("The DGOS headers state the spud date as 27-06-2026.", SPUD)
    assert not mentions_conflict("Mud weight was not recorded.", SPUD)
