"""Scope policy: deterministic, so refusals are consistent and testable without a model.

The analyzer's verdict decides, except that an "out of scope" verdict is overridden when the
question carries a strong domain signal (the model may be wrong; the answer step can still
refuse). Unsafe questions are always refused.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from wellscope.domain.catalog import CatalogEntry
from wellscope.qa.analyzer import Scope
from wellscope.qa.extractors import References
from wellscope.retrieval.glossary_index import GlossaryHit


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    """Whether to answer, and why."""

    allowed: bool
    reason: str


def decide_scope(scope: Scope, strong_signal: bool) -> ScopeDecision:
    """Apply the policy to the analyzer's verdict."""
    if scope is Scope.UNSAFE:
        return ScopeDecision(allowed=False, reason="unsafe")
    if scope is Scope.OUT_OF_SCOPE:
        if strong_signal:
            return ScopeDecision(allowed=True, reason="domain_signal")
        return ScopeDecision(allowed=False, reason="out_of_scope")
    return ScopeDecision(allowed=True, reason="in_scope")


def has_domain_signal(
    question: str,
    references: References,
    hits: Sequence[GlossaryHit],
    catalog: Sequence[CatalogEntry],
) -> bool:
    """A report reference, an exactly spelled glossary term, or a well or rig name."""
    if references.any or any(hit.strong for hit in hits):
        return True
    text = question.casefold()
    names = {name.casefold() for entry in catalog for name in (entry.well, entry.rig) if name}
    return any(name in text for name in names)
