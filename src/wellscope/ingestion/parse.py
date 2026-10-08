"""Parse one source file, choosing the parser from the file's content."""

from __future__ import annotations

from pathlib import Path

from wellscope.domain.documents import ParserInfo, ReportDocument, SourceInfo
from wellscope.domain.glossary import Glossary
from wellscope.errors import DocumentParseError
from wellscope.ingestion.classify import classify
from wellscope.ingestion.docx.glossary_parser import build_entries, is_glossary, read_tables
from wellscope.ingestion.pdf.form_parser import parse_report
from wellscope.ingestion.pdf.generic import parse_generic
from wellscope.ingestion.pdf.layout import load_layout
from wellscope.ingestion.pdf.templates import load_templates
from wellscope.ingestion.quality import check_document

PARSER_NAME = "wellscope"
PARSER_VERSION = "1.1.0"


def parse_pdf(path: Path, relative_path: str, sha256: str) -> ReportDocument:
    """A report document with quality checks; unknown forms fall back to generic parsing."""
    pages = load_layout(path)
    template = classify(pages[0].text() if pages else "", load_templates())
    source = SourceInfo(
        file_name=path.name,
        relative_path=relative_path,
        sha256=sha256,
        page_count=len(pages),
        parser=ParserInfo(
            name=PARSER_NAME,
            version=PARSER_VERSION,
            template=template.id if template else None,
        ),
    )
    document = parse_report(pages, template, source) if template else parse_generic(pages, source)
    return document.model_copy(update={"quality": check_document(document)})


def parse_glossary(path: Path, relative_path: str, sha256: str) -> Glossary:
    """The glossary knowledge base from a Word file; other Word files are rejected."""
    tables = read_tables(path)
    if not is_glossary(tables):
        message = f"{path.name} has no glossary table (a header ending in 'Meaning')"
        raise DocumentParseError(message, code="unsupported_document")
    source = SourceInfo(
        file_name=path.name,
        relative_path=relative_path,
        sha256=sha256,
        page_count=0,
        parser=ParserInfo(name=PARSER_NAME, version=PARSER_VERSION, template="glossary@1"),
    )
    return Glossary(source=source, entries=build_entries(tables))
