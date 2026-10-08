from __future__ import annotations

import pytest

from wellscope.llm.pricing import estimate_cost


def test_cost_uses_list_prices_per_million_tokens() -> None:
    assert estimate_cost("gpt-5.4-mini", 1_000_000, 100_000) == pytest.approx(0.75 + 0.45)


def test_dated_model_names_match_their_family() -> None:
    assert estimate_cost("gpt-5.4-nano-2026-03-17", 10_000, 0) == pytest.approx(0.002)


def test_unknown_models_have_no_estimate() -> None:
    assert estimate_cost("fake-chat", 1000, 10) is None
