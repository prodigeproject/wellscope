"""Glossary knowledge-base entries."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

GlossaryCategory = Literal["abbreviation", "well_name_part"]


class GlossaryStatus(StrEnum):
    """How certain the glossary itself is about a definition."""

    CONFIRMED = "confirmed"
    TO_BE_CONFIRMED = "to_be_confirmed"
    UNKNOWN = "unknown"


class GlossaryEntry(BaseModel):
    """One glossary row: a term, every spelling that refers to it, and its meaning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    term: str
    aliases: tuple[str, ...]
    expansion: str | None = None
    description: str | None = None
    status: GlossaryStatus = GlossaryStatus.CONFIRMED
    senses: tuple[str, ...] = ()
    category: GlossaryCategory = "abbreviation"
    source_row: int
