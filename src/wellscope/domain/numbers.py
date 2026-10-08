"""Number parsing shared by ingestion (English reports) and answer verification (EN/ID prose)."""

from __future__ import annotations

import re

_ENGLISH = re.compile(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_INDONESIAN = re.compile(r"[-+]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?")
_TOKEN = re.compile(r"[-+]?\d[\d.,]*")
_TRAILING_PUNCTUATION = ".,"
_PERCENT = "%"


def parse_number(text: str) -> float | None:
    """Parse an English-formatted number such as ``1,200.00`` or ``26.82%``."""
    token = text.strip().removesuffix(_PERCENT).strip()
    if not _ENGLISH.fullmatch(token):
        return None
    return float(token.replace(",", ""))


def number_candidates(token: str) -> set[float]:
    """Every plausible value of ``token`` under English and Indonesian separators.

    ``1.200`` is ambiguous (1.2 in English, 1200 in Indonesian) and yields both readings, so
    a verifier can accept a number when any reading matches the source.
    """
    token = token.strip().rstrip(_TRAILING_PUNCTUATION)
    values: set[float] = set()
    if _ENGLISH.fullmatch(token):
        values.add(float(token.replace(",", "")))
    if _INDONESIAN.fullmatch(token):
        values.add(float(token.replace(".", "").replace(",", ".")))
    return values


def number_tokens(text: str) -> list[tuple[str, set[float]]]:
    """Numeric tokens in ``text`` with their candidate values, in reading order."""
    tokens = []
    for match in _TOKEN.finditer(text):
        candidates = number_candidates(match.group())
        if candidates:
            tokens.append((match.group().rstrip(_TRAILING_PUNCTUATION), candidates))
    return tokens


def extract_numbers(text: str) -> set[float]:
    """All values mentioned in ``text`` under either separator convention."""
    values: set[float] = set()
    for _, candidates in number_tokens(text):
        values |= candidates
    return values
