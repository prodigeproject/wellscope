"""Parts of the geological summary that are not key-value pairs: remarks and progress grids."""

from __future__ import annotations

import re
from collections.abc import Sequence

from wellscope.domain.documents import FieldValue, Remark, Table
from wellscope.domain.quantities import parse_quantity
from wellscope.ingestion.pdf.grid import Section, read_grid
from wellscope.ingestion.pdf.layout import PageLayout
from wellscope.ingestion.pdf.templates import FormTemplate, GridSpec

REMARKS_KIND = "remarks"
PAIR_KEYS = "|"
PAIR_VALUES = "/"
_NUMBER = re.compile(r"\d+")


def read_remarks(sections: Sequence[Section]) -> list[Remark]:
    """Numbered remarks; an unnumbered line continues the previous remark."""
    remarks: list[Remark] = []
    for section in sections:
        if section.spec.kind != REMARKS_KIND:
            continue
        for row in section.rows():
            number, text = row[0].strip(), " ".join(row[1:]).strip()
            if _NUMBER.fullmatch(number) and text:
                remarks.append(Remark(number=int(number), text=text))
            elif remarks and (continuation := f"{number} {text}".strip()):
                last = remarks[-1]
                remarks[-1] = Remark(number=last.number, text=f"{last.text} {continuation}")
    return remarks


def read_grids(
    pages: Sequence[PageLayout], template: FormTemplate
) -> tuple[list[Table], dict[str, FieldValue]]:
    """Tables for every templated grid and the fields mapped from their value rows."""
    tables: list[Table] = []
    fields: dict[str, FieldValue] = {}
    for spec in template.grids:
        for page in pages:
            rows = read_grid(page, spec)
            if rows:
                tables.append(Table(section=spec.name, page=page.number, header_rows=1, rows=rows))
                fields.update(_grid_fields(spec, rows, page.number))
                break
    return tables, fields


def _grid_fields(spec: GridSpec, rows: list[list[str]], page: int) -> dict[str, FieldValue]:
    header, values = rows[0], rows[1:]
    fields: dict[str, FieldValue] = {}
    for row_keys, row in zip(spec.rows, values, strict=False):
        prefix = "" if row is values[0] else f"{row[0]} "
        for column, key in enumerate(row_keys):
            if key is None or column >= len(row):
                continue
            label = f"{prefix}{header[column]}".strip()
            keys = key.split(PAIR_KEYS)
            parts = row[column].split(PAIR_VALUES) if len(keys) > 1 else [row[column]]
            for name, part in zip(keys, parts, strict=False):
                fields[name] = _value(label, spec.name, part.strip(), page)
    return fields


def _value(label: str, section: str, raw: str, page: int) -> FieldValue:
    quantity = parse_quantity(raw)
    return FieldValue(
        label=label,
        section=section,
        raw=raw,
        value=quantity.value,
        unit=quantity.unit,
        page=page,
    )
