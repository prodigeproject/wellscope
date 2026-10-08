from __future__ import annotations

import pytest
from pydantic import ValidationError

from wellscope.domain.documents import DocumentType
from wellscope.ingestion.pdf.templates import SectionSpec, load_templates, parse_template


def test_packaged_templates_load_and_cover_both_report_families() -> None:
    templates = {template.doc_type for template in load_templates()}
    assert templates == {DocumentType.DDR, DocumentType.DGOS}


def test_section_titles_match_exactly_or_by_declared_prefix() -> None:
    safety = SectionSpec(name="safety", titles=("SAFETY",))
    bha = SectionSpec(name="bha", titles=("BHA no.#*",))
    assert safety.matches("SAFETY")
    assert not safety.matches("SAFETY CARDS")
    assert bha.matches("BHA no.# 3 Bit no.:")


def test_parse_template_rejects_references_to_unknown_fields() -> None:
    text = """
    id: broken@1
    doc_type: DDR
    title: Broken
    signatures: ["Broken"]
    period: {start_offset_hours: 0, length_hours: 24}
    report_number_field: report_number
    report_date_field: report_date
    well: {name: well}
    fields:
      report_number: {section: header, kind: integer, labels: ["Report no."]}
    """
    with pytest.raises(ValidationError, match="unknown fields"):
        parse_template(text)


def test_parse_template_rejects_unknown_keys() -> None:
    text = """
    id: typo@1
    doc_type: DGOS
    title: Typo
    signatures: ["Typo"]
    period: {start_offset_hours: 0, length_hours: 24}
    report_number_field: n
    report_date_field: d
    well: {}
    fields:
      n: {section: s, labels: ["N"], kind: integer}
      d: {section: s, labels: ["D"], kind: date, colour: red}
    """
    with pytest.raises(ValidationError, match="colour"):
        parse_template(text)
