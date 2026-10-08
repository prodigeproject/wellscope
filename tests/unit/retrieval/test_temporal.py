from __future__ import annotations

from datetime import date, datetime, timedelta

from wellscope.domain.catalog import CatalogEntry
from wellscope.retrieval.models import DocumentFilter
from wellscope.retrieval.temporal import resolve


def entry(doc_id: str, doc_type: str, number: int, day: date, start: datetime) -> CatalogEntry:
    hours = 30 if doc_type == "DDR" else 24
    return CatalogEntry(
        doc_id=doc_id,
        doc_type=doc_type,
        label=f"{doc_type} #{number} ({day})",
        title="",
        well="A-1",
        rig=None,
        report_number=number,
        report_date=day,
        period_start=start,
        period_end=start + timedelta(hours=hours),
        quality_status="ok",
        summary="",
    )


DDR_32 = entry("ddr-32", "DDR", 32, date(2026, 7, 19), datetime(2026, 7, 19))
DDR_53 = entry("ddr-53", "DDR", 53, date(2026, 8, 9), datetime(2026, 8, 9))
DGOS_72 = entry("dgos-72", "DGOS", 72, date(2026, 8, 29), datetime(2026, 8, 28, 6))
CATALOG = [DDR_32, DDR_53, DGOS_72]


def ids(filters: DocumentFilter) -> list[str]:
    return [item.doc_id for item in resolve(CATALOG, filters).entries]


def test_no_filter_keeps_every_report_and_is_not_unmatched() -> None:
    resolution = resolve(CATALOG, DocumentFilter())
    assert [item.doc_id for item in resolution.entries] == ["ddr-32", "ddr-53", "dgos-72"]
    assert not resolution.unmatched


def test_report_numbers_and_types_narrow_the_reports() -> None:
    assert ids(DocumentFilter(report_numbers=(53,))) == ["ddr-53"]
    assert ids(DocumentFilter(doc_types=("DGOS",))) == ["dgos-72"]


def test_a_date_matches_its_report_and_reports_whose_period_covers_it() -> None:
    assert ids(DocumentFilter(dates=(date(2026, 8, 29),))) == ["dgos-72"]
    assert ids(DocumentFilter(dates=(date(2026, 8, 28),))) == ["dgos-72"]
    assert ids(DocumentFilter(dates=(date(2026, 7, 20),))) == ["ddr-32"]


def test_reports_dated_on_the_requested_day_come_first() -> None:
    next_day = entry("ddr-33", "DDR", 33, date(2026, 7, 20), datetime(2026, 7, 20))
    resolution = resolve([DDR_32, next_day], DocumentFilter(dates=(date(2026, 7, 20),)))
    assert [item.doc_id for item in resolution.entries] == ["ddr-33", "ddr-32"]


def test_date_ranges_select_overlapping_periods() -> None:
    window = DocumentFilter(date_from=date(2026, 8, 1), date_to=date(2026, 8, 28))
    assert ids(window) == ["ddr-53", "dgos-72"]
    assert ids(DocumentFilter(date_from=date(2026, 8, 30))) == []


def test_latest_picks_the_newest_report_overall_or_per_requested_type() -> None:
    assert ids(DocumentFilter(latest=True)) == ["dgos-72"]
    assert ids(DocumentFilter(latest=True, doc_types=("DDR", "DGOS"))) == ["ddr-53", "dgos-72"]


def test_filters_that_match_nothing_are_unmatched() -> None:
    resolution = resolve(CATALOG, DocumentFilter(report_numbers=(72,), doc_types=("DDR",)))
    assert resolution.entries == ()
    assert resolution.unmatched
