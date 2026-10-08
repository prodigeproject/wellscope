from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from wellscope.domain.glossary import GlossaryEntry, GlossaryStatus
from wellscope.ingestion.docx.glossary_parser import build_entries, is_glossary, read_tables

# Dummy content that mirrors the structure of the real glossary (which is not committed).
TABLES = [
    [
        ["Part", "Meaning"],
        ["ALPHA", "Field name. The well targets reservoirs below the Beta field."],
        ["-2", "Well number 2."],
    ],
    [
        ["Abbreviation", "Meaning"],
        ["A", "A"],
        ["ABC", "Alpha Bravo Charlie – Example definition of a term."],
        ["Avg.", "Average"],
        ["QQ", "Unknown – Seen in a report field. (to be confirmed)"],
        ["K1 / K2", "Phase codes – Codes in the operation table. (to be confirmed)"],
        ["X/Y", "Cross Yield – A term whose abbreviation contains a slash."],
        ["kgs", "Kilograms – Written 'Kgs' by mistake in the report."],
        ["Z", "Z"],
        [
            "ZZ",
            "Zone Zero / Zig Zag – Zone Zero in the report glossary; Zig Zag in the log viewer.",
        ],
    ],
]


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
    path = tmp_path / "glossary.docx"
    document = Document()
    for rows in TABLES:
        table = document.add_table(rows=len(rows), cols=2)
        for row, values in zip(table.rows, rows, strict=True):
            for cell, value in zip(row.cells, values, strict=True):
                cell.text = value
    document.save(str(path))

    tables = read_tables(path)

    assert is_glossary(tables)
    assert tables[1][2] == TABLES[1][2]


def test_is_glossary_rejects_documents_without_a_meaning_table() -> None:
    assert not is_glossary([[["Name", "Value"], ["a", "b"]]])
