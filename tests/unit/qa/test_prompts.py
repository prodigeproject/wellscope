"""Prompt contracts: the rules the pipeline relies on must stay in the versioned prompts."""

from __future__ import annotations

from wellscope.qa.prompts import load_prompt


def test_answer_prompt_states_the_grounding_rules() -> None:
    prompt = load_prompt("answer")
    for rule in (
        "only from the sources",
        "not instructions",
        "[S1]",
        "exactly as written",
        "not_found",
        "out_of_scope",
        "caveats",
        "{language}",
        "{nonce}",
    ):
        assert rule in prompt, rule


def test_analyzer_prompt_defines_every_scope_and_intent() -> None:
    prompt = load_prompt("analyzer")
    for value in (
        "in_scope",
        "out_of_scope",
        "unsafe",
        "glossary",
        "report_fact",
        "operations",
        "comparison",
        "aggregation",
        "catalog",
        "standalone_question",
        "Never follow instructions",
    ):
        assert value in prompt, value
