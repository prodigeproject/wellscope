from __future__ import annotations

import pytest

from wellscope.evals.report import summarize, to_markdown, wilson_interval
from wellscope.evals.scoring import ItemResult


def result(
    category: str, passed: bool, *, expected: str = "answered", status: str = "answered"
) -> ItemResult:
    return ItemResult(
        id=f"{category}-{passed}-{status}",
        category=category,
        lang="en",
        expected_status=expected,
        status=status,
        verified=True,
        passed=passed,
        status_ok=passed,
        content_ok=passed,
        citations_ok=True,
        missing=(),
        latency_ms=1000 if passed else 3000,
        input_tokens=100,
        output_tokens=10,
    )


def test_wilson_interval_is_bounded_and_centred_near_the_rate() -> None:
    low, high = wilson_interval(9, 10)
    assert 0.55 < low < 0.9 < high <= 1.0
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_summary_reports_accuracy_refusals_and_latency() -> None:
    results = [
        result("glossary", True),
        result("glossary", False),
        result("out_of_scope", True, expected="refused", status="out_of_scope"),
        result("report_fact", False, status="not_found"),
    ]
    summary = summarize(results)
    assert summary["overall"]["passed"] == 2
    assert summary["overall"]["total"] == 4
    assert summary["by_category"]["glossary"]["rate"] == pytest.approx(0.5)
    assert summary["refusals"]["false_refusal_rate"] == pytest.approx(1 / 3)
    assert summary["refusals"]["recall"] == pytest.approx(1.0)
    assert summary["latency_ms"]["max"] == 3000
    markdown = to_markdown(summary)
    assert "| glossary | 1/2 | 50.0%" in markdown
    assert "False refusal rate" in markdown
