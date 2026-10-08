from __future__ import annotations

import json

import pytest

from tests.support.pdf_canvas import pdf_canvas
from wellscope.config import Settings
from wellscope.errors import ConfigurationError, IngestionError
from wellscope.pipeline import run_ingest


def test_ingest_isolates_bad_files_and_keeps_going(settings: Settings) -> None:
    result = run_ingest(settings)
    manifest = result.manifest
    assert [document.doc_type.value for document in manifest.documents] == ["GENERIC"]
    assert manifest.glossary is not None
    assert manifest.glossary.entries == 9
    reasons = {entry.source_file: entry.reason for entry in manifest.quarantined}
    assert reasons == {"broken.pdf": "parse_error", "notes.docx": "unsupported_document"}


def test_ingest_writes_json_outputs_that_round_trip(settings: Settings) -> None:
    manifest = run_ingest(settings).manifest
    output = settings.output_dir
    document_file = output / manifest.documents[0].json_path
    payload = json.loads(document_file.read_text(encoding="utf-8"))
    assert payload["doc_type"] == "GENERIC"
    assert payload["report"]["date"] == "2026-03-15"
    assert "Oil rate" in payload["pages"][0]["text"]
    assert (output / "glossary.json").is_file()
    assert (output / "quality_report.json").is_file()


def test_ingest_is_deterministic_and_prunes_removed_sources(settings: Settings) -> None:
    first = run_ingest(settings).manifest
    second = run_ingest(settings).manifest
    assert first.index_version == second.index_version
    (settings.data_dir / "nested" / "Production Summary.pdf").unlink()
    third = run_ingest(settings)
    assert third.manifest.documents == []
    assert any("removed stale output" in note for note in third.notes)
    assert not list((settings.output_dir / "documents").glob("*.json"))


def test_reports_without_a_date_sort_with_dated_ones(settings: Settings) -> None:
    with pdf_canvas(settings.data_dir / "undated.pdf") as canvas:
        canvas.text(40, 40, "WEEKLY NOTE WITHOUT A DATE")
        canvas.text(40, 60, "Mud weight 10.0 ppg")
    documents = run_ingest(settings).manifest.documents
    assert len(documents) == 2
    assert [document.report_date is None for document in documents] == [False, True]


def test_a_missing_data_folder_is_an_error(settings: Settings) -> None:
    missing = settings.model_copy(update={"data_dir": settings.data_dir / "typo"})
    with pytest.raises(ConfigurationError) as raised:
        run_ingest(missing)
    assert raised.value.code == "data_dir_missing"


def test_a_folder_without_sources_leaves_previous_outputs_alone(settings: Settings) -> None:
    run_ingest(settings)
    empty = settings.data_dir.parent / "empty"
    empty.mkdir()
    with pytest.raises(IngestionError) as raised:
        run_ingest(settings.model_copy(update={"data_dir": empty}))
    assert raised.value.code == "no_sources"
    assert list((settings.output_dir / "documents").glob("*.json"))
