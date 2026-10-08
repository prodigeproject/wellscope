"""Versioned prompt templates; a behavioural change gets a new file (``answer.v2.md``)."""

from __future__ import annotations

from importlib.resources import files

PROMPT_VERSIONS = {"analyzer": "v1", "answer": "v1"}


def load_prompt(name: str) -> str:
    """The current version of prompt ``name``."""
    version = PROMPT_VERSIONS[name]
    return (files(__name__) / f"{name}.{version}.md").read_text(encoding="utf-8")
