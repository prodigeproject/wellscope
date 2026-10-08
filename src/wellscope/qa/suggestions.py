"""Example questions for the empty chat, built from the reports that are actually indexed."""

from __future__ import annotations

from collections.abc import Sequence

from wellscope.domain.catalog import CatalogEntry

MAX_SUGGESTIONS = 6
GENERAL = (
    "What is the latest reported depth?",
    "Apa kepanjangan NPT?",
    "Laporan apa saja yang tersedia?",
)


def suggested_questions(catalog: Sequence[CatalogEntry]) -> list[str]:
    """Questions about the newest report of each type, then general ones."""
    questions: list[str] = []
    newest = _newest_by_type(catalog)
    if (ddr := newest.get("DDR")) is not None:
        questions += [
            f"What was the daily cost in DDR {ddr.report_number}?",
            f"Operasi apa yang tercatat sebagai NPT pada DDR {ddr.report_number}?",
        ]
    if (dgos := newest.get("DGOS")) is not None:
        questions.append(f"What was the current operation in DGOS {dgos.report_number}?")
    return [*questions, *GENERAL][:MAX_SUGGESTIONS] if catalog else []


def _newest_by_type(catalog: Sequence[CatalogEntry]) -> dict[str, CatalogEntry]:
    newest: dict[str, CatalogEntry] = {}
    for entry in catalog:
        if entry.report_number is None or entry.report_date is None:
            continue
        current = newest.get(entry.doc_type)
        if current is None or (current.report_date or entry.report_date) < entry.report_date:
            newest[entry.doc_type] = entry
    return newest
