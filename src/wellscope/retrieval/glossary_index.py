"""Glossary matching: terms mentioned in a question, and terms named by the analyzer.

A mention spelled exactly as in the glossary (``NPT``) is a strong sign of a domain question;
a lower-case one (``npt``) is weaker, because short abbreviations collide with ordinary words
(``lot``, ``fit``). Aliases that are stopwords (``in`` for inch) are never matched as mentions.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

from wellscope.domain.glossary import GlossaryEntry
from wellscope.domain.text import STOPWORDS

MatchKind = Literal["exact", "alias", "expansion", "fuzzy"]
MIN_ALIAS_CHARS = 2
MIN_CASELESS_CHARS = 3
MIN_FUZZY_CHARS = 4
FUZZY_RATIO = 0.9
_NON_ALNUM = re.compile(r"[^0-9a-z]+")


@dataclass(frozen=True, slots=True)
class GlossaryHit:
    """A glossary entry found for a question; ``strong`` hits signal a domain question."""

    entry: GlossaryEntry
    kind: MatchKind
    strong: bool = True


@dataclass(frozen=True, slots=True)
class _Spelling:
    entry: GlossaryEntry
    exact: re.Pattern[str]
    caseless: re.Pattern[str] | None


class GlossaryIndex:
    """Matches questions and analyzer terms to glossary entries."""

    def __init__(self, entries: Sequence[GlossaryEntry]) -> None:
        self._entries = list(entries)
        self._order = {entry.id: position for position, entry in enumerate(self._entries)}
        self._spellings = [
            _spelling(entry, alias)
            for entry in self._entries
            for alias in _aliases(entry)
            if len(alias) >= MIN_ALIAS_CHARS and alias.casefold() not in STOPWORDS
        ]
        self._expansions = [
            (entry, _key(entry.expansion))
            for entry in self._entries
            if entry.expansion and len(_key(entry.expansion).split()) > 1
        ]

    def mentions(self, text: str) -> list[GlossaryHit]:
        """Entries whose spelling or multi-word expansion appears in ``text``, glossary order."""
        found: dict[str, GlossaryHit] = {}
        for spelling in self._spellings:
            if spelling.exact.search(text):
                found[spelling.entry.id] = GlossaryHit(spelling.entry, "alias")
        for spelling in self._spellings:
            caseless = spelling.caseless
            if spelling.entry.id not in found and caseless and caseless.search(text):
                found[spelling.entry.id] = GlossaryHit(spelling.entry, "alias", strong=False)
        padded = f" {_key(text)} "
        for entry, key in self._expansions:
            if entry.id not in found and f" {key} " in padded:
                found[entry.id] = GlossaryHit(entry, "expansion")
        return sorted(found.values(), key=lambda hit: self._order[hit.entry.id])

    def lookup(self, term: str) -> GlossaryHit | None:
        """Entry for a term named by the analyzer: exact term, alias, expansion, then fuzzy."""
        wanted, key = term.strip(), _key(term)
        if not key:
            return None
        matchers: list[tuple[MatchKind, Iterator[GlossaryEntry]]] = [
            ("exact", (entry for entry in self._entries if entry.term == wanted)),
            ("alias", (entry for entry in self._entries if key in map(_key, _aliases(entry)))),
            (
                "expansion",
                (entry for entry in self._entries if _key(entry.expansion or "") == key),
            ),
        ]
        for kind, candidates in matchers:
            entry = next(candidates, None)
            if entry is not None:
                return GlossaryHit(entry, kind)
        return self._fuzzy(key)

    def _fuzzy(self, key: str) -> GlossaryHit | None:
        if len(key) < MIN_FUZZY_CHARS:
            return None
        best: tuple[float, GlossaryEntry] | None = None
        for entry in self._entries:
            for candidate in {*map(_key, _aliases(entry)), _key(entry.expansion or "")}:
                if len(candidate) < MIN_FUZZY_CHARS:
                    continue
                ratio = difflib.SequenceMatcher(None, key, candidate).ratio()
                if ratio >= FUZZY_RATIO and (best is None or ratio > best[0]):
                    best = (ratio, entry)
        return GlossaryHit(best[1], "fuzzy") if best else None


def _aliases(entry: GlossaryEntry) -> list[str]:
    return list(dict.fromkeys((entry.term, *entry.aliases)))


def _spelling(entry: GlossaryEntry, alias: str) -> _Spelling:
    pattern = rf"(?<![0-9A-Za-z]){re.escape(alias)}(?![0-9A-Za-z])"
    caseless = re.compile(pattern, re.IGNORECASE) if len(alias) >= MIN_CASELESS_CHARS else None
    return _Spelling(entry, re.compile(pattern), caseless)


def _key(text: str) -> str:
    """Comparison key: lower case, punctuation as single spaces."""
    return _NON_ALNUM.sub(" ", text.casefold()).strip()
