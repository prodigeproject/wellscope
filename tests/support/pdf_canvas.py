"""Tiny drawing DSL over reportlab that speaks in top-left coordinates like pdfplumber."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
TEAL = (0.06, 0.36, 0.35)
PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0
FONT = "Helvetica"
FONT_SIZE = 9.0


class PdfCanvas:
    """Draw text, boxes and lines on letter-sized pages using a top-left origin."""

    def __init__(self, path: Path) -> None:
        self._canvas = Canvas(str(path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
        self._canvas.setFont(FONT, FONT_SIZE)

    def text(self, x: float, top: float, value: str, color: tuple[float, ...] = BLACK) -> None:
        self._canvas.setFillColorRGB(*color)
        self._canvas.drawString(x, PAGE_HEIGHT - top - FONT_SIZE, value)

    def box(
        self, x0: float, top: float, x1: float, bottom: float, color: tuple[float, ...]
    ) -> None:
        self._canvas.setFillColorRGB(*color)
        self._canvas.rect(x0, PAGE_HEIGHT - bottom, x1 - x0, bottom - top, fill=1, stroke=0)

    def line(self, x0: float, top: float, x1: float, bottom: float) -> None:
        self._canvas.setStrokeColorRGB(*BLACK)
        self._canvas.setLineWidth(0.5)
        self._canvas.line(x0, PAGE_HEIGHT - top, x1, PAGE_HEIGHT - bottom)

    def grid(self, columns: list[float], rows: list[float]) -> None:
        """Draw a ruled table whose cell borders sit at the given x and y positions."""
        for x in columns:
            self.line(x, rows[0], x, rows[-1])
        for y in rows:
            self.line(columns[0], y, columns[-1], y)

    def new_page(self) -> None:
        self._canvas.showPage()
        self._canvas.setFont(FONT, FONT_SIZE)

    def save(self) -> None:
        self._canvas.save()


@contextmanager
def pdf_canvas(path: Path) -> Iterator[PdfCanvas]:
    """Yield a canvas and save the PDF on exit."""
    canvas = PdfCanvas(path)
    yield canvas
    canvas.save()
