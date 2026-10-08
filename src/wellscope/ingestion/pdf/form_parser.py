"""Assemble a report document from page layouts and the template of its form family."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, time, timedelta

from wellscope.domain.documents import (
    DocumentType,
    FieldValue,
    PageText,
    ReportDocument,
    ReportInfo,
    SectionText,
    SourceInfo,
    Table,
    WellInfo,
)
from wellscope.ingestion.pdf.dgos import read_grids, read_remarks
from wellscope.ingestion.pdf.fields import extract_fields
from wellscope.ingestion.pdf.grid import Section, find_sections
from wellscope.ingestion.pdf.layout import PageLayout
from wellscope.ingestion.pdf.operations import parse_operations
from wellscope.ingestion.pdf.templates import FormTemplate

TABLE_KIND = "table"
KV_KIND = "kv"
VISIBLE_RATIO_DIGITS = 3
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def parse_report(
    pages: Sequence[PageLayout], template: FormTemplate, source: SourceInfo
) -> ReportDocument:
    """Typed fields, operations, remarks, tables and page text of one templated report."""
    sections = find_sections(pages, template.sections)
    fields = extract_fields(pages, template, sections)
    grid_tables, grid_fields = read_grids(pages, template)
    fields.update({key: value for key, value in grid_fields.items() if key not in fields})
    report = _report_info(template, fields)
    operations, next_day = (
        parse_operations(sections, template.operations, report.date)
        if template.operations
        else ([], None)
    )
    well = _well_info(template, fields, pages)
    return ReportDocument(
        doc_id=document_id(template.doc_type, well.name, report.number, source.sha256),
        doc_type=template.doc_type,
        title=template.title,
        source=source,
        well=well,
        report=report,
        fields=fields,
        operations=operations,
        next_day=next_day,
        remarks=read_remarks(sections),
        tables=[*grid_tables, *_tables(sections)],
        sections=[
            SectionText(section=section.name, page=section.page.number, text=section.text())
            for section in sections
            if section.spec.kind == KV_KIND
        ],
        pages=page_texts(pages),
    )


def document_id(doc_type: DocumentType, well: str | None, number: int | None, sha256: str) -> str:
    """Stable, readable id such as ``ddr-well-a-1-0032``."""
    slug = _NON_ALNUM.sub("-", (well or "unknown").lower()).strip("-") or "unknown"
    suffix = f"{number:04d}" if number is not None else sha256[:8]
    return f"{doc_type.value.lower()}-{slug}-{suffix}"


def page_texts(pages: Sequence[PageLayout]) -> list[PageText]:
    """Visible text of every page with its visibility ratio."""
    return [
        PageText(
            number=page.number,
            text=page.text(),
            visible_ratio=round(page.visibility.ratio, VISIBLE_RATIO_DIGITS),
        )
        for page in pages
    ]


def _tables(sections: Sequence[Section]) -> list[Table]:
    return [
        Table(
            section=section.name,
            page=section.page.number,
            header_rows=section.spec.header_rows,
            rows=rows,
        )
        for section in sections
        if section.spec.kind == TABLE_KIND and (rows := section.rows())
    ]


def _report_info(template: FormTemplate, fields: Mapping[str, FieldValue]) -> ReportInfo:
    number_field = fields.get(template.report_number_field)
    date_field = fields.get(template.report_date_field)
    number = int(number_field.value) if number_field and number_field.value is not None else None
    day = date_field.date if date_field else None
    if day is None:
        return ReportInfo(number=number)
    start = datetime.combine(day, time()) + timedelta(hours=template.period.start_offset_hours)
    end = start + timedelta(hours=template.period.length_hours)
    return ReportInfo(number=number, date=day, period_start=start, period_end=end)


def _well_info(
    template: FormTemplate, fields: Mapping[str, FieldValue], pages: Sequence[PageLayout]
) -> WellInfo:
    values = {
        attribute: fields[key].raw
        for attribute, key in template.well.items()
        if key in fields and fields[key].raw
    }
    if template.operator_above_title and "operator" not in values and pages:
        operator = _line_above_title(pages[0], template.signatures)
        if operator:
            values["operator"] = operator
    return WellInfo.model_validate(values)


def _line_above_title(page: PageLayout, signatures: Sequence[str]) -> str | None:
    """Reports print the operator's name on the line above the report title."""
    lines = page.lines()
    for index, line in enumerate(lines):
        if index and any(signature.casefold() in line.text.casefold() for signature in signatures):
            return lines[index - 1].text
    return None
