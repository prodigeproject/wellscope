from __future__ import annotations

from wellscope.ingestion.pdf.geometry import (
    Box,
    Rule,
    Word,
    cluster_lines,
    column_bounds,
    split_into_columns,
    words_in,
)


def word(text: str, x0: float, top: float, width: float = 20.0, height: float = 8.0) -> Word:
    return Word(text=text, x0=x0, x1=x0 + width, top=top, bottom=top + height)


def test_cluster_lines_groups_words_sharing_a_baseline_and_orders_them() -> None:
    words = [word("B", 60, 100.6), word("A", 10, 100.0), word("C", 10, 112.0)]
    lines = cluster_lines(words)
    assert [line.text for line in lines] == ["A B", "C"]


def test_cluster_lines_does_not_split_a_line_at_bucket_boundaries() -> None:
    # Rounding-based bucketing (top / 2.5) would put 98.7 and 98.8 in different rows.
    lines = cluster_lines([word("left", 10, 98.7), word("right", 80, 98.8)])
    assert [line.text for line in lines] == ["left right"]


def test_column_bounds_use_vertical_rules_crossing_the_band() -> None:
    rules = [
        Rule(x0=10, x1=10, top=0, bottom=200),
        Rule(x0=50, x1=50, top=0, bottom=200),
        Rule(x0=120, x1=120, top=0, bottom=200),
        Rule(x0=80, x1=80, top=150, bottom=200),
    ]
    assert column_bounds(rules, top=90, bottom=110) == [(10, 50), (50, 120)]


def test_column_bounds_merge_double_lines() -> None:
    rules = [Rule(10, 10, 0, 100), Rule(10.6, 10.6, 0, 100), Rule(40, 40, 0, 100)]
    assert column_bounds(rules, top=40, bottom=60) == [(10, 40)]


def test_split_into_columns_assigns_words_by_centre() -> None:
    line = cluster_lines([word("0:00", 5, 10), word("1.50", 55, 10), word("Drill", 130, 10)])[0]
    cells = split_into_columns(line, [(0, 50), (50, 120), (120, 400)])
    assert cells == ["0:00", "1.50", "Drill"]


def test_words_in_keeps_only_words_centred_inside_the_box() -> None:
    words = [word("in", 10, 10), word("edge", 95, 10), word("out", 200, 10)]
    inside = words_in(words, Box(0, 0, 100, 50))
    assert [w.text for w in inside] == ["in"]
