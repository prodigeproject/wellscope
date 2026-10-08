"""Deterministic scoring: status, required facts (notation-insensitive) and cited documents."""

from __future__ import annotations

import re
from dataclasses import dataclass

from wellscope.domain.dates import date_matches
from wellscope.domain.numbers import extract_numbers, number_candidates
from wellscope.evals.golden import GoldenItem
from wellscope.qa.service import Answer

REFUSALS = frozenset({"not_found", "out_of_scope"})
ACCEPTED_STATUSES = {
    "answered": frozenset({"answered"}),
    "not_found": frozenset({"not_found"}),
    "out_of_scope": frozenset({"out_of_scope"}),
    "refused": REFUSALS,
    "grounded": frozenset({"answered", "not_found"}),
}
EXACT_DIGITS = 6
_NUMERIC = re.compile(r"[-+]?\d[\d.,]*%?")
_DASHES = str.maketrans({"–": "-", "—": "-", "’": "'", "‘": "'", "“": '"', "”": '"'})
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class ItemResult:
    """Outcome of one golden question; holds no answer text, so reports are safe to share."""

    id: str
    category: str
    lang: str
    expected_status: str
    status: str
    verified: bool
    passed: bool
    status_ok: bool
    content_ok: bool
    citations_ok: bool
    missing: tuple[str, ...]
    latency_ms: int
    input_tokens: int
    output_tokens: int


def score(item: GoldenItem, answer: Answer) -> ItemResult:
    """Compare an answer with the item's expectation."""
    expect = item.expect
    status_ok = answer.status in ACCEPTED_STATUSES[expect.status]
    shown = "\n".join((answer.markdown, *answer.caveats))  # the interface shows both
    missing = [token for token in expect.must_include if not contains(shown, token)]
    missing += [
        "one of " + " | ".join(group)
        for group in expect.must_include_any
        if not any(contains(shown, token) for token in group)
    ]
    cited = {citation.doc_id for citation in answer.citations}
    citations_ok = all(doc_id in cited for doc_id in expect.must_cite_docs)
    return ItemResult(
        id=item.id,
        category=item.category,
        lang=item.lang.value,
        expected_status=expect.status,
        status=answer.status,
        verified=answer.verified,
        passed=status_ok and not missing and citations_ok,
        status_ok=status_ok,
        content_ok=not missing,
        citations_ok=citations_ok,
        missing=tuple(missing),
        latency_ms=answer.latency_ms,
        input_tokens=sum(usage.input_tokens for usage in answer.usage),
        output_tokens=sum(usage.output_tokens for usage in answer.usage),
    )


def contains(text: str, expected: str) -> bool:
    """Whether ``text`` states ``expected``: dates and numbers in any notation, text loosely."""
    dates = date_matches(expected)
    if dates and dates[0].text == expected.strip():
        return dates[0].value in {match.value for match in date_matches(text)}
    if _NUMERIC.fullmatch(expected.strip()):
        wanted = {round(value, EXACT_DIGITS) for value in number_candidates(expected.strip("%"))}
        found = {round(value, EXACT_DIGITS) for value in extract_numbers(text)}
        return bool(wanted & found)
    return _normalised(expected) in _normalised(text)


def _normalised(text: str) -> str:
    return _SPACES.sub(" ", text.translate(_DASHES).casefold()).strip()
