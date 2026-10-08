from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.pdf_canvas import pdf_canvas
from wellscope.errors import DocumentParseError
from wellscope.ingestion.pdf.layout import load_layout


@pytest.fixture
def overflowing_table(tmp_path: Path) -> Path:
    path = tmp_path / "table.pdf"
    with pdf_canvas(path) as canvas:
        canvas.grid(columns=[20, 120, 200], rows=[50, 70, 90])
        canvas.text(24, 55, "OVERFLOWINGCOMPANYNAMETEXT")
        canvas.text(185, 55, "7")
        canvas.text(24, 75, "SHORT")
        canvas.text(185, 75, "3")
    return path


def test_load_layout_clips_text_that_spills_past_a_cell_border(overflowing_table: Path) -> None:
    page = load_layout(overflowing_table)[0]
    texts = {word.text for word in page.words}
    assert "7" in texts
    assert not any(text.endswith("7") and len(text) > 1 for text in texts)
    assert all(word.x1 <= 121 for word in page.words if word.text.startswith("OVERFLOW"))


def test_load_layout_detects_cells_from_ruling_lines(overflowing_table: Path) -> None:
    page = load_layout(overflowing_table)[0]
    assert len(page.cells) == 4
    assert page.text(page.cells[-1]) == "3"


def test_load_layout_rejects_documents_over_the_page_limit(tmp_path: Path) -> None:
    path = tmp_path / "long.pdf"
    with pdf_canvas(path) as canvas:
        canvas.text(20, 20, "page one")
        canvas.new_page()
        canvas.text(20, 20, "page two")
    with pytest.raises(DocumentParseError) as raised:
        load_layout(path, max_pages=1)
    assert raised.value.code == "too_many_pages"
