"""Aggregate evaluation metrics, with Wilson 95% intervals; no answer text is included."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from typing import Any

from wellscope.evals.scoring import REFUSALS, ItemResult

EXPECT_REFUSAL = frozenset({"not_found", "out_of_scope", "refused"})

Z_95 = 1.96
PERCENT = 100
P95 = 0.95


def wilson_interval(passed: int, total: int) -> tuple[float, float]:
    """95% Wilson score interval of ``passed / total``."""
    if total == 0:
        return 0.0, 0.0
    rate = passed / total
    denominator = 1 + Z_95**2 / total
    centre = (rate + Z_95**2 / (2 * total)) / denominator
    spread = Z_95 * math.sqrt(rate * (1 - rate) / total + Z_95**2 / (4 * total**2)) / denominator
    return max(0.0, centre - spread), min(1.0, centre + spread)


def proportion(passed: int, total: int) -> dict[str, Any]:
    """A rate with its interval."""
    low, high = wilson_interval(passed, total)
    rate = passed / total if total else 0.0
    return {"passed": passed, "total": total, "rate": rate, "ci95": [low, high]}


def summarize(results: Sequence[ItemResult]) -> dict[str, Any]:
    """Accuracy overall and per category, refusal behaviour, verification, latency and tokens."""
    categories = sorted({result.category for result in results})
    expect_answer = [result for result in results if result.expected_status == "answered"]
    expect_refusal = [result for result in results if result.expected_status in EXPECT_REFUSAL]
    refused = [result for result in results if result.status in REFUSALS]
    answered = [result for result in results if result.status == "answered"]
    latencies = sorted(result.latency_ms for result in results) or [0]
    return {
        "overall": proportion(sum(r.passed for r in results), len(results)),
        "by_category": {
            category: proportion(
                sum(r.passed for r in results if r.category == category),
                sum(r.category == category for r in results),
            )
            for category in categories
        },
        "refusals": {
            "recall": _rate(sum(r.status in REFUSALS for r in expect_refusal), len(expect_refusal)),
            "precision": _rate(sum(r.status_ok for r in refused), len(refused)),
            "false_refusal_rate": _rate(
                sum(r.status in REFUSALS for r in expect_answer), len(expect_answer)
            ),
        },
        "verified_rate": _rate(sum(r.verified for r in answered), len(answered)),
        "latency_ms": {
            "p50": statistics.median(latencies),
            "p95": latencies[min(len(latencies) - 1, math.ceil(P95 * len(latencies)) - 1)],
            "max": latencies[-1],
        },
        "tokens_mean": {
            "input": statistics.fmean(r.input_tokens for r in results) if results else 0,
            "output": statistics.fmean(r.output_tokens for r in results) if results else 0,
        },
        "failures": [
            {"id": r.id, "status": r.status, "missing": list(r.missing)}
            for r in results
            if not r.passed
        ],
    }


def to_markdown(summary: dict[str, Any]) -> str:
    """The summary as a Markdown report."""
    overall = summary["overall"]
    refusals = summary["refusals"]
    latency = summary["latency_ms"]
    lines = [
        "# Evaluation report",
        "",
        f"**Accuracy: {_cell(overall)}**",
        "",
        "| Category | Passed | Rate | 95% CI |",
        "|---|---|---|---|",
    ]
    lines += [f"| {name} | {_cell(value)} |" for name, value in summary["by_category"].items()]
    lines += [
        "",
        f"- Refusal recall: {refusals['recall']:.1%}",
        f"- Refusal precision: {refusals['precision']:.1%}",
        f"- False refusal rate: {refusals['false_refusal_rate']:.1%}",
        f"- Answers with verified citations and figures: {summary['verified_rate']:.1%}",
        f"- Latency p50 / p95 / max: {latency['p50'] / 1000:.1f} s / "
        f"{latency['p95'] / 1000:.1f} s / {latency['max'] / 1000:.1f} s",
        f"- Mean tokens per question: {summary['tokens_mean']['input']:.0f} in, "
        f"{summary['tokens_mean']['output']:.0f} out",
    ]
    if summary["failures"]:
        lines += ["", "Failed items: " + ", ".join(item["id"] for item in summary["failures"])]
    return "\n".join(lines) + "\n"


def _cell(value: dict[str, Any]) -> str:
    low, high = value["ci95"]
    rate = value["rate"] * PERCENT
    return f"{value['passed']}/{value['total']} | {rate:.1f}% | {low:.0%}–{high:.0%}"


def _rate(part: int, whole: int) -> float:
    return part / whole if whole else 0.0
