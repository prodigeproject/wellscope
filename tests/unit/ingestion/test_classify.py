from __future__ import annotations

from wellscope.domain.documents import DocumentType
from wellscope.ingestion.classify import classify
from wellscope.ingestion.pdf.form_parser import document_id
from wellscope.ingestion.pdf.templates import load_templates


def test_classify_uses_content_signatures_case_and_space_insensitively() -> None:
    templates = load_templates()
    ddr = classify("ACME ENERGY\nDaily   Operation Report\nWell: X-1", templates)
    dgos = classify("daily geological operations summary", templates)
    assert ddr is not None
    assert ddr.doc_type is DocumentType.DDR
    assert dgos is not None
    assert dgos.doc_type is DocumentType.DGOS


def test_classify_returns_none_for_unknown_forms() -> None:
    assert classify("Monthly Production Report", load_templates()) is None


def test_document_id_is_readable_and_falls_back_to_the_hash() -> None:
    assert document_id(DocumentType.DDR, "Well A-1", 32, "f" * 64) == "ddr-well-a-1-0032"
    assert document_id(DocumentType.GENERIC, None, None, "abc12345ff") == "generic-unknown-abc12345"
