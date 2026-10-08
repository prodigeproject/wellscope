"""Request and response models of the HTTP API (they also document it in OpenAPI)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator

from wellscope.domain.catalog import CatalogEntry
from wellscope.domain.glossary import GlossaryEntry
from wellscope.qa.service import Answer

MAX_QUESTION_CHARS = 4000
MAX_HISTORY_TURNS = 3
HISTORY_QUESTION_CHARS = 1000
HISTORY_ANSWER_CHARS = 1500
DOC_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{2,79}$"
MAX_GLOSSARY_QUERY = 64


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class HistoryTurn(_Request):
    """An earlier question and the answer shown for it (used to resolve follow-ups)."""

    question: str = Field(min_length=1, max_length=HISTORY_QUESTION_CHARS)
    answer: str = Field(default="", max_length=HISTORY_ANSWER_CHARS)


class ChatBody(_Request):
    """A question, optionally with up to three earlier turns."""

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value


class HealthResponse(BaseModel):
    """Service state; never includes secrets."""

    status: str
    version: str
    index_version: str | None
    documents: int
    glossary_entries: int
    model_configured: bool


class DocumentOut(BaseModel):
    """A report in the catalog."""

    doc_id: str
    doc_type: str
    label: str
    title: str
    well: str | None
    rig: str | None
    report_number: int | None
    report_date: dt.date | None
    period: str
    quality_status: str
    summary: str

    @classmethod
    def of(cls, entry: CatalogEntry) -> DocumentOut:
        """Response view of a catalog entry."""
        return cls(
            doc_id=entry.doc_id,
            doc_type=entry.doc_type,
            label=entry.label,
            title=entry.title,
            well=entry.well,
            rig=entry.rig,
            report_number=entry.report_number,
            report_date=entry.report_date,
            period=entry.period,
            quality_status=entry.quality_status,
            summary=entry.summary,
        )


class CatalogResponse(BaseModel):
    """Every indexed report, the glossary size and example questions."""

    index_version: str | None
    documents: list[DocumentOut]
    glossary_entries: int
    suggestions: list[str]


class GlossaryEntryOut(BaseModel):
    """A glossary entry."""

    id: str
    term: str
    aliases: list[str]
    expansion: str | None
    description: str | None
    status: str

    @classmethod
    def of(cls, entry: GlossaryEntry) -> GlossaryEntryOut:
        """Response view of a glossary entry."""
        return cls(
            id=entry.id,
            term=entry.term,
            aliases=list(entry.aliases),
            expansion=entry.expansion,
            description=entry.description,
            status=entry.status.value,
        )


class GlossaryResponse(BaseModel):
    """Glossary entries matching the query (all entries without one)."""

    entries: list[GlossaryEntryOut]


class SourceResponse(BaseModel):
    """A whole report rendered as sanitised HTML, for the source viewer."""

    doc_id: str
    label: str
    period: str
    html: str


class CitationOut(BaseModel):
    """A source cited by an answer."""

    id: str
    doc_id: str
    label: str
    section: str
    page: int | None
    period: str
    excerpt: str


class AnswerMeta(BaseModel):
    """Tracing data shown under an answer."""

    request_id: str
    latency_ms: int
    retrieval_mode: str
    reason: str
    models: list[str]
    input_tokens: int
    output_tokens: int


class AnswerEvent(BaseModel):
    """Payload of the ``answer`` server-sent event."""

    status: str
    verified: bool
    language: str
    html: str
    markdown: str
    citations: list[CitationOut]
    caveats: list[str]
    meta: AnswerMeta

    @classmethod
    def of(cls, answer: Answer, request_id: str) -> AnswerEvent:
        """Event view of an answer."""
        return cls(
            status=answer.status,
            verified=answer.verified,
            language=answer.language.value,
            html=answer.html,
            markdown=answer.markdown,
            citations=[
                CitationOut(
                    id=citation.id,
                    doc_id=citation.doc_id,
                    label=citation.label,
                    section=citation.section,
                    page=citation.page,
                    period=citation.period,
                    excerpt=citation.excerpt,
                )
                for citation in answer.citations
            ],
            caveats=list(answer.caveats),
            meta=AnswerMeta(
                request_id=request_id,
                latency_ms=answer.latency_ms,
                retrieval_mode=answer.retrieval_mode,
                reason=answer.reason,
                models=[usage.model for usage in answer.usage],
                input_tokens=sum(usage.input_tokens for usage in answer.usage),
                output_tokens=sum(usage.output_tokens for usage in answer.usage),
            ),
        )


class ErrorBody(BaseModel):
    """Error details; ``request_id`` correlates with the server log."""

    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    """Envelope of every error response."""

    error: ErrorBody
