"""Question answering: analyse, apply the scope policy, retrieve, answer, verify and render.

Every outcome is an ``Answer``: refusals, not-found replies and failures use canonical messages,
so the interface never has to interpret exceptions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Literal

from wellscope.domain.messages import Language, MessageKind, message, not_found
from wellscope.errors import ModelError
from wellscope.llm.ports import ChatResult
from wellscope.qa.analyzer import Analysis, Analyzer, Scope, Turn
from wellscope.qa.answerer import Answerer, Draft
from wellscope.qa.conflicts import conflict_caveats, mentions_conflict
from wellscope.qa.extractors import clean_question, detect_language
from wellscope.qa.html import render_answer
from wellscope.qa.policy import decide_scope, has_domain_signal
from wellscope.qa.verifier import Verification, cited_ids, verify
from wellscope.retrieval.models import Retrieval, RetrievalQuery, Source
from wellscope.retrieval.ports import ReportIndex
from wellscope.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)
Stage = Literal["analyzing", "retrieving", "composing", "verifying"]
StageCallback = Callable[[Stage], None]
ResultStatus = Literal["answered", "not_found", "out_of_scope", "error"]
EXCERPT_CHARS = 600
MILLISECONDS = 1000
UNVERIFIED_NOTE = {
    Language.EN: "Some figures could not be matched to the cited sources: {numbers}.",
    Language.ID: "Beberapa angka tidak dapat dicocokkan dengan sumber yang dikutip: {numbers}.",
}


class StageCancelled(Exception):  # noqa: N818 - a control signal, not an error
    """Raised by a stage callback to stop answering, for example when the client went away."""


@dataclass(frozen=True, slots=True)
class Citation:
    """A source the answer cites, with enough context to show it."""

    id: str
    doc_id: str
    label: str
    section: str
    page: int | None
    excerpt: str
    period: str = ""


@dataclass(frozen=True, slots=True)
class ModelUsage:
    """One model call, for latency and cost reporting."""

    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(frozen=True, slots=True)
class Answer:
    """The outcome of a question, ready to display."""

    status: ResultStatus
    language: Language
    markdown: str
    html: str
    citations: tuple[Citation, ...] = ()
    caveats: tuple[str, ...] = ()
    verified: bool = True
    reason: str = ""
    retrieval_mode: str = "none"
    latency_ms: int = 0
    usage: tuple[ModelUsage, ...] = ()


class QAService:
    """Answers questions about the indexed reports and glossary."""

    def __init__(
        self,
        index: ReportIndex,
        retriever: Retriever,
        analyzer: Analyzer,
        answerer: Answerer | None,
    ) -> None:
        self._index = index
        self._retriever = retriever
        self._analyzer = analyzer
        self._answerer = answerer

    def ask(
        self,
        question: str,
        history: Sequence[Turn] = (),
        on_stage: StageCallback | None = None,
    ) -> Answer:
        """Answer ``question``; ``on_stage`` is told when each pipeline stage starts."""
        started = perf_counter()
        answer = self._answer(clean_question(question), history, on_stage or _ignore)
        return replace(answer, latency_ms=int((perf_counter() - started) * MILLISECONDS))

    def _answer(self, question: str, history: Sequence[Turn], notify: StageCallback) -> Answer:
        language = detect_language(question)
        if not self._index.available():
            return _fixed("error", MessageKind.NO_INDEX, language, "no_index")
        if self._answerer is None:
            return _fixed("error", MessageKind.NO_API_KEY, language, "no_api_key")
        notify("analyzing")
        catalog = self._index.catalog()
        analysis = self._analyzer.analyze(question, history, catalog)
        usage = _usage(analysis.result)
        hits = self._retriever.glossary_hits(analysis.standalone_question, analysis.glossary_terms)
        signal = has_domain_signal(question, analysis.references, hits, catalog)
        if analysis.scope is Scope.OUT_OF_SCOPE and not signal:
            signal = self._retriever.names_corpus_entity(question)
        decision = decide_scope(analysis.scope, signal)
        if not decision.allowed:
            kind = MessageKind.OUT_OF_SCOPE
            return _fixed("out_of_scope", kind, analysis.language, decision.reason, usage)
        notify("retrieving")
        retrieval = self._retriever.retrieve(_query(analysis))
        labels = [entry.label for entry in catalog]
        if retrieval.unmatched_filter or not retrieval.sources:
            reason = "unmatched_filter" if retrieval.unmatched_filter else "no_sources"
            return _not_found(analysis.language, labels, reason, usage)
        try:
            draft, check, usage = self._draft(self._answerer, analysis, retrieval, usage, notify)
        except ModelError as error:
            logger.warning("answer model failed (%s)", error.code)
            return _fixed("error", MessageKind.MODEL_ERROR, analysis.language, error.code, usage)
        reports = {entry.doc_id: entry.label for entry in catalog}
        text = f"{question}\n{draft.markdown}"
        draft = _state_conflicts(draft, text, analysis.language, retrieval, reports)
        return _finish(draft, check, analysis.language, retrieval, labels, usage)

    def _draft(
        self,
        answerer: Answerer,
        analysis: Analysis,
        retrieval: Retrieval,
        usage: tuple[ModelUsage, ...],
        notify: StageCallback,
    ) -> tuple[Draft, Verification, tuple[ModelUsage, ...]]:
        """Draft and verify; a draft that fails verification is regenerated once."""
        question, sources = analysis.standalone_question, retrieval.sources
        notify("composing")
        draft, result = answerer.answer(question, analysis.language, sources)
        usage += _usage(result)
        notify("verifying")
        check = verify(draft, sources)
        if not check.ok:
            logger.info("draft failed verification: %s", check.feedback())
            draft, result = answerer.answer(question, analysis.language, sources, check.feedback())
            usage += _usage(result)
            check = verify(draft, sources)
        return draft, check, usage


def _state_conflicts(
    draft: Draft,
    text: str,
    language: Language,
    retrieval: Retrieval,
    reports: Mapping[str, str],
) -> Draft:
    """Replace the model's notes on a data conflict with every value, taken from the checks."""
    if draft.status != "answered":
        return draft
    notes = conflict_caveats(retrieval.conflicts, reports, text, language)
    if not notes:
        return draft
    touched = [conflict for conflict in retrieval.conflicts if mentions_conflict(text, conflict)]
    others = [
        caveat
        for caveat in draft.caveats
        if not any(mentions_conflict(caveat, conflict) for conflict in touched)
    ]
    return replace(draft, caveats=(*notes, *others))


