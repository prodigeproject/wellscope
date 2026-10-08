"""Typed field values read from key-value blocks with a template's labels."""

from __future__ import annotations

from collections.abc import Sequence

from wellscope.domain.dates import parse_date
from wellscope.domain.documents import FieldValue
from wellscope.domain.numbers import parse_number
from wellscope.domain.quantities import parse_quantity
from wellscope.ingestion.pdf.grid import Section, text_blocks
from wellscope.ingestion.pdf.kv import extract_pairs
from wellscope.ingestion.pdf.layout import PageLayout
from wellscope.ingestion.pdf.templates import STOP_KEY, FieldSpec, FormTemplate

KV_KIND = "kv"


def extract_fields(
    pages: Sequence[PageLayout], template: FormTemplate, sections: Sequence[Section]
) -> dict[str, FieldValue]:
    """Every templated field found on the pages; the first non-empty value of a key wins."""
    colon_specs = template.label_specs(heading=False)
    heading_specs = template.label_specs(heading=True)
    found: dict[str, FieldValue] = {}
    for page in pages:
        regions = [
            section.region
            for section in sections
            if section.page is page and section.spec.kind == KV_KIND and section.spec.merge_cells
        ]
        for lines in text_blocks(page, regions):
            for key, raw in extract_pairs(lines, colon_specs, heading_specs).items():
                if key == STOP_KEY:
                    continue
                current = found.get(key)
                if current is None or (not current.raw and raw):
                    found[key] = to_field_value(template.fields[key], raw, page.number)
    return found


def to_field_value(spec: FieldSpec, raw: str, page: int) -> FieldValue:
    """Interpret ``raw`` according to the field kind while keeping the verbatim text."""
    text = raw.strip()
    common = {"label": spec.labels[0], "section": spec.section, "raw": text, "page": page}
    if spec.kind == "quantity":
        quantity = parse_quantity(text)
        return FieldValue(**common, value=quantity.value, unit=quantity.unit)
    if spec.kind == "integer":
        return FieldValue(**common, value=parse_number(text.split(" ")[0]) if text else None)
    if spec.kind == "date":
        return FieldValue(**common, date=parse_date(text))
    return FieldValue(**common)
