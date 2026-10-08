"""Question analysis: a small model classifies scope and intent and rewrites follow-ups.

Deterministic extractors supply the report numbers and dates, and take over completely when the
model is unavailable or replies outside the schema, so the pipeline degrades instead of failing.
"""

from __future__ import annotations

import datetime as dt
import html
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from wellscope.domain.catalog import CatalogEntry
from wellscope.domain.messages import Language
from wellscope.errors import ModelError
from wellscope.llm.ports import ChatModel, ChatRequest, ChatResult
from wellscope.qa.extractors import References, detect_language, extract_references
from wellscope.qa.prompts import load_prompt
from wellscope.retrieval.models import DocumentFilter, Intent

logger = logging.getLogger(__name__)
ANALYZER_MAX_TOKENS = 500
HISTORY_ANSWER_CHARS = 400
_GLOSSARY_QUESTION = re.compile(
    r"\b(?:apa\s+itu|apa\s+arti|artinya|kepanjangan|singkatan|definisi|stand\s+for|"
    r"meaning|mean|abbreviation|definition)\b",
    re.IGNORECASE,
)


class Scope(StrEnum):
    """Whether a question may be answered from the documents."""

    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    UNSAFE = "unsafe"


@dataclass(frozen=True, slots=True)
class Turn:
    """An earlier exchange, used to resolve follow-up questions."""

    question: str
    answer: str


@dataclass(frozen=True, slots=True)
class Analysis:
    """What the pipeline needs to know about a question."""

    language: Language
    scope: Scope
    intent: Intent
    standalone_question: str
    glossary_terms: tuple[str, ...]
    filters: DocumentFilter
    search_queries: tuple[str, ...]
    references: References
    result: ChatResult | None


class _Reply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Language
    scope: Scope
    intent: Intent
    standalone_question: str
    glossary_terms: list[str]
    doc_types: list[Literal["DDR", "DGOS"]]
    report_numbers: list[int]
    dates: list[str]
    date_from: str | None
    date_to: str | None
    latest: bool
    search_queries_en: list[str]


_STRINGS = {"type": "array", "items": {"type": "string"}}
_OPTIONAL_DATE = {"type": ["string", "null"]}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": list(_Reply.model_fields),
    "properties": {
        "language": {"type": "string", "enum": [language.value for language in Language]},
        "scope": {"type": "string", "enum": [scope.value for scope in Scope]},
        "intent": {"type": "string", "enum": [intent.value for intent in Intent]},
        "standalone_question": {"type": "string"},
        "glossary_terms": _STRINGS,
        "doc_types": {"type": "array", "items": {"type": "string", "enum": ["DDR", "DGOS"]}},
        "report_numbers": {"type": "array", "items": {"type": "integer"}},
        "dates": _STRINGS,
        "date_from": _OPTIONAL_DATE,
        "date_to": _OPTIONAL_DATE,
        "latest": {"type": "boolean"},
        "search_queries_en": _STRINGS,
    },
}


class Analyzer:
    """Analyses questions with a model when one is configured, otherwise with rules."""

    def __init__(self, model: ChatModel | None) -> None:
        self._model = model
        self._prompt = load_prompt("analyzer")

    def analyze(
        self, question: str, history: Sequence[Turn], catalog: Sequence[CatalogEntry]
    ) -> Analysis:
        """Analyse ``question`` in the context of the conversation and the report catalog."""
        references = extract_references(question, _default_year(catalog))
        if self._model is None:
            return _by_rules(question, references)
        request = ChatRequest(
            system=self._prompt,
            user=_user_message(question, history, catalog),
            schema_name="question_analysis",
            schema=SCHEMA,
            max_output_tokens=ANALYZER_MAX_TOKENS,
        )
        try:
            result = self._model.complete(request)
            reply = _Reply.model_validate(result.content)
        except ModelError as error:
            logger.warning("analyzer failed (%s); using rules", error.code)
            return _by_rules(question, references)
        except ValidationError:
            logger.warning("analyzer reply did not match the schema; using rules")
            return _by_rules(question, references)
        return _merge(question, reply, references, result, follow_up=bool(history))


def _merge(
    question: str, reply: _Reply, references: References, result: ChatResult, *, follow_up: bool
) -> Analysis:
    """Model for scope, intent and rewriting; the question's own numbers and dates win.

    Only a follow-up is rewritten: a question that stands on its own keeps its exact words,
    since a rewrite can change the meaning ("what drill" read as "what drilling").
    """
    rewritten = reply.standalone_question.strip() if follow_up else ""
    filters = DocumentFilter(
        doc_types=references.doc_types or tuple(reply.doc_types),
        report_numbers=references.report_numbers or tuple(reply.report_numbers),
        dates=references.dates or _model_dates(reply),
        date_from=_iso_date(reply.date_from),
        date_to=_iso_date(reply.date_to),
        latest=references.latest or reply.latest,
    )
    return Analysis(
        language=reply.language,
        scope=reply.scope,
        intent=reply.intent,
        standalone_question=rewritten or question,
        glossary_terms=tuple(reply.glossary_terms),
        filters=filters,
        search_queries=tuple(reply.search_queries_en),
        references=references,
        result=result,
    )


def _by_rules(question: str, references: References) -> Analysis:
    """Fallback analysis: scope stays open; the answer step still refuses what it cannot ground."""
    glossary = _GLOSSARY_QUESTION.search(question)
    filters = DocumentFilter(
        doc_types=references.doc_types,
        report_numbers=references.report_numbers,
        dates=references.dates,
        latest=references.latest,
    )
    return Analysis(
        language=detect_language(question),
        scope=Scope.IN_SCOPE,
        intent=Intent.GLOSSARY if glossary else Intent.REPORT_FACT,
        standalone_question=question,
        glossary_terms=(),
        filters=filters,
        search_queries=(),
        references=references,
        result=None,
    )


def _user_message(question: str, history: Sequence[Turn], catalog: Sequence[CatalogEntry]) -> str:
    lines = ["Report catalog:"]
    lines += [
        f"- {_escape(entry.label)}, covers {entry.period or 'an unstated period'}"
        for entry in catalog
    ] or ["- (no reports)"]
    if history:
        lines += ["", "Conversation so far (oldest first):"]
        for turn in history:
            lines.append(f"User: {_escape(turn.question)}")
            lines.append(f"Assistant: {_escape(turn.answer[:HISTORY_ANSWER_CHARS])}")
    lines += ["", "Question to analyse:", f"<question>{_escape(question)}</question>"]
    return "\n".join(lines)


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _default_year(catalog: Sequence[CatalogEntry]) -> int | None:
    """Year assumed for dates written without one: that of the newest report."""
    newest = max((entry.report_date for entry in catalog if entry.report_date), default=None)
    return newest.year if newest else None


def _model_dates(reply: _Reply) -> tuple[dt.date, ...]:
    """Specific days named by the model; a period (date_from/date_to) takes precedence."""
    if reply.date_from or reply.date_to:
        return ()
    return tuple(day for day in map(_iso_date, reply.dates) if day is not None)


def _iso_date(value: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value) if value else None
    except ValueError:
        return None
