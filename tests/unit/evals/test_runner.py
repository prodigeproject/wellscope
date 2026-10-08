from __future__ import annotations

from typing import Any

from wellscope.domain.messages import Language
from wellscope.evals.golden import Expectation, GoldenItem
from wellscope.evals.runner import run_eval
from wellscope.qa.service import Answer


class FlakyService:
    def ask(self, question: str, history: Any) -> Answer:
        if question == "boom":
            raise RuntimeError("unexpected")
        return Answer(status="answered", language=Language.EN, markdown="ok", html="ok")


def item(question: str) -> GoldenItem:
    expectation = Expectation(status="answered")
    return GoldenItem(
        id=question, lang=Language.EN, category="c", question=question, expect=expectation
    )


def test_an_exception_on_one_item_does_not_abort_the_run() -> None:
    runs = run_eval(FlakyService(), [item("fine"), item("boom")], workers=2)  # type: ignore[arg-type]
    statuses = {run[0].id: run[1].status for run in runs}
    assert statuses == {"fine": "answered", "boom": "error"}
    assert runs[1][1].reason == "exception:RuntimeError"
