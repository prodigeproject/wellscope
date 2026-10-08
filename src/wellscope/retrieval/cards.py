"""Synthetic sources: the report catalog and the cross-report conflicts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from wellscope.domain.catalog import CatalogEntry, ConflictRecord


def catalog_card(catalog: Sequence[CatalogEntry]) -> str:
    """One line per report: label, well, covered period, data quality and key facts."""
    lines = [f"[Report catalog: {len(catalog)} reports]"]
    for entry in catalog:
        period = f"covers {entry.period}" if entry.period else "period not stated"
        parts = [entry.label, entry.well or "well not stated", period]
        if entry.quality_status != "ok":
            parts.append(f"data-quality {entry.quality_status}")
        if entry.summary:
            parts.append(entry.summary)
        lines.append("- " + " · ".join(parts))
    return "\n".join(lines)


def conflict_card(conflicts: Sequence[ConflictRecord], labels: Mapping[str, str]) -> str:
    """Each conflict with the value every report gives."""
    lines = ["[Data conflicts between reports]"]
    for conflict in conflicts:
        values = "; ".join(
            f"{labels.get(doc_id, doc_id)} = {value}" for doc_id, value in conflict.values
        )
        lines.append(f"- {conflict.detail} Values: {values}")
    return "\n".join(lines)
