from __future__ import annotations

from datetime import date

from wellscope.domain.chunks import GLOSSARY_DOC_ID, document_chunks, glossary_chunks
from wellscope.domain.documents import (
    DocumentType,
    FieldValue,
    ParserInfo,
    ReportDocument,
    ReportInfo,
    SourceInfo,
    WellInfo,
)
from wellscope.domain.glossary import Glossary, GlossaryEntry

SOURCE = SourceInfo(
    file_name="r.pdf",
    relative_path="r.pdf",
    sha256="0" * 64,
    page_count=1,
    parser=ParserInfo(name="t", version="1"),
)


def test_document_chunks_carry_provenance_and_normalised_index_text() -> None:
    document = ReportDocument(
        doc_id="ddr-a-0001",
        doc_type=DocumentType.DDR,
        title="Daily Operation Report",
        source=SOURCE,
        well=WellInfo(name="A-1"),
        report=ReportInfo(number=1, date=date(2026, 1, 1)),
        fields={
            "size": FieldValue(label="Hole", section="depth_days", raw='17½"', page=1),
        },
    )
    chunks = document_chunks(document)
    assert [chunk.chunk_id for chunk in chunks] == ["ddr-a-0001:fields:depth_days"]
    assert chunks[0].text.startswith("[DDR #1 (2026-01-01) · A-1 · Depth and days · p.1]")
    assert '17-1/2"' in chunks[0].index_text
    assert chunks[0].doc_id == "ddr-a-0001"


def test_glossary_chunks_use_the_glossary_document_id() -> None:
    glossary = Glossary(
        source=SOURCE,
        entries=[GlossaryEntry(id="gl-abc", term="ABC", aliases=("ABC",), source_row=1)],
    )
    chunks = glossary_chunks(glossary)
    assert chunks[0].chunk_id == "glossary:gl-abc"
    assert chunks[0].doc_id == GLOSSARY_DOC_ID
    assert chunks[0].kind == "glossary"
