from __future__ import annotations

from pathlib import Path

import pytest
from reportlab.pdfbase.pdfmetrics import stringWidth

from tests.support.pdf_canvas import FONT, FONT_SIZE, pdf_canvas
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


def test_text_spilling_past_a_cell_border_stays_whole_in_its_own_cell(
    overflowing_table: Path,
) -> None:
    page = load_layout(overflowing_table)[0]
    texts = {word.text for word in page.words}
    assert "7" in texts
    assert "OVERFLOWINGCOMPANYNAMETEXT" in texts
    assert not any(text.endswith("7") and len(text) > 1 for text in texts)
    assert all(word.x1 <= 121 for word in page.words if word.text.startswith("OVERFLOW"))


def test_load_layout_splits_words_that_touch_across_a_cell_border(tmp_path: Path) -> None:
    path = tmp_path / "touching.pdf"
    border = 120.0
    left_text = "ABCD"
    left_x = border - stringWidth(left_text, FONT, FONT_SIZE) - 0.2
    with pdf_canvas(path) as canvas:
        canvas.grid(columns=[20, border, 200], rows=[50, 70])
        canvas.text(left_x, 55, left_text)
        canvas.text(border + 0.4, 55, "WXYZ")
    texts = [word.text for word in load_layout(path)[0].words]
    assert texts == ["ABCD", "WXYZ"]


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


def test_text_clipped_under_a_neighbouring_label_is_restored(tmp_path: Path) -> None:
    path = tmp_path / "interleaved.pdf"
    border = 120.0
    with pdf_canvas(path) as canvas:
        canvas.grid(columns=[20, border, 200], rows=[50, 70])
        canvas.text(border - stringWidth("Aban", FONT, FONT_SIZE), 55, "Abandon")
        canvas.text(border + 1.0, 55, "Last")
    texts = [word.text for word in load_layout(path)[0].words]
    assert texts == ["Abandon", "Last"]
