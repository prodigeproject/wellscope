"""Fallback for PDFs of an unknown form: visible page text plus every row of ruled cells.

Unknown documents stay searchable and answerable from their text, with lower confidence than
templated reports (no typed fields and no invariants).
"""

from __future__ import annotations

from collections.abc import Sequence

from wellscope.domain.dates import parse_date
from wellscope.domain.documents import DocumentType, ReportDocument, ReportInfo, SourceInfo, Table
from wellscope.ingestion.pdf.form_parser import document_id, page_texts
from wellscope.ingestion.pdf.grid import page_rows
from wellscope.ingestion.pdf.layout import PageLayout

DATE_SEARCH_LINES = 20


def parse_generic(pages: Sequence[PageLayout], source: SourceInfo) -> ReportDocument:
    """A document holding text and cell rows only."""
    first_lines = [line.text for line in pages[0].lines()] if pages else []
    report_date = next(
        (day for line in first_lines[:DATE_SEARCH_LINES] if (day := parse_date(line))), None
    )
    tables = [
        Table(section=f"page_{page.number}", page=page.number, rows=rows)
        for page in pages
        if (rows := page_rows(page))
    ]
    return ReportDocument(
        doc_id=document_id(DocumentType.GENERIC, None, None, source.sha256),
        doc_type=DocumentType.GENERIC,
        title=first_lines[0] if first_lines else source.file_name,
        source=source,
        report=ReportInfo(date=report_date),
        tables=tables,
        pages=page_texts(pages),
    )
