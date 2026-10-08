from __future__ import annotations

from datetime import date, datetime

from tests.support.documents import make_catalog_entry
from wellscope.qa.suggestions import suggested_questions


def test_suggestions_ask_about_the_newest_report_of_each_type() -> None:
    catalog = [
        make_catalog_entry("ddr-32", "DDR", 32, date(2026, 7, 19), datetime(2026, 7, 19)),
        make_catalog_entry("ddr-53", "DDR", 53, date(2026, 8, 9), datetime(2026, 8, 9)),
        make_catalog_entry("dgos-84", "DGOS", 84, date(2026, 9, 10), datetime(2026, 9, 9, 6)),
    ]
    questions = suggested_questions(catalog)
    text = " ".join(questions)
    assert "DDR 53" in text
    assert "DGOS 84" in text
    assert "DDR 32" not in text
    assert len(questions) == 6


def test_an_empty_catalog_has_no_suggestions() -> None:
    assert suggested_questions([]) == []
