"""Deterministic answer checks: cited sources exist, and every number comes from them.

A number passes when it appears in a cited source or in the question, is a small count (at most
10), or is the sum, difference or ratio of two numbers that pass. Codes such as ``D18`` and
citation ids are ignored. Numbers match under English and Indonesian separators alike.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import permutations

from wellscope.domain.numbers import extract_numbers, number_tokens
from wellscope.qa.answerer import Draft
from wellscope.retrieval.models import Source

SMALL_COUNT = 10
PERCENT = 100
EXACT_DIGITS = 6
DERIVED_REL_TOLERANCE = 0.005
DERIVED_ABS_TOLERANCE = 0.05
_CITATION = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*\]")
_CODE = re.compile(r"\b[A-Za-z]+\d[\w-]*")


@dataclass(frozen=True, slots=True)
class Verification:
    """Problems found in a draft; an empty result means it passed."""

    unknown_citations: tuple[str, ...] = ()
    missing_citation: bool = False
    unsupported_numbers: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether the draft passed every check."""
        return not (self.unknown_citations or self.missing_citation or self.unsupported_numbers)

    def feedback(self) -> str:
        """The problems, phrased for the model that has to fix them."""
        problems = []
        if self.unknown_citations:
            problems.append(f"citations {', '.join(self.unknown_citations)} are not sources")
        if self.missing_citation:
            problems.append("the answer cites no source")
        if self.unsupported_numbers:
            numbers = ", ".join(self.unsupported_numbers)
            problems.append(f"these numbers are not in the cited sources: {numbers}")
        return "; ".join(problems) + "."


def cited_ids(draft: Draft) -> list[str]:
    """Source ids cited in the list or inline in the text, first mention first."""
    inline = [
        part.strip()
        for match in _CITATION.finditer(draft.markdown)
        for part in re.split(r"[,;]", match.group(1))
    ]
    return list(dict.fromkeys([*draft.citations, *inline]))


def verify(draft: Draft, sources: Sequence[Source], question: str) -> Verification:
    """Check an answered draft against the sources it cites."""
    if draft.status != "answered":
        return Verification()
    by_id = {source.id: source for source in sources}
    cited = cited_ids(draft)
    known = [by_id[source_id] for source_id in cited if source_id in by_id]
    allowed = _values(question) | {value for source in known for value in _values(source.text)}
    return Verification(
        unknown_citations=tuple(source_id for source_id in cited if source_id not in by_id),
        missing_citation=not known,
        unsupported_numbers=_unsupported(draft.markdown, allowed),
    )


def _unsupported(text: str, allowed: set[float]) -> tuple[str, ...]:
    exact = {round(value, EXACT_DIGITS) for value in allowed}
    supported: list[float] = []
    pending: list[tuple[str, set[float]]] = []
    for token, candidates in number_tokens(_without_codes(text)):
        values = {abs(value) for value in candidates}
        matched = [value for value in values if round(value, EXACT_DIGITS) in exact]
        if matched or min(values) <= SMALL_COUNT:
            supported.extend(matched or [min(values)])
        else:
            pending.append((token, values))
    derived = _derived(supported)
    return tuple(
        token for token, values in pending if not any(_near(value, derived) for value in values)
    )


def _derived(values: Sequence[float]) -> list[float]:
    """Sums, differences and ratios (also as percentages) of supported numbers, and their total."""
    results = [sum(values)]
    for first, second in permutations(set(values), 2):
        results += [first + second, first - second]
        if second:
            results += [first / second, first / second * PERCENT]
    return results


def _near(value: float, candidates: Iterable[float]) -> bool:
    return any(
        math.isclose(value, candidate, rel_tol=DERIVED_REL_TOLERANCE, abs_tol=DERIVED_ABS_TOLERANCE)
        for candidate in candidates
    )


def _values(text: str) -> set[float]:
    return {abs(value) for value in extract_numbers(_without_codes(text))}


def _without_codes(text: str) -> str:
    return _CODE.sub(" ", _CITATION.sub(" ", text))