def _finish(
    draft: Draft,
    check: Verification,
    language: Language,
    retrieval: Retrieval,
    labels: Sequence[str],
    usage: tuple[ModelUsage, ...],
) -> Answer:
    if draft.status == "out_of_scope":
        return _fixed("out_of_scope", MessageKind.OUT_OF_SCOPE, language, "answer_refused", usage)
    if draft.status == "not_found" or not draft.markdown:
        return _not_found(language, labels, "answer_not_found", usage)
    by_id = {source.id: source for source in retrieval.sources}
    cited = [by_id[source_id] for source_id in cited_ids(draft) if source_id in by_id]
    if not cited:
        # Every fact must be cited; an answer that still cites nothing is not grounded.
        return _not_found(language, labels, "uncited", usage)
    caveats = list(draft.caveats)
    if check.unsupported_numbers:
        numbers = ", ".join(check.unsupported_numbers)
        caveats.append(UNVERIFIED_NOTE[language].format(numbers=numbers))
    return Answer(
        status="answered",
        language=language,
        markdown=draft.markdown,
        html=render_answer(draft.markdown, by_id.keys()),
        citations=tuple(_citation(source) for source in cited),
        caveats=tuple(caveats),
        verified=check.ok,
        reason="answered",
        retrieval_mode=retrieval.mode,
        usage=usage,
    )


def _fixed(
    status: ResultStatus,
    kind: MessageKind,
    language: Language,
    reason: str,
    usage: tuple[ModelUsage, ...] = (),
) -> Answer:
    text = message(kind, language)
    return Answer(status, language, text, _html(text), reason=reason, usage=usage)


def _not_found(
    language: Language, labels: Sequence[str], reason: str, usage: tuple[ModelUsage, ...]
) -> Answer:
    text = not_found(language, labels)
    return Answer("not_found", language, text, _html(text), reason=reason, usage=usage)


def _html(text: str, source_ids: Collection[str] = ()) -> str:
    return render_answer(text, source_ids)


def _query(analysis: Analysis) -> RetrievalQuery:
    return RetrievalQuery(
        question=analysis.standalone_question,
        intent=analysis.intent,
        filters=analysis.filters,
        glossary_terms=analysis.glossary_terms,
        search_queries=analysis.search_queries,
    )


def _citation(source: Source) -> Citation:
    return Citation(
        id=source.id,
        doc_id=source.doc_id,
        label=source.label,
        section=source.section,
        page=source.page,
        excerpt=_without_provenance(source.text)[:EXCERPT_CHARS],
        period=source.period,
    )


def _without_provenance(text: str) -> str:
    """Drop the ``[DDR #12 · … · p.1]`` header line; the citation shows that information."""
    first, _, rest = text.partition("\n")
    return rest if first.startswith("[") and first.endswith("]") and rest else text


def _usage(result: ChatResult | None) -> tuple[ModelUsage, ...]:
    if result is None:
        return ()
    usage = ModelUsage(result.model, result.input_tokens, result.output_tokens, result.latency_ms)
    return (usage,)


def _ignore(stage: Stage) -> None:
    """Default stage callback."""
