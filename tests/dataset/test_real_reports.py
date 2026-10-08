"""Invariants on the real reports (skipped when the dataset is absent).

Only structural properties are asserted here, so no dataset values are published with the code.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from wellscope.domain.documents import DocumentType, ReportDocument
from wellscope.ingestion.parse import parse_glossary, parse_pdf

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
PDFS = sorted(DATA_DIR.rglob("*.pdf"))
GLOSSARIES = [path for path in sorted(DATA_DIR.rglob("*.docx")) if "gloss" in path.name.casefold()]
FAMILIES = {DocumentType.DDR, DocumentType.DGOS}

pytestmark = [
    pytest.mark.dataset,
    pytest.mark.skipif(not PDFS, reason="dataset not present in data/raw"),
]


@pytest.fixture(scope="module")
def documents() -> list[ReportDocument]:
    return [
        parse_pdf(path, path.name, hashlib.sha256(path.read_bytes()).hexdigest()) for path in PDFS
    ]


def checks_of(document: ReportDocument) -> dict[str, bool]:
    return {check.id: check.ok for check in document.quality}


def test_every_report_is_classified_with_a_number_and_date(documents: list[ReportDocument]) -> None:
    reports = [document for document in documents if document.doc_type in FAMILIES]
    assert {document.doc_type for document in reports} == FAMILIES
    for document in reports:
        assert document.report.number is not None
        assert document.report.date is not None
        assert document.report.period_start is not None


def test_drilling_reports_satisfy_the_operation_invariants(
    documents: list[ReportDocument],
) -> None:
    drilling = [document for document in documents if document.doc_type is DocumentType.DDR]
    assert drilling
    for document in drilling:
        checks = checks_of(document)
        assert checks["operations.hours_total"], document.doc_id
        assert checks["operations.npt_matches_header"], document.doc_id
        assert checks["operations.row_hours"], document.doc_id
        assert document.next_day is not None
        assert document.next_day.entries


def test_geological_summaries_have_remarks_grids_and_formation_tops(
    documents: list[ReportDocument],
) -> None:
    summaries = [document for document in documents if document.doc_type is DocumentType.DGOS]
    assert summaries
    for document in summaries:
        sections = {table.section for table in document.tables}
        assert {"progress_summary", "progress", "casing_shoe", "formation_tops"} <= sections
        assert document.remarks
        assert "phase" in document.fields


def test_hidden_text_is_removed_from_summaries(documents: list[ReportDocument]) -> None:
    for document in documents:
        if document.doc_type is DocumentType.DGOS:
            assert min(page.visible_ratio for page in document.pages) < 1
            assert "DAILY UPDATES" not in document.pages[0].text


@pytest.mark.skipif(not GLOSSARIES, reason="glossary not present in data/raw")
def test_glossary_parses_entries_with_statuses() -> None:
    path = GLOSSARIES[0]
    glossary = parse_glossary(path, path.name, hashlib.sha256(path.read_bytes()).hexdigest())
    statuses = {entry.status.value for entry in glossary.entries}
    assert len(glossary.entries) > 100
    assert {"confirmed", "to_be_confirmed", "unknown"} <= statuses
