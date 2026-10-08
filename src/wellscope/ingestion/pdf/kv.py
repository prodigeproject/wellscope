"""Known-label key-value extraction for form blocks written as ``Label : value``.

Values may follow the label on the same line, sit on the next line (label above value) or wrap
over several lines. Only labels declared in a form template are recognised, so words inside a
value are never mistaken for labels.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True, slots=True)
class LabelSpec:
    """A canonical key and the label spellings that introduce its value."""

    key: str
    labels: tuple[str, ...]


def extract_pairs(lines: Iterable[str], specs: Sequence[LabelSpec]) -> dict[str, str]:
    """Map each recognised label's key to its value text.

    A label must start at a word boundary and be followed by a colon. A repeated label (for
    example a page header printed on every page) keeps its first value.
    """
    pattern, keys = _compile(tuple(specs))
    values: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        matches = list(pattern.finditer(line))
        prefix = line[: matches[0].start()] if matches else line
        if current is not None and prefix.strip():
            values[current].append(prefix.strip())
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            key = keys[_normalise(match["label"])]
            if key in values:
                current = None
                continue
            values[key] = [line[match.end() : end].strip()]
            current = key
    return {key: " ".join(part for part in parts if part) for key, parts in values.items()}


@lru_cache(maxsize=64)
def _compile(specs: tuple[LabelSpec, ...]) -> tuple[re.Pattern[str], dict[str, str]]:
    keys = {_normalise(label): spec.key for spec in specs for label in spec.labels}
    aliases = sorted(keys, key=len, reverse=True)
    alternation = "|".join(re.escape(alias).replace(r"\ ", r"\s+") for alias in aliases)
    pattern = re.compile(rf"(?<![A-Za-z0-9])(?P<label>{alternation})\s*:", re.IGNORECASE)
    return pattern, keys


def _normalise(label: str) -> str:
    return " ".join(label.split()).lower()
