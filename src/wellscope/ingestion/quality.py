"""Data-quality checks: invariants inside one report and conflicts between reports.

Findings never change source values. They are recorded so answers can mention them and so a
parser regression shows up as a failed invariant instead of silently wrong data.
"""

from __future__ import annotations

from collections.abc import Sequence

from wellscope.domain.catalog import ConflictValue, CrossDocumentFinding
from wellscope.domain.documents import FieldValue, QualityCheck, ReportDocument

HOURS_PER_DAY = 24.0
HOURS_TOLERANCE = 0.01
LOW_VISIBILITY = 0.5
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}
CONFLICT_FIELDS = {"spud_date": "Spud date", "afe_number": "AFE number"}


def check_document(document: ReportDocument) -> list[QualityCheck]:
    """Every check that applies to ``document``."""
    checks = [_identity(document), _visibility(document)]
    if document.operations:
        checks += [_operations_total(document), _npt_matches_header(document)]
        checks += [_row_hours(document)]
    for check in (_spud_before_report(document), _bop_test_order(document)):
        if check is not None:
            checks.append(check)
    return checks


def document_status(checks: Sequence[QualityCheck]) -> str:
    """``ok`` or the worst severity among failed checks."""
    failed = [check.severity for check in checks if not check.ok]
    return max(failed, key=SEVERITY_ORDER.__getitem__) if failed else "ok"


def cross_document_findings(documents: Sequence[ReportDocument]) -> list[CrossDocumentFinding]:
    """Facts that different documents report differently (e.g. the spud date)."""
    findings = []
    for key, label in CONFLICT_FIELDS.items():
        values = [
            ConflictValue(doc_id=document.doc_id, value=_normalised(document.fields[key]))
            for document in documents
            if key in document.fields and document.fields[key].raw
        ]
        if len({value.value for value in values}) > 1:
            findings.append(
                CrossDocumentFinding(
                    id=f"conflict.{key}",
                    severity="warning",
                    detail=f"{label} differs between documents.",
                    values=values,
                )
            )
    return findings


def _identity(document: ReportDocument) -> QualityCheck:
    ok = document.report.number is not None and document.report.date is not None
    detail = "report number and date found" if ok else "report number or date missing"
    return QualityCheck(id="report.identity", ok=ok, severity="warning", detail=detail)


def _visibility(document: ReportDocument) -> QualityCheck:
    lowest = min((page.visible_ratio for page in document.pages), default=1.0)
    detail = f"lowest visible-text ratio {lowest:.2f}"
    if lowest < 1:
        detail += " (hidden text layers removed)"
    return QualityCheck(
        id="pdf.visibility", ok=lowest >= LOW_VISIBILITY, severity="warning", detail=detail
    )


def _operations_total(document: ReportDocument) -> QualityCheck:
    total = sum(operation.hours or 0.0 for operation in document.operations)
    ok = abs(total - HOURS_PER_DAY) <= HOURS_TOLERANCE
    return QualityCheck(
        id="operations.hours_total", ok=ok, severity="warning", detail=f"{total:.2f} h of 24.00 h"
    )


def _npt_matches_header(document: ReportDocument) -> QualityCheck:
    rows = sum(operation.hours or 0.0 for operation in document.operations if operation.npt)
    header = document.fields.get("daily_npt")
    if header is None or header.value is None:
        detail = f"{rows:.2f} h flagged as NPT; no daily NPT in header"
        return QualityCheck(
            id="operations.npt_matches_header", ok=True, severity="info", detail=detail
        )
    ok = abs(rows - header.value) <= HOURS_TOLERANCE
    detail = f"{rows:.2f} h flagged as NPT vs {header.value:.2f} h in header"
    return QualityCheck(
        id="operations.npt_matches_header", ok=ok, severity="warning", detail=detail
    )


def _row_hours(document: ReportDocument) -> QualityCheck:
    mismatched = [
        str(operation.seq)
        for operation in document.operations
        if operation.hours is not None
        and abs(operation.hours - _span_hours(operation.start, operation.end)) > HOURS_TOLERANCE
    ]
    detail = f"rows with hours not matching their time range: {', '.join(mismatched) or 'none'}"
    return QualityCheck(
        id="operations.row_hours", ok=not mismatched, severity="warning", detail=detail
    )


def _spud_before_report(document: ReportDocument) -> QualityCheck | None:
    spud = document.fields.get("spud_date")
    if spud is None or spud.date is None or document.report.date is None:
        return None
    ok = spud.date <= document.report.date
    detail = f"spud date {spud.date} vs report date {document.report.date}"
    return QualityCheck(id="dates.spud_before_report", ok=ok, severity="warning", detail=detail)


def _bop_test_order(document: ReportDocument) -> QualityCheck | None:
    last = document.fields.get("last_bop_pressure_test")
    due = document.fields.get("next_bop_test_due")
    if last is None or due is None or last.date is None or due.date is None:
        return None
    ok = due.date >= last.date
    detail = f"next BOP test due {due.date} vs last BOP pressure test {last.date}"
    return QualityCheck(id="dates.bop_test_order", ok=ok, severity="warning", detail=detail)


def _span_hours(start: str, end: str) -> float:
    def minutes(clock: str) -> int:
        hours, mins = clock.split(":")
        return int(hours) * 60 + int(mins)

    return (minutes(end) - minutes(start)) / 60


def _normalised(field: FieldValue) -> str:
    return field.date.isoformat() if field.date is not None else " ".join(field.raw.split())
