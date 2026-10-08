"""Known-label key-value extraction for form blocks written as ``Label : value``.

Values may follow the label on the same line, sit on the next line (label above value) or wrap
over several lines. Only labels declared in a form template are recognised, so words inside a
value are never mistaken for labels, and text that is not aligned with a value (a centred title,
a neighbouring column) ends the value instead of being appended to it.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache

ALIGN_TOLERANCE = 20.0
SELF_DELIMITED = "#"
_NEVER = re.compile(r"(?!)")


@dataclass(frozen=True, slots=True)
class LabelSpec:
    """A canonical key and the label spellings that introduce its value."""

    key: str
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TextLine:
    """A line of text and the horizontal extent of each word."""

    words: tuple[tuple[str, float, float], ...]

    @classmethod
    def from_text(cls, text: str) -> TextLine:
        """A line without positions; every word counts as aligned."""
        return cls(tuple((word, 0.0, 0.0) for word in text.split()))

    @classmethod
    def from_words(cls, words: Iterable[tuple[str, float] | tuple[str, float, float]]) -> TextLine:
        """A line from ``(text, x0)`` or ``(text, x0, x1)`` tuples."""
        return cls(tuple((word[0], word[1], word[-1]) for word in words))

    @property
    def text(self) -> str:
        """Words joined by single spaces."""
        return " ".join(word for word, _, _ in self.words)

    def x_at(self, offset: int) -> float:
        """Horizontal position of character ``offset`` of :attr:`text`."""
        start = 0
        for word, x0, x1 in self.words:
            end = start + len(word)
            if offset < end:
                inside = max(offset - start, 0)
                return x0 + (x1 - x0) * inside / len(word)
            start = end + 1
        return math.inf


def extract_pairs(
    lines: Iterable[TextLine | str],
    specs: Sequence[LabelSpec],
    headings: Sequence[LabelSpec] = (),
) -> dict[str, str]:
    """Map each recognised label's key to its value text.

    A label must start at a word boundary and be followed by a colon (a label that ends in ``#``,
    such as ``BHA no.#``, needs none); a heading label must fill its whole line. A repeated label
    (for example a page header printed on every page) keeps its first value.
    """
    pattern, keys = _compile(tuple(specs))
    heading_keys = {_normalise(label): spec.key for spec in headings for label in spec.labels}
    values: dict[str, list[str]] = {}
    anchors: dict[str, float] = {}
    current: str | None = None
    for item in lines:
        line = item if isinstance(item, TextLine) else TextLine.from_text(item)
        text = line.text
        heading = heading_keys.get(_normalise(text))
        if heading is not None:
            current = None if heading in values else heading
            values.setdefault(heading, [])
            continue
        matches = list(pattern.finditer(text))
        prefix = text[: matches[0].start()] if matches else text
        if current is not None and prefix.strip():
            accepted = _continue(values[current], anchors, current, prefix.strip(), line.x_at(0))
            current = current if accepted else None
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            key = keys[_normalise(match["label"].rstrip(": "))]
            if key in values:
                current = None
                continue
            raw_value = text[match.end() : end]
            value = raw_value.strip()
            values[key] = [value] if value else []
            if value:
                anchors[key] = line.x_at(match.end() + len(raw_value) - len(raw_value.lstrip()))
            current = key
    return {key: " ".join(parts) for key, parts in values.items()}


def _continue(parts: list[str], anchors: dict[str, float], key: str, text: str, x: float) -> bool:
    """Append a continuation line when it starts at or left of the value's first word."""
    anchor = anchors.get(key)
    if anchor is None:
        anchors[key] = x
    elif x > anchor + ALIGN_TOLERANCE:
        return False
    parts.append(text)
    return True


@lru_cache(maxsize=64)
def _compile(specs: tuple[LabelSpec, ...]) -> tuple[re.Pattern[str], dict[str, str]]:
    keys = {_normalise(label): spec.key for spec in specs for label in spec.labels}
    if not keys:
        return _NEVER, keys
    aliases = sorted(keys, key=len, reverse=True)
    alternation = "|".join(_label_pattern(alias) for alias in aliases)
    pattern = re.compile(rf"(?<![A-Za-z0-9])(?P<label>{alternation})", re.IGNORECASE)
    return pattern, keys


def _label_pattern(alias: str) -> str:
    """A label and its delimiter: a colon, unless the label ends in ``#`` itself."""
    words = re.escape(alias).replace(r"\ ", r"\s+")
    return words if alias.endswith(SELF_DELIMITED) else rf"{words}\s*:"


def _normalise(label: str) -> str:
    return " ".join(label.split()).lower()
