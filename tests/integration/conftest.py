from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.glossary_docx import GLOSSARY_TABLES, write_docx
from tests.support.pdf_canvas import pdf_canvas
from wellscope.config import Settings


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


@pytest.fixture
def settings(data_dir: Path) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=data_dir, output_dir=data_dir.parent / "processed"
    )
