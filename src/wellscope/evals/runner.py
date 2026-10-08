"""Run a golden set through the question-answering service, a few questions at a time."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from wellscope.evals.golden import GoldenItem
from wellscope.evals.report import to_markdown
from wellscope.evals.scoring import ItemResult, score
from wellscope.qa.analyzer import Turn
from wellscope.qa.service import Answer, QAService

logger = logging.getLogger(__name__)


def run_eval(
    service: QAService, items: Sequence[GoldenItem], workers: int
) -> list[tuple[GoldenItem, Answer, ItemResult]]:
    """Answer and score every item, in input order."""

    def answer(item: GoldenItem) -> Answer:
        history = [Turn(turn.question, turn.answer) for turn in item.history]
        try:
            return service.ask(item.question, history)
        except Exception as error:  # one failing item must not abort a paid run
            logger.exception("evaluation item %s failed", item.id)
            reason = f"exception:{type(error).__name__}"
            return Answer(status="error", language=item.lang, markdown="", html="", reason=reason)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        answers = list(pool.map(answer, items))
    return [(item, reply, score(item, reply)) for item, reply in zip(items, answers, strict=True)]


def save_run(
    runs: Sequence[tuple[GoldenItem, Answer, ItemResult]],
    summary: dict[str, Any],
    reports_dir: Path,
    details_dir: Path,
) -> Path:
    """Write the aggregate report (shareable) and the answers (private); returns the report."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    reports_dir.mkdir(parents=True, exist_ok=True)
    details_dir.mkdir(parents=True, exist_ok=True)
    report = reports_dir / f"eval-{stamp}.md"
    report.write_text(to_markdown(summary), encoding="utf-8")
    (reports_dir / f"eval-{stamp}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (details_dir / f"eval-{stamp}.jsonl").open("w", encoding="utf-8") as details:
        for item, answer, result in runs:
            record = {"question": item.question, "answer": asdict(answer), "result": asdict(result)}
            details.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return report
