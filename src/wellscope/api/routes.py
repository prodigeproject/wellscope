"""HTTP endpoints. There is deliberately no upload or ingest endpoint: data enters only through
the local ``wellscope ingest`` command, which keeps untrusted files off the network surface."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse

from wellscope import __version__
from wellscope.api.schemas import (
    DOC_ID_PATTERN,
    MAX_GLOSSARY_QUERY,
    AnswerEvent,
    CatalogResponse,
    ChatBody,
    DocumentOut,
    ErrorResponse,
    GlossaryEntryOut,
    GlossaryResponse,
    HealthResponse,
    SourceResponse,
)
from wellscope.api.sse import SSE_HEADERS, Question, answer_events
from wellscope.domain.catalog import CatalogEntry
from wellscope.qa.analyzer import Turn
from wellscope.qa.html import render_answer
from wellscope.qa.suggestions import suggested_questions
from wellscope.retrieval.ports import ReportIndex

if TYPE_CHECKING:
    from wellscope.api.app import AppState

logger = logging.getLogger(__name__)
NOT_FOUND = 404
TOO_MANY_REQUESTS = 429
UNPROCESSABLE = 422
ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (404, 413, 422, 429)
}
router = APIRouter(prefix="/api", responses=ERRORS)


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Whether an index is loaded and a model is configured (never reveals the key)."""
    state = _state(request)
    index = state.services.index
    available = index.available()
    return HealthResponse(
        status="ok" if available else "no_index",
        version=__version__,
        index_version=index.version(),
        documents=len(index.catalog()) if available else 0,
        glossary_entries=len(index.glossary()) if available else 0,
        model_configured=state.services.model_configured,
    )


@router.get("/catalog", response_model=CatalogResponse)
def catalog(request: Request) -> CatalogResponse:
    """Every indexed report, the glossary size and example questions."""
    index = _state(request).services.index
    if not index.available():
        return CatalogResponse(index_version=None, documents=[], glossary_entries=0, suggestions=[])
    entries = index.catalog()
    return CatalogResponse(
        index_version=index.version(),
        documents=[DocumentOut.of(entry) for entry in entries],
        glossary_entries=len(index.glossary()),
        suggestions=suggested_questions(entries),
    )


@router.get("/glossary", response_model=GlossaryResponse)
def glossary(
    request: Request, q: Annotated[str, Query(max_length=MAX_GLOSSARY_QUERY)] = ""
) -> GlossaryResponse:
    """Glossary entries whose term, aliases, expansion or description contain ``q``."""
    index = _state(request).services.index
    if not index.available():
        return GlossaryResponse(entries=[])
    needle = q.strip().casefold()
    entries = [
        GlossaryEntryOut.of(entry)
        for entry in index.glossary()
        if needle
        in " ".join(
            (entry.term, *entry.aliases, entry.expansion or "", entry.description or "")
        ).casefold()
    ]
    return GlossaryResponse(entries=entries)


@router.get("/sources/{doc_id}", response_model=SourceResponse)
def source(
    request: Request, doc_id: Annotated[str, Path(pattern=DOC_ID_PATTERN)]
) -> SourceResponse:
    """A whole report as sanitised HTML; reports are addressed by id only, never by path."""
    index = _state(request).services.index
    entry = _find_report(index, doc_id)
    if entry is None:
        raise HTTPException(NOT_FOUND, "No report with that id.")
    markdown = index.rendered([doc_id]).get(doc_id, "")
    return SourceResponse(
        doc_id=doc_id, label=entry.label, period=entry.period, html=render_answer(markdown, ())
    )


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {"schema": AnswerEvent.model_json_schema()}}}
    },
)
async def chat(request: Request, body: ChatBody) -> StreamingResponse:
    """Answer a question as server-sent events: ``stage`` events, then ``answer`` or ``error``."""
    state = _state(request)
    wait = state.limiter.acquire(request.client.host if request.client else "unknown")
    if wait:
        headers = {"Retry-After": str(math.ceil(wait))}
        raise HTTPException(TOO_MANY_REQUESTS, "Too many questions; please wait.", headers)
    limit = state.settings.max_question_chars
    if len(body.question) > limit:
        raise HTTPException(UNPROCESSABLE, f"Questions are limited to {limit} characters.")
    question_log = {"question": body.question} if state.settings.log_questions else {}
    logger.info("question received", extra={"chars": len(body.question), **question_log})
    history = tuple(Turn(turn.question, turn.answer) for turn in body.history)
    question = Question(body.question, history, request.state.request_id)
    events = answer_events(state.services.qa, question, state.llm_slots)
    return StreamingResponse(events, media_type="text/event-stream", headers=SSE_HEADERS)


def _find_report(index: ReportIndex, doc_id: str) -> CatalogEntry | None:
    if not index.available():
        return None
    return next((entry for entry in index.catalog() if entry.doc_id == doc_id), None)


def _state(request: Request) -> AppState:
    state: AppState = request.app.state.wellscope
    return state
