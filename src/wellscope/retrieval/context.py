"""Numbered sources within a token budget, and the delimited format the model reads them in.

Source text is HTML-escaped and every tag carries a per-request nonce, so text inside a
report can neither close its own source tag nor forge a new one (prompt-injection defence).
"""

from __future__ import annotations

import html
import math
from collections.abc import Sequence

from wellscope.retrieval.models import Evidence, Source

CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    """Conservative token estimate; reports are dense in numbers and codes."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


class SourceBuilder:
    """Collects sources S1, S2, ... until the token budget is spent; skips duplicate texts."""

    def __init__(self, budget_tokens: int) -> None:
        self._remaining = budget_tokens
        self._sources: list[Source] = []
        self._texts: set[str] = set()

    @property
    def sources(self) -> tuple[Source, ...]:
        """Sources added so far."""
        return tuple(self._sources)

    @property
    def remaining(self) -> int:
        """Tokens left in the budget."""
        return self._remaining

    def add(self, evidence: Evidence) -> bool:
        """Number and add ``evidence``; ``False`` when it does not fit the remaining budget."""
        if evidence.text in self._texts:
            return True
        cost = estimate_tokens(evidence.text)
        if cost > self._remaining:
            return False
        self._remaining -= cost
        self._texts.add(evidence.text)
        self._sources.append(
            Source(
                id=f"S{len(self._sources) + 1}",
                doc_id=evidence.doc_id,
                label=evidence.label,
                section=evidence.section,
                page=evidence.page,
                text=evidence.text,
                period=evidence.period,
            )
        )
        return True


def format_sources(sources: Sequence[Source], nonce: str) -> str:
    """Sources as nonce-delimited tags with escaped text, for the answer prompt."""
    blocks = []
    for source in sources:
        attributes = {
            "id": source.id,
            "doc": source.label,
            "section": source.section,
            "page": "" if source.page is None else str(source.page),
            "period": source.period,
        }
        rendered = " ".join(
            f'{name}="{html.escape(value)}"' for name, value in attributes.items() if value
        )
        text = html.escape(source.text, quote=False)
        blocks.append(f'<source {rendered} nonce="{nonce}">\n{text}\n</source nonce="{nonce}">')
    return "\n\n".join(blocks)
