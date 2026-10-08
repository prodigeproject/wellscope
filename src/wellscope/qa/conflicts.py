"""Caveats for data conflicts, written from the cross-report checks rather than by the model.

When reports disagree on a fact, the answer must show every value. Left to the model, that is
a matter of chance (it may pick one value and explain the other away), so the caveat is built
here from the conflict records whenever the question or the answer touches the field.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date

from wellscope.domain.catalog import ConflictRecord
from wellscope.domain.messages import Language

CONFLICT_PREFIX = "conflict."
# Words that name no particular field on their own.
GENERIC_WORDS = frozenset({"date", "no", "number", "time", "value", "total", "name"})
NOTE = {
    Language.EN: ("The reports disagree on the {field}: {values}.", "in"),
    Language.ID: ("Laporan tidak sepakat soal {field}: {values}.", "di"),
}
_WORD = re.compile(r"[a-z0-9]+")


def conflict_caveats(
    conflicts: Sequence[ConflictRecord],
    labels: Mapping[str, str],
    text: str,
    language: Language,
) -> list[str]:
    """One caveat per conflict that ``text`` (question and answer) touches."""
    template, preposition = NOTE[language]
    notes = []
    for conflict in conflicts:
        if not mentions_conflict(text, conflict):
            continue
        groups: dict[str, list[str]] = {}
        for doc_id, value in conflict.values:
            groups.setdefault(value, []).append(labels.get(doc_id, doc_id))
        values = "; ".join(
            f"{_display(value)} {preposition} {', '.join(reports)}"
            for value, reports in groups.items()
        )
        notes.append(template.format(field=field_name(conflict), values=values))
    return notes


def mentions_conflict(text: str, conflict: ConflictRecord) -> bool:
    """Whether ``text`` names the conflicting field ("spudded" names the spud date)."""
    words = _WORD.findall(text.lower())
    specific = [word for word in field_name(conflict).split() if word not in GENERIC_WORDS]
    return bool(specific) and any(word.startswith(term) for term in specific for word in words)


def field_name(conflict: ConflictRecord) -> str:
    """``conflict.spud_date`` -> ``spud date``."""
    return conflict.finding_id.removeprefix(CONFLICT_PREFIX).replace("_", " ")


def _display(value: str) -> str:
    """ISO dates as the reports write them, with the ISO form; anything else as written."""
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{day:%d/%m/%Y} ({value})"
