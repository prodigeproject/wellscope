from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.glossary_docx import GLOSSARY_TABLES as TABLES
from tests.support.glossary_docx import write_docx
from wellscope.domain.glossary import GlossaryEntry, GlossaryStatus
from wellscope.ingestion.docx.glossary_parser import build_entries, is_glossary, read_tables


@pytest.fixture
def entries() -> dict[str, GlossaryEntry]:
    return {entry.term: entry for entry in build_entries(TABLES)}


def test_build_entries_skips_header_and_letter_separator_rows(
    entries: dict[str, GlossaryEntry],
) -> None:
    assert sorted(entries) == ["-2", "ABC", "ALPHA", "Avg.", "K1 / K2", "QQ", "X/Y", "ZZ", "kgs"]


def test_build_entries_splits_expansion_and_description(entries: dict[str, GlossaryEntry]) -> None:
    entry = entries["ABC"]
    assert entry.expansion == "Alpha Bravo Charlie"
    assert entry.description == "Example definition of a term."
    assert entry.status is GlossaryStatus.CONFIRMED


def test_build_entries_keeps_expansion_only_rows(entries: dict[str, GlossaryEntry]) -> None:
    assert entries["Avg."].expansion == "Average"
    assert entries["Avg."].description is None


def test_build_entries_marks_unknown_and_to_be_confirmed(entries: dict[str, GlossaryEntry]) -> None:
    assert entries["QQ"].status is GlossaryStatus.UNKNOWN
    assert entries["QQ"].expansion is None
    assert entries["QQ"].description == "Seen in a report field."
    assert entries["K1 / K2"].status is GlossaryStatus.TO_BE_CONFIRMED
    assert entries["K1 / K2"].description == "Codes in the operation table."


def test_build_entries_splits_aliases_only_on_spaced_slashes(
    entries: dict[str, GlossaryEntry],
) -> None:
    assert entries["K1 / K2"].aliases == ("K1", "K2")
    assert entries["X/Y"].aliases == ("X/Y",)


def test_build_entries_adds_misspelling_aliases(entries: dict[str, GlossaryEntry]) -> None:
    assert entries["kgs"].aliases == ("kgs", "Kgs")


def test_build_entries_lists_every_sense_of_ambiguous_terms(
    entries: dict[str, GlossaryEntry],
) -> None:
    assert entries["ZZ"].senses == ("Zone Zero", "Zig Zag")
    assert entries["ABC"].senses == ()


def test_build_entries_assigns_categories_and_unique_ids(
    entries: dict[str, GlossaryEntry],
) -> None:
    assert entries["ALPHA"].category == "well_name_part"
    assert entries["ABC"].category == "abbreviation"
    assert len({entry.id for entry in entries.values()}) == len(entries)


def test_read_tables_and_detection_work_on_a_real_docx(tmp_path: Path) -> None:
    tables = read_tables(write_docx(tmp_path / "glossary.docx", TABLES))

    assert is_glossary(tables)
    assert tables[1][2] == TABLES[1][2]


def test_is_glossary_rejects_documents_without_a_meaning_table() -> None:
    assert not is_glossary([[["Name", "Value"], ["a", "b"]]])


def test_a_term_repeated_across_tables_still_gets_unique_ids() -> None:
    table = [["Abbreviation", "Meaning"], ["X", "X"], ["TD", "Total Depth"]]
    entries = build_entries([table, table, table])
    assert len({entry.id for entry in entries}) == len(entries) == 3
