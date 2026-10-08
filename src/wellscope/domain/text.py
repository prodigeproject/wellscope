"""Text normalisation for the keyword index, applied identically to documents and questions."""

from __future__ import annotations

import re

_FRACTIONS = {"½": "1/2", "¼": "1/4", "¾": "3/4", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
_QUOTES = str.maketrans({"”": '"', "“": '"', "’": "'", "‘": "'"})
_GLUED_DEPTH_UNIT = re.compile(r"\bm(?=(?:MDDF|TVDDF|TVDSS)\b)")
_TRAILING = re.compile(r"(?<=[A-Za-z0-9])[.,;:)\]]+(?=\s|$)")
_LEADING = re.compile(r"(?<!\S)[(\[]+(?=[A-Za-z0-9])")
_TERM = re.compile(r"[a-z0-9][a-z0-9.\-/]*")
MAX_TERMS = 32

STOPWORDS = frozenset(
    """
    a an the of in on at to for from by with and or is are was were be been being what which
    who whom when where why how did do does done has have had this that these those it its as
    about into there their any all me my tell show give please can could would should will
    much many per vs than then also
    apa apakah berapa berapakah siapa kapan dimana mana di ke dari pada yang dan atau untuk
    dengan adalah ialah itu ini tersebut saja juga sudah telah akan bisa dapat tolong mohon
    jelaskan sebutkan bagaimana mengapa kenapa tentang dalam oleh sebagai para tanggal jam
    pukul berapa nya kah
    """.split()  # noqa: SIM905 - a long word list reads better as text
)


def normalize_for_index(text: str) -> str:
    """Make sizes, units and codes tokenise the same way in documents and in questions."""
    text = text.translate(_QUOTES)
    for symbol, fraction in _FRACTIONS.items():
        text = re.sub(rf"(?<=\d){symbol}", f"-{fraction}", text)
        text = text.replace(symbol, fraction)
    text = _GLUED_DEPTH_UNIT.sub("m ", text)
    text = _TRAILING.sub("", text)
    return _LEADING.sub("", text)


def search_terms(text: str) -> list[str]:
    """Distinct lower-case keywords of ``text`` without English or Indonesian stopwords."""
    terms: list[str] = []
    for raw in _TERM.findall(normalize_for_index(text).casefold()):
        term = raw.rstrip(".-/")
        if term in STOPWORDS or term in terms or not (term.isdigit() or len(term) > 1):
            continue
        terms.append(term)
    return terms[:MAX_TERMS]
