from __future__ import annotations

from datetime import date

from wellscope.domain.documents import (
    DocumentType,
    FieldValue,
    Operation,
    PageText,
    ParserInfo,
    ReportDocument,
    ReportInfo,
    SourceInfo,
)
from wellscope.ingestion.quality import check_document, cross_document_findings, document_status

SOURCE = SourceInfo(
    file_name="r.pdf", relative_path="r.pdf", sha256="0" * 64, page_count=1,
    parser=ParserInfo(name="test", version="1"),
)  # fmt: skip


def operation(seq: int, start: str, end: str, hours: float, *, npt: bool = False) -> Operation:
    return Operation(seq=seq, start=start, end=end, hours=hours, npt=npt, description="op", page=1)


def field(raw: str, *, value: float | None = None, day: date | None = None) -> FieldValue:
    return FieldValue(label="l", section="s", raw=raw, value=value, date=day, page=1)


def document(**changes: object) -> ReportDocument:
    base = ReportDocument(
        doc_id="ddr-a-0001",
        doc_type=DocumentType.DDR,
        title="Daily Operation Report",
        source=SOURCE,
        report=ReportInfo(number=1, date=date(2026, 1, 10)),
        pages=[PageText(number=1, text="", visible_ratio=1.0)],
    )
    return base.model_copy(update=changes)


def checks(doc: ReportDocument) -> dict[str, tuple[bool, str]]:
    return {check.id: (check.ok, check.detail) for check in check_document(doc)}


def test_operations_must_cover_24_hours() -> None:
    full = document(
        operations=[operation(1, "00:00", "12:00", 12), operation(2, "12:00", "24:00", 12)]
    )
    short = document(operations=[operation(1, "00:00", "20:00", 20)])
    assert checks(full)["operations.hours_total"][0] is True
    assert checks(short)["operations.hours_total"] == (False, "20.00 h of 24.00 h")


def test_npt_rows_must_match_the_header_daily_npt() -> None:
    ops = [operation(1, "00:00", "23:00", 23), operation(2, "23:00", "24:00", 1, npt=True)]
    matching = document(operations=ops, fields={"daily_npt": field("1.00 hr", value=1.0)})
    differing = document(operations=ops, fields={"daily_npt": field("2.00 hr", value=2.0)})
    assert checks(matching)["operations.npt_matches_header"][0] is True
    assert checks(differing)["operations.npt_matches_header"][0] is False


def test_row_hours_must_match_their_time_range() -> None:
    doc = document(
        operations=[operation(1, "00:00", "12:00", 11), operation(2, "12:00", "24:00", 12)]
    )
    assert checks(doc)["operations.row_hours"] == (
        False,
        "rows with hours not matching their time range: 1",
    )


def test_spud_date_after_report_date_is_flagged() -> None:
    doc = document(fields={"spud_date": field("27/06/2027", day=date(2027, 6, 27))})
    ok, detail = checks(doc)["dates.spud_before_report"]
    assert ok is False
    assert "2027-06-27" in detail


def test_next_bop_test_before_last_test_is_flagged() -> None:
    doc = document(
        fields={
            "last_bop_pressure_test": field("29/07/2026", day=date(2026, 7, 29)),
            "next_bop_test_due": field("20/06/2026", day=date(2026, 6, 20)),
        }
    )
    assert checks(doc)["dates.bop_test_order"][0] is False


def test_document_status_reports_the_worst_failed_severity() -> None:
    assert document_status(check_document(document())) == "ok"
    late_spud = document(fields={"spud_date": field("x", day=date(2027, 1, 1))})
    assert document_status(check_document(late_spud)) == "warning"


def test_cross_document_findings_report_conflicting_spud_dates() -> None:
    first = document(doc_id="a", fields={"spud_date": field("27-06-2026", day=date(2026, 6, 27))})
    second = document(doc_id="b", fields={"spud_date": field("27/06/2027", day=date(2027, 6, 27))})
    same = document(doc_id="c", fields={"spud_date": field("27/06/2026", day=date(2026, 6, 27))})
    findings = cross_document_findings([first, second, same])
    assert [finding.id for finding in findings] == ["conflict.spud_date"]
    assert {value.value for value in findings[0].values} == {"2026-06-27", "2027-06-27"}
    assert cross_document_findings([first, same]) == []
