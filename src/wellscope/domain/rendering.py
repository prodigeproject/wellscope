"""Markdown views of documents and glossary entries, shared by indexing and answering.

The same passages feed the search index and the model's context, so what retrieval finds is
exactly what the model reads. Blank fields are rendered explicitly so "not recorded" can be
answered from the source instead of being guessed.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from wellscope.domain.documents import DocumentType, Operation, ReportDocument
from wellscope.domain.glossary import GlossaryEntry, GlossaryStatus

BLANK = "(blank)"
SUMMARY_FIELDS = (
    "md",
    "tvd",
    "depth_mddf",
    "depth_tvdss",
    "current_hole_size",
    "daily_cost",
    "cumm_cost",
    "cost_musd",
    "daily_npt",
    "cumm_npt",
    "mud_weight",
    "phase",
    "current_status",
    "current_operation",
)
SUMMARY_VALUE_LIMIT = 160
SECTION_TITLES = {
    "header": "Report header",
    "well_info": "Well info",
    "depth_days": "Depth and days",
    "costs": "Costs (USD)",
    "status": "Status",
    "mud_check": "Mud check",
    "bha": "BHA",
    "gas_readings": "Gas readings",
    "mud_volume": "Mud volume",
    "personnel": "Personnel",
    "weather": "Weather",
    "safety": "Safety",
    "well_data": "Well data",
    "operation_update": "Operation update (06:00 to 06:00)",
    "objectives": "Objectives and offset wells",
    "location": "Location",
    "rig": "Rig information",
    "progress_summary": "Progress summary (actual and AFE)",
    "progress": "Progress and mud weight",
}


@dataclass(frozen=True, slots=True)
class Passage:
    """A titled piece of a document that is indexed and quoted as one unit."""

    key: str
    kind: str
    title: str
    page: int | None
    body: str


def document_label(document: ReportDocument) -> str:
    """Short human label such as ``DDR #32 (2026-07-19)``."""
    if document.doc_type is DocumentType.GENERIC:
        return document.title
    number = f" #{document.report.number}" if document.report.number is not None else ""
    day = f" ({document.report.date.isoformat()})" if document.report.date else ""
    return f"{document.doc_type.value}{number}{day}"


def catalog_summary(document: ReportDocument) -> str:
    """One line of key facts for the catalog card (only fields the report actually has)."""
    facts = []
    for key in SUMMARY_FIELDS:
        field = document.fields.get(key)
        if field is not None and field.raw:
            value = field.raw[:SUMMARY_VALUE_LIMIT]
            facts.append(f"{field.label}: {value}")
    return "; ".join(facts)


def document_passages(document: ReportDocument) -> list[Passage]:
    """Every passage of a document, in reading order; empty passages are omitted."""
    passages = [
        *_field_passages(document),
        *_operation_passages(document),
        *_next_day_passages(document),
        *_remark_passages(document),
        *_table_passages(document),
        *_page_passages(document),
        *_quality_passages(document),
    ]
    return [passage for passage in passages if passage.body.strip()]


def passage_text(document: ReportDocument, passage: Passage) -> str:
    """Passage body prefixed with a provenance line."""
    parts = [document_label(document), document.well.name or "", passage.title]
    if passage.page is not None:
        parts.append(f"p.{passage.page}")
    header = " · ".join(part for part in parts if part)
    return f"[{header}]\n{passage.body}"


def render_document(document: ReportDocument) -> str:
    """The whole document as markdown, used when a question targets this report."""
    title = " · ".join(part for part in (document_label(document), document.well.name) if part)
    blocks = [f"# {title}"]
    for passage in document_passages(document):
        page = f" (p.{passage.page})" if passage.page is not None else ""
        blocks.append(f"## {passage.title}{page}\n{passage.body}")
    return "\n\n".join(blocks)


