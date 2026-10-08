from __future__ import annotations

import pytest

from wellscope.domain.text import normalize_for_index, search_terms


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('Drill 17½" hole', 'Drill 17-1/2" hole'),
        ("POOH 14¾ BHA", "POOH 14-3/4 BHA"),
        ("to 2349 mMDDF.", "to 2349 m MDDF"),
        ("Bit (PDC), then", "Bit PDC then"),
        ("12-1/4 x 14 UR BHA", "12-1/4 x 14 UR BHA"),
        ("10.0ppg SBM", "10.0ppg SBM"),
        ("17½” x 20” UR", '17-1/2" x 20" UR'),
    ],
)
def test_normalize_for_index_keeps_sizes_and_codes_searchable(raw: str, expected: str) -> None:
    assert normalize_for_index(raw) == expected


def test_search_terms_drop_stopwords_in_both_languages_and_deduplicate() -> None:
    terms = search_terms("Berapa daily cost pada report 32 dan the daily NPT?")
    assert terms == ["daily", "cost", "report", "32", "npt"]


def test_search_terms_keep_hyphenated_sizes_and_decimal_values() -> None:
    assert search_terms('What happened in the 17½" hole at 10.0ppg?') == [
        "happened",
        "17-1/2",
        "hole",
        "10.0ppg",
    ]
