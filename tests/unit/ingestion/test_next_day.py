from __future__ import annotations

from datetime import date

from wellscope.ingestion.pdf.operations import parse_next_day, split_next_day

SEPARATOR = r"^(?:\*{6,}|_{6,})$"


def test_split_next_day_cuts_at_a_star_or_underscore_separator() -> None:
    lines = ["Retrieve bearing assembly.", "**********", "20th July 2026", "00:00 - 00:15 hrs"]
    before, after = split_next_day(lines, SEPARATOR)
    assert before == ["Retrieve bearing assembly."]
    assert after == ["20th July 2026", "00:00 - 00:15 hrs"]
    assert split_next_day(["a", "________", "b"], SEPARATOR) == (["a"], ["b"])


def test_split_next_day_keeps_everything_when_there_is_no_separator() -> None:
    assert split_next_day(["one", "two"], SEPARATOR) == (["one", "two"], [])


def test_parse_next_day_reads_date_and_timed_entries() -> None:
    lines = [
        "20th July 2026",
        "00:00 - 00:15 hrs",
        "Continue retrieve bearing assembly.",
        "00:15 - 01:30 hrs",
        "Set bore protector.",
        "Note:",
        "- Monitor well on trip tank.",
    ]
    result = parse_next_day(lines, report_date=date(2026, 7, 19), page=3)
    assert result.date == date(2026, 7, 20)
    assert [(entry.start, entry.end) for entry in result.entries] == [
        ("00:00", "00:15"),
        ("00:15", "01:30"),
    ]
    assert result.entries[1].description == (
        "Set bore protector.\nNote:\n- Monitor well on trip tank."
    )


def test_parse_next_day_defaults_to_the_day_after_the_report() -> None:
    result = parse_next_day(["02:00 - 03:00 hrs", "Pull out of hole."], date(2026, 8, 9), 2)
    assert result.date == date(2026, 8, 10)
    assert result.entries[0].description == "Pull out of hole."
