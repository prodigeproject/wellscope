"""Totals computed from a report's operations table; the report itself does not print them.

Language models add up columns unreliably, so questions such as "how many hours was the rig
on standby?" are answered from these exact, citable totals instead.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from wellscope.domain.documents import Operation

INTRO = (
    "Computed by WellScope from the operations table (these totals are not printed in the report)."
)
GROUPINGS: tuple[tuple[str, Callable[[Operation], str | None]], ...] = (
    ("rig status", lambda operation: operation.rig_status),
    ("productive code", lambda operation: operation.productive_code),
    ("phase", lambda operation: operation.phase_code),
    ("activity", lambda operation: operation.activity_code),
)


def operation_totals(operations: Sequence[Operation]) -> str:
    """Hours in total, of NPT, and per rig status, productive code, phase and activity."""
    timed = sorted((op for op in operations if op.hours is not None), key=lambda op: op.seq)
    if not timed:
        return ""
    npt = [operation for operation in timed if operation.npt]
    lines = [
        INTRO,
        f"- Total: {_hours(timed)} in {len(timed)} rows",
        f"- NPT: {_hours(npt)} ({_spans(npt)})" if npt else "- NPT: 0.00 h",
    ]
    for label, key in GROUPINGS:
        groups: dict[str, list[Operation]] = {}
        for operation in timed:
            value = key(operation)
            if value:
                groups.setdefault(value, []).append(operation)
        if groups:
            totals = "; ".join(
                f"{name} {_hours(ops)} ({_spans(ops)})" for name, ops in groups.items()
            )
            lines.append(f"- By {label}: {totals}")
    return "\n".join(lines)


def _hours(operations: Sequence[Operation]) -> str:
    return f"{sum(operation.hours or 0.0 for operation in operations):.2f} h"


def _spans(operations: Sequence[Operation]) -> str:
    """Time ranges of the rows, touching ranges merged (``17:00–18:00, 18:00–24:00`` → one)."""
    spans: list[list[str]] = []
    for operation in operations:
        if spans and spans[-1][1] == operation.start:
            spans[-1][1] = operation.end
        else:
            spans.append([operation.start, operation.end])
    return ", ".join(f"{start}–{end}" for start, end in spans)
