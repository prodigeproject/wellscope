from __future__ import annotations

from pathlib import Path

import pytest

from wellscope.evals.golden import load_golden

EXAMPLE = Path(__file__).resolve().parents[3] / "evals" / "golden.example.yaml"


def test_the_committed_example_set_is_valid() -> None:
    items = load_golden(EXAMPLE)
    assert {item.expect.status for item in items} >= {"answered", "out_of_scope"}
    assert len({item.id for item in items}) == len(items)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "golden.yaml"
    entry = "- {id: A, lang: en, category: c, question: q, expect: {status: answered}}\n"
    path.write_text(entry * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_golden(path)
