"""Deterministic answer checks: cited sources exist, and every figure comes from them.

Evidence is the text, label and period of the cited sources only; the question is not evidence,
so a false premise cannot verify itself. Times (``17:00``) and dates (``19/07/2026`` =
``19 Juli 2026``) must appear in that evidence. Other numbers must appear there too, except:

- plain counts up to 10 (``3 attempts``, ``run #2``) and codes such as ``D18``;
- the ``100`` of a shown percentage calculation (``40.00 / 50.00 x 100``);
- a value calculated from figures in the same or the previous sentence: a sum or difference of
  two of them, the total of the figures listed before it, or a percentage of one by another.

Numbers match under English and Indonesian separators alike.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import permutations

from wellscope.domain.dates import date_matches
from wellscope.domain.numbers import extract_numbers, number_candidates
from wellscope.qa.answerer import Draft
from wellscope.retrieval.models import Source

SMALL_COUNT = 10
PERCENT = 100.0
EXACT_DIGITS = 6
SUM_TOLERANCE = 0.006
PERCENT_TOLERANCE = 0.051
WHOLE_PERCENT_TOLERANCE = 0.5
MIDNIGHT = ("24:00", "00:00")
_CITATION = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*\]")
_CODE = re.compile(r"\b[A-Za-z]+\d[\w-]*")
_TIME = re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2})(?![\d:])")
_NUMBER = re.compile(r"[-+]?\d[\d.,]*")
_SMALL_INTEGER = re.compile(r"\d{1,2}")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?;])\s+|\n+")
_PERCENT_SIGN = re.compile(r"\s*(?:%|percent\b|persen\b)", re.IGNORECASE)
_TIMES_SIGN = re.compile(r"[x\N{MULTIPLICATION SIGN}*]\s*$")


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


@dataclass(slots=True)
class _Facts:
    numbers: set[float] = field(default_factory=set)
    times: set[str] = field(default_factory=set)
    dates: set[dt.date] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class _Figure:
    token: str
    values: frozenset[float]
    percent: bool
    supported: bool


def cited_ids(draft: Draft) -> list[str]:
    """Source ids cited in the list or inline in the text, first mention first."""
    inline = [
        part.strip()
        for match in _CITATION.finditer(draft.markdown)
        for part in re.split(r"[,;]", match.group(1))
    ]
    return list(dict.fromkeys([*draft.citations, *inline]))


def verify(draft: Draft, sources: Sequence[Source]) -> Verification:
    """Check an answered draft against the sources it cites."""
    if draft.status != "answered":
        return Verification()
    by_id = {source.id: source for source in sources}
    cited = cited_ids(draft)
    known = [by_id[source_id] for source_id in cited if source_id in by_id]
    evidence = _facts(
        text for source in known for text in (source.label, source.period, source.text)
    )
    return Verification(
        unknown_citations=tuple(source_id for source_id in cited if source_id not in by_id),
        missing_citation=not known,
        unsupported_numbers=_unsupported(draft.markdown, evidence),
    )


def _facts(texts: Iterable[str]) -> _Facts:
    facts = _Facts()
    for text in texts:
        remainder, times, dates = _split(text)
        facts.numbers.update(_rounded(extract_numbers(remainder)))
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


def _unsupported(text: str, evidence: _Facts) -> tuple[str, ...]:
    remainder, times, dates = _split(text)
    problems = [spelled for spelled, time in times if time not in evidence.times]
    problems += [spelled for spelled, date in dates if date not in evidence.dates]
    previous: list[float] = []
    for sentence in _SENTENCE_BREAK.split(remainder):
        figures = _figures(sentence, evidence.numbers)
        operands = previous + [
            value for figure in figures if figure.supported for value in figure.values
        ]
        listed: list[float] = []
        for figure in figures:
            if not figure.supported and not _calculated(figure, operands, listed):
                problems.append(figure.token)
            listed.append(min(figure.values))
        previous = [value for figure in figures if figure.supported for value in figure.values]
    return tuple(problems)


def _figures(sentence: str, known: set[float]) -> list[_Figure]:
    """Numbers of a sentence; a figure is supported when the evidence or a rule allows it."""
    figures = []
    for match in _NUMBER.finditer(sentence):
        token = match.group().rstrip(".,")
        candidates = number_candidates(token)
        if not candidates:
            continue
        values = frozenset(abs(value) for value in candidates)
        matched = frozenset(value for value in values if round(value, EXACT_DIGITS) in known)
        count = _SMALL_INTEGER.fullmatch(token) is not None and int(token) <= SMALL_COUNT
        factor = PERCENT in values and _TIMES_SIGN.search(sentence[: match.start()]) is not None
        percent = _PERCENT_SIGN.match(sentence, match.end()) is not None
        figures.append(_Figure(token, matched or values, percent, bool(matched) or count or factor))
    return figures


def _calculated(figure: _Figure, operands: Sequence[float], listed: Sequence[float]) -> bool:
    """A total of the values listed before it, or a sum, difference or percentage of two."""
    if len(listed) > 1 and any(
        _close(value, sum(listed), SUM_TOLERANCE) for value in figure.values
    ):
        return True
    for first, second in permutations(dict.fromkeys(operands), 2):
        if figure.percent and second:
            tolerance = (
                PERCENT_TOLERANCE
                if "." in figure.token or "," in figure.token
                else WHOLE_PERCENT_TOLERANCE
            )
            if any(_close(value, first / second * PERCENT, tolerance) for value in figure.values):
                return True
        elif any(
            _close(value, first + second, SUM_TOLERANCE)
            or _close(value, first - second, SUM_TOLERANCE)
            for value in figure.values
        ):
            return True
    return False


def _close(value: float, target: float, tolerance: float) -> bool:
    return math.isclose(value, target, rel_tol=1e-9, abs_tol=tolerance)


def _rounded(values: Iterable[float]) -> set[float]:
    return {round(abs(value), EXACT_DIGITS) for value in values}