def glossary_passage(entry: GlossaryEntry) -> Passage:
    """One glossary entry, stating how certain the glossary is about it."""
    meaning = entry.expansion or "meaning unknown"
    body = f"{entry.term} — {meaning}"
    if entry.description:
        body += f": {entry.description}"
    if entry.status is GlossaryStatus.TO_BE_CONFIRMED:
        body += " (The glossary marks this definition as 'to be confirmed'.)"
    elif entry.status is GlossaryStatus.UNKNOWN:
        body += " (The glossary marks this term as unknown.)"
    extra_spellings = [alias for alias in entry.aliases if alias != entry.term]
    if extra_spellings and " / " not in entry.term:
        body += f" Also written: {', '.join(extra_spellings)}."
    if entry.senses:
        senses = " ".join(f"{index}) {sense}" for index, sense in enumerate(entry.senses, 1))
        body += f" Meanings: {senses}."
    return Passage(
        key=entry.id, kind="glossary", title=f"Glossary: {entry.term}", page=None, body=body
    )


def _field_passages(document: ReportDocument) -> Iterator[Passage]:
    sections: dict[str, list[str]] = {}
    pages: dict[str, int] = {}
    for field in document.fields.values():
        value = field.raw or BLANK
        if field.date is not None and field.date.isoformat() not in value:
            value += f" ({field.date.isoformat()})"
        sections.setdefault(field.section, []).append(f"- {field.label}: {value}")
        pages.setdefault(field.section, field.page)
    for section, lines in sections.items():
        title = SECTION_TITLES.get(section, section.replace("_", " ").capitalize())
        yield Passage(f"fields:{section}", "facts", title, pages[section], "\n".join(lines))


def _operation_passages(document: ReportDocument) -> Iterator[Passage]:
    for operation in document.operations:
        yield Passage(
            key=f"operation:{operation.seq}",
            kind="operation",
            title=f"Operation {operation.start}–{operation.end}",
            page=operation.page,
            body=f"{_operation_summary(operation)}\n{operation.description}",
        )


def _operation_summary(operation: Operation) -> str:
    day = f"{operation.date.isoformat()} " if operation.date else ""
    parts = [f"{day}{operation.start}–{operation.end} ({operation.hours:g} h)"]
    labelled = (
        ("phase", operation.phase_code),
        ("activity", operation.activity_code),
        ("code", operation.productive_code),
        ("rig status", operation.rig_status),
    )
    parts += [f"{label} {value}" for label, value in labelled if value]
    parts.append(f"NPT: {'yes' if operation.npt else 'no'}")
    if operation.md_from_m is not None:
        parts.append(f"MD from {operation.md_from_m:.2f} m")
    return " · ".join(parts)


def _next_day_passages(document: ReportDocument) -> Iterator[Passage]:
    if document.next_day is None:
        return
    day = document.next_day.date.isoformat() if document.next_day.date else "next day"
    for index, entry in enumerate(document.next_day.entries, 1):
        span = f" {entry.start}–{entry.end}" if entry.start and entry.end else ""
        yield Passage(
            key=f"next_day:{index}",
            kind="next_day",
            title=f"Next-day operation {day}{span}",
            page=entry.page,
            body=entry.description,
        )


def _remark_passages(document: ReportDocument) -> Iterator[Passage]:
    if document.remarks:
        body = "\n".join(f"{remark.number}. {remark.text}" for remark in document.remarks)
        yield Passage("remarks", "remarks", "Remarks", None, body)


def _table_passages(document: ReportDocument) -> Iterator[Passage]:
    for index, table in enumerate(document.tables, 1):
        width = max((len(row) for row in table.rows), default=0)
        lines = []
        for row_number, row in enumerate(table.rows, 1):
            lines.append("| " + " | ".join(cell or " " for cell in row) + " |")
            if row_number == table.header_rows:
                lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
        title = SECTION_TITLES.get(table.section, table.section.replace("_", " ").capitalize())
        yield Passage(f"table:{index}", "table", f"Table: {title}", table.page, "\n".join(lines))


def _page_passages(document: ReportDocument) -> Iterator[Passage]:
    if document.doc_type is DocumentType.GENERIC:
        for page in document.pages:
            yield Passage(
                f"page:{page.number}", "text", f"Page {page.number}", page.number, page.text
            )


def _quality_passages(document: ReportDocument) -> Iterator[Passage]:
    notes = [f"- {check.detail} ({check.severity})" for check in document.quality if not check.ok]
    if notes:
        yield Passage("quality", "quality", "Data-quality notes", None, "\n".join(notes))
