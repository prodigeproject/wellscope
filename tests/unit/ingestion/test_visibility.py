from __future__ import annotations

from pathlib import Path

import pdfplumber
import pytest

from tests.support.pdf_canvas import TEAL, WHITE, pdf_canvas
from wellscope.ingestion.pdf.visibility import visible_page


@pytest.fixture
def layered_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "layered.pdf"
    with pdf_canvas(path) as canvas:
        canvas.text(40, 40, "PLAIN")
        canvas.text(40, 80, "GHOST", color=WHITE)
        canvas.box(30, 115, 200, 135, color=TEAL)
        canvas.text(40, 120, "HEADER", color=WHITE)
        canvas.text(40, 160, "COVERED")
        canvas.box(30, 155, 200, 175, color=WHITE)
        canvas.box(30, 195, 200, 215, color=TEAL)
        canvas.text(40, 200, "DARKONDARK", color=(0.1, 0.3, 0.3))
    return path


def visible_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        page, _ = visible_page(pdf.pages[0])
        return page.extract_text()


def test_visible_page_keeps_ordinary_text(layered_pdf: Path) -> None:
    assert "PLAIN" in visible_text(layered_pdf)


def test_visible_page_drops_white_text_on_white_background(layered_pdf: Path) -> None:
    assert "GHOST" not in visible_text(layered_pdf)


def test_visible_page_keeps_white_text_on_dark_fill(layered_pdf: Path) -> None:
    assert "HEADER" in visible_text(layered_pdf)


def test_visible_page_drops_text_painted_over_by_a_later_shape(layered_pdf: Path) -> None:
    assert "COVERED" not in visible_text(layered_pdf)


def test_visible_page_drops_text_without_contrast_against_its_fill(layered_pdf: Path) -> None:
    assert "DARKONDARK" not in visible_text(layered_pdf)


def test_visible_page_reports_visibility_ratio(layered_pdf: Path) -> None:
    with pdfplumber.open(layered_pdf) as pdf:
        _, stats = visible_page(pdf.pages[0])
    assert stats.total_chars > stats.visible_chars > 0
    assert 0 < stats.ratio < 1
