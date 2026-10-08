"""Builders for domain objects used across tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from wellscope.domain.catalog import CatalogEntry
from wellscope.domain.documents import (
    DocumentType,
    FieldValue,
    NextDayOperations,
    Operation,
    ParserInfo,
    QualityCheck,
    ReportDocument,
    ReportInfo,
    SourceInfo,
    Table,
    TimedNote,
    WellInfo,
)
from wellscope.domain.glossary import Glossary, GlossaryEntry

SOURCE = SourceInfo(
    file_name="r.pdf",
    relative_path="r.pdf",
    sha256="0" * 64,
    page_count=2,
    parser=ParserInfo(name="t", version="1"),
)


def make_document() -> ReportDocument:
    return ReportDocument(
        doc_id="ddr-well-a-1-0012",
        doc_type=DocumentType.DDR,
        title="Daily Operation Report",
        source=SOURCE,
        well=WellInfo(name="WELL-A-1"),
        report=ReportInfo(number=12, date=date(2026, 1, 14)),
        fields={
            "daily_cost": FieldValue(
                label="Daily Cost", section="costs", raw="250,000.00", value=250000.0, page=1
            ),
            "spud_date": FieldValue(
                label="Spud date",
                section="well_info",
                raw="02/01/2026",
                date=date(2026, 1, 2),
                page=1,
            ),
            "end_date": FieldValue(label="End date", section="well_info", raw="", page=1),
        },
        operations=[
            Operation(
                seq=1,
                date=date(2026, 1, 14),
                start="16:15",
                end="19:00",
                hours=2.75,
                phase_code="D18",
                activity_code="DRL",
                productive_code="OPRN",
                npt=True,
                rig_status="OPRN",
                md_from_m=1500.0,
                description="Attempt to open reamer.",
                page=2,
            )
        ],
        next_day=NextDayOperations(
            date=date(2026, 1, 15),
            entries=[
                TimedNote(start="00:00", end="02:00", description="Pull out of hole.", page=2)
            ],
        ),
        tables=[
            Table(
                section="lot_fit", page=2, header_rows=1, rows=[["EMW", "MAASP"], ["15.0", "2,000"]]
            )
        ],
        quality=[
            QualityCheck(id="dates.x", ok=False, severity="warning", detail="spud date is odd"),
            QualityCheck(id="ok.check", ok=True, severity="warning", detail="fine"),
        ],
    )


def make_glossary(*entries: GlossaryEntry) -> Glossary:
    return Glossary(source=SOURCE, entries=list(entries))


def make_catalog_entry(
    doc_id: str, doc_type: str, number: int, day: date, start: datetime, hours: int = 24
) -> CatalogEntry:
    return CatalogEntry(
        doc_id=doc_id,
        doc_type=doc_type,
        label=f"{doc_type} #{number} ({day.isoformat()})",
        title="",
        well="WELL-B-2",
        rig="RIG-7",
        report_number=number,
        report_date=day,
        period_start=start,
        period_end=start + timedelta(hours=hours),
        quality_status="ok",
        summary="",
    )
