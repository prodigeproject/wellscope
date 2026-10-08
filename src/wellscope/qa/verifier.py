"""Deterministic answer checks: cited sources exist, and every figure comes from them.

Times (``17:00``) and dates (``19/07/2026`` = ``19 Juli 2026``) must appear in a cited source or
in the question. Other numbers pass when they appear there too, are small counts (at most 10)
or the 100 of a percentage calculation, or are the sum, difference or ratio of two numbers that
pass. Codes such as ``D18`` and citation
ids are ignored, and numbers match under English and Indonesian separators alike.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import permutations

from wellscope.domain.dates import date_matches
from wellscope.domain.numbers import extract_numbers, number_tokens
from wellscope.qa.answerer import Draft
from wellscope.retrieval.models import Source

SMALL_COUNT = 10
PERCENT = 100
EXACT_DIGITS = 6
DERIVED_REL_TOLERANCE = 0.005
DERIVED_ABS_TOLERANCE = 0.05
MIDNIGHT = ("24:00", "00:00")
_CITATION = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*\]")
_CODE = re.compile(r"\b[A-Za-z]+\d[\w-]*")
_TIME = re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2})(?![\d:])")


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
            problems.append(f"these values are not in the cited sources: {numbers}")
        return "; ".join(problems) + "."


@dataclass(frozen=True, slots=True)
class _Facts:
    numbers: set[float]
    times: set[str]
    dates: set[dt.date]


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
    allowed = _facts([question, *(source.text for source in known)])
    return Verification(
        unknown_citations=tuple(source_id for source_id in cited if source_id not in by_id),
        missing_citation=not known,
        unsupported_numbers=_unsupported(draft.markdown, allowed),
    )


def _facts(texts: Iterable[str]) -> _Facts:
    facts = _Facts(set(), set(), set())
    for text in texts:
        remainder, times, dates = _split(text)
        facts.numbers.update(
            round(abs(value), EXACT_DIGITS) for value in extract_numbers(remainder)
        )
        facts.times.update(time for _, time in times)
        facts.dates.update(date for _, date in dates)
    return facts


def _split(text: str) -> tuple[str, list[tuple[str, str]], list[tuple[str, dt.date]]]:
    """Text without citations, dates, times and codes; plus the dates and times it held."""
    text = _CITATION.sub(" ", text)
    matches = date_matches(text)
    for match in reversed(matches):
        text = f"{text[: match.start]} {text[match.end :]}"
    times = [(found.group(), _clock(found)) for found in _TIME.finditer(text)]
    text = _CODE.sub(" ", _TIME.sub(" ", text))
    return text, times, [(match.text, match.value) for match in matches]


def _clock(match: re.Match[str]) -> str:
    clock = f"{int(match.group(1)):02d}:{match.group(2)}"
    return MIDNIGHT[1] if clock == MIDNIGHT[0] else clock


def _unsupported(text: str, allowed: _Facts) -> tuple[str, ...]:
    remainder, times, dates = _split(text)
    problems = [spelled for spelled, time in times if time not in allowed.times]
    problems += [spelled for spelled, date in dates if date not in allowed.dates]
    supported: list[float] = []
    pending: list[tuple[str, set[float]]] = []
    for token, candidates in number_tokens(remainder):
        values = {abs(value) for value in candidates}
        matched = [value for value in values if round(value, EXACT_DIGITS) in allowed.numbers]
        if matched or min(values) <= SMALL_COUNT or PERCENT in values:
            supported.extend(matched or [min(values)])
        else:
            pending.append((token, values))
    derived = _derived(supported)
    problems += [token for token, values in pending if not any(_near(v, derived) for v in values)]
    return tuple(problems)


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
