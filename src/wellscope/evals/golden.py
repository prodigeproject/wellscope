"""Golden question sets: questions with the facts a correct answer must contain.

The real set (``evals/private/golden.yaml``) holds facts from the dataset and is never
committed; ``evals/golden.example.yaml`` documents the format with dummy data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, TypeAdapter

from wellscope.domain.base import StrictModel
from wellscope.domain.messages import Language

ExpectedStatus = Literal["answered", "not_found", "out_of_scope", "refused", "grounded"]


class Expectation(StrictModel):
    """What a correct answer looks like."""

    status: ExpectedStatus = "answered"
    must_include: list[str] = Field(default_factory=list)
    must_include_any: list[list[str]] = Field(default_factory=list)
    must_cite_docs: list[str] = Field(default_factory=list)


class GoldenTurn(StrictModel):
    """An earlier exchange, for follow-up questions."""

    question: str
    answer: str = ""


class GoldenItem(StrictModel):
    """One evaluation question."""

    id: str
    lang: Language
    category: str
    question: str
    history: list[GoldenTurn] = Field(default_factory=list)
    expect: Expectation


_ITEMS = TypeAdapter(list[GoldenItem])


def load_golden(path: Path) -> list[GoldenItem]:
    """Read and validate a golden set; ids must be unique."""
    items = _ITEMS.validate_python(yaml.safe_load(path.read_text(encoding="utf-8")) or [])
    ids = [item.id for item in items]
    duplicates = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate golden ids: {', '.join(duplicates)}")
    return items
