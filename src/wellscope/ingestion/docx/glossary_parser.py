"""Glossary extraction from Word tables whose header ends with a ``Meaning`` column.

Rows read ``Term | Expansion – Description``. Letter rows (``A``, ``B`` …) only separate
sections; ``(to be confirmed)`` and ``Unknown –`` mark how certain a definition is.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from docx import Document

from wellscope.domain.glossary import GlossaryCategory, GlossaryEntry, GlossaryStatus

Table = list[list[str]]

MEANING_HEADER = "meaning"
PART_HEADER = "part"
TO_BE_CONFIRMED_MARKER = "(to be confirmed)"
UNKNOWN_EXPANSION = "unknown"
TERM_AND_MEANING = 2
_DASH = re.compile(r"\s+[–—-]\s+")
_SPACED_SLASH = re.compile(r"\s+/\s+")
_MISSPELLING = re.compile(r"\bwritten\s+'([^']+)'", re.IGNORECASE)
_TBC = re.compile(re.escape(TO_BE_CONFIRMED_MARKER), re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def read_tables(path: Path) -> list[Table]:
    """Cell texts of every table in a ``.docx`` file, row by row."""
    document = Document(str(path))
    return [
        [[cell.text.strip() for cell in row.cells] for row in table.rows]
        for table in document.tables
    ]


def is_glossary(tables: Sequence[Table]) -> bool:
    """Whether any table looks like a glossary (its header ends with ``Meaning``)."""
    return any(table and _is_header(table[0]) for table in tables)


def build_entries(tables: Sequence[Table]) -> list[GlossaryEntry]:
    """Turn glossary tables into entries, skipping headers and letter separators."""
    entries: list[GlossaryEntry] = []
    used_ids: set[str] = set()
    for table in tables:
        if not table or not _is_header(table[0]):
            continue
        category: GlossaryCategory = (
            "well_name_part" if table[0][0].strip().lower() == PART_HEADER else "abbreviation"
        )
        for row_number, row in enumerate(table[1:], start=1):
            entry = _entry(row, category, row_number, used_ids)
            if entry is not None:
                entries.append(entry)
                used_ids.add(entry.id)
    return entries


def _is_header(row: Sequence[str]) -> bool:
    return len(row) >= TERM_AND_MEANING and row[-1].strip().lower() == MEANING_HEADER


def _entry(
    row: Sequence[str], category: GlossaryCategory, row_number: int, used_ids: set[str]
) -> GlossaryEntry | None:
    term = row[0].strip() if row else ""
    meaning = row[1].strip() if len(row) > 1 else ""
    if not term or _is_separator(term, meaning):
        return None
    status = GlossaryStatus.CONFIRMED
    if _TBC.search(meaning):
        status = GlossaryStatus.TO_BE_CONFIRMED
        meaning = _TBC.sub("", meaning).strip()
    expansion, description = _split_meaning(meaning, category)
    if expansion is not None and expansion.lower() == UNKNOWN_EXPANSION:
        status, expansion = GlossaryStatus.UNKNOWN, None
    aliases = _aliases(term, description)
    return GlossaryEntry(
        id=_unique_id(term, row_number, used_ids),
        term=term,
        aliases=aliases,
        expansion=expansion,
        description=description,
        status=status,
        senses=_senses(expansion, aliases),
        category=category,
        source_row=row_number,
    )


def _is_separator(term: str, meaning: str) -> bool:
    return len(term) == 1 and term.isalpha() and meaning in ("", term)


def _split_meaning(meaning: str, category: GlossaryCategory) -> tuple[str | None, str | None]:
    parts = _DASH.split(meaning, maxsplit=1)
    if len(parts) == TERM_AND_MEANING:
        return parts[0].strip() or None, parts[1].strip() or None
    if category == "well_name_part":
        return None, meaning or None
    return meaning or None, None


def _aliases(term: str, description: str | None) -> tuple[str, ...]:
    names = [name.strip() for name in _SPACED_SLASH.split(term) if name.strip()]
    if description:
        names.extend(_MISSPELLING.findall(description))
    return tuple(dict.fromkeys(names))


def _senses(expansion: str | None, aliases: tuple[str, ...]) -> tuple[str, ...]:
    """Distinct meanings of a single term, e.g. ``Running Tool / Real Time``."""
    if expansion is None or len(aliases) != 1 or not _SPACED_SLASH.search(expansion):
        return ()
    return tuple(part.strip() for part in _SPACED_SLASH.split(expansion))


def _unique_id(term: str, row_number: int, used_ids: set[str]) -> str:
    slug = _NON_ALNUM.sub("-", term.lower()).strip("-") or "term"
    candidate = f"gl-{slug}"
    return candidate if candidate not in used_ids else f"{candidate}-{row_number}"
