from __future__ import annotations

from wellscope.domain.documents import Operation
from wellscope.domain.operation_totals import operation_totals


def op(
    seq: int, start: str, end: str, hours: float, status: str, *, npt: bool = False
) -> Operation:
    return Operation(
        seq=seq,
        start=start,
        end=end,
        hours=hours,
        rig_status=status,
        phase_code="D18",
        npt=npt,
        description="work",
        page=1,
    )


def test_totals_group_hours_and_merge_touching_time_ranges() -> None:
    text = operation_totals(
        [
            op(1, "00:00", "12:00", 12, "OPRN"),
            op(2, "12:00", "17:00", 5, "OPRN"),
            op(3, "17:00", "18:00", 1, "STDBY"),
            op(4, "18:00", "24:00", 6, "STDBY"),
        ]
    )
    assert "- Total: 24.00 h in 4 rows" in text
    assert "- NPT: 0.00 h" in text
    assert "- By rig status: OPRN 17.00 h (00:00–17:00); STDBY 7.00 h (17:00–24:00)" in text
    assert "- By phase: D18 24.00 h (00:00–24:00)" in text


def test_npt_rows_are_totalled_with_their_times() -> None:
    text = operation_totals(
        [
            op(1, "20:00", "22:30", 2.5, "OPRN"),
            op(2, "22:30", "23:15", 0.75, "OPRN", npt=True),
            op(3, "23:15", "24:00", 0.75, "OPRN", npt=True),
        ]
    )
    assert "- NPT: 1.50 h (22:30–24:00)" in text


def test_a_report_without_operations_has_no_totals() -> None:
    assert operation_totals([]) == ""
