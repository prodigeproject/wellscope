from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.glossary_docx import GLOSSARY_TABLES, write_docx
from tests.support.pdf_canvas import pdf_canvas
from wellscope.config import Settings
from wellscope.pipeline import run_ingest


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    (raw / "nested").mkdir(parents=True)
    write_docx(raw / "Glossary.docx", GLOSSARY_TABLES)
    write_docx(raw / "notes.docx", [[["Name", "Value"], ["a", "b"]]])
    (raw / "~$Glossary.docx").write_bytes(b"lock file")
    (raw / "broken.pdf").write_bytes(b"this is not a pdf")
    with pdf_canvas(raw / "nested" / "Production Summary.pdf") as canvas:
        canvas.text(40, 40, "MONTHLY PRODUCTION SUMMARY")
        canvas.text(40, 60, "Report date: 15/03/2026")
        canvas.grid(columns=[40, 200, 300], rows=[100, 120, 140])
        canvas.text(44, 104, "Oil rate")
        canvas.text(204, 104, "1,250 bbl/d")
    return raw


def settings_for(data_dir: Path) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=data_dir, output_dir=data_dir.parent / "processed"
    )


def test_ingest_isolates_bad_files_and_keeps_going(data_dir: Path) -> None:
    result = run_ingest(settings_for(data_dir))
    manifest = result.manifest
    assert [document.doc_type.value for document in manifest.documents] == ["GENERIC"]
    assert manifest.glossary is not None
    assert manifest.glossary.entries == 9
    reasons = {entry.source_file: entry.reason for entry in manifest.quarantined}
    assert reasons == {"broken.pdf": "parse_error", "notes.docx": "unsupported_document"}


def test_ingest_writes_json_outputs_that_round_trip(data_dir: Path) -> None:
    settings = settings_for(data_dir)
    manifest = run_ingest(settings).manifest
    output = settings.output_dir
    document_file = output / manifest.documents[0].json_path
    payload = json.loads(document_file.read_text(encoding="utf-8"))
    assert payload["doc_type"] == "GENERIC"
    assert payload["report"]["date"] == "2026-03-15"
    assert "Oil rate" in payload["pages"][0]["text"]
    assert (output / "glossary.json").is_file()
    assert (output / "quality_report.json").is_file()


def test_ingest_is_deterministic_and_prunes_removed_sources(data_dir: Path) -> None:
    settings = settings_for(data_dir)
    first = run_ingest(settings).manifest
    second = run_ingest(settings).manifest
    assert first.index_version == second.index_version
    (data_dir / "nested" / "Production Summary.pdf").unlink()
    third = run_ingest(settings)
    assert third.manifest.documents == []
    assert any("removed stale output" in note for note in third.notes)
    assert not list((settings.output_dir / "documents").glob("*.json"))
