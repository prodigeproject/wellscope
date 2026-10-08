from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from tests.support.documents import make_document, make_glossary
from tests.support.index import build_test_index
from wellscope.domain.glossary import GlossaryEntry
from wellscope.domain.messages import Language, MessageKind, message
from wellscope.errors import ModelError
from wellscope.llm.fakes import FakeChatModel, Responder
from wellscope.llm.ports import ChatRequest
from wellscope.qa.analyzer import Analyzer
from wellscope.qa.answerer import Answerer
from wellscope.qa.service import QAService
from wellscope.retrieval.retriever import Retriever
from wellscope.retrieval.search import HybridSearch
from wellscope.storage.index_reader import SearchIndex

NPT = GlossaryEntry(
    id="gl-npt", term="NPT", aliases=("NPT",), expansion="Non-Productive Time", source_row=1
)
ANALYSIS: dict[str, Any] = {
    "language": "en",
    "scope": "in_scope",
    "intent": "report_fact",
    "standalone_question": "What was the daily cost in DDR 12?",
    "glossary_terms": [],
    "doc_types": ["DDR"],
    "report_numbers": [12],
    "dates": [],
    "date_from": None,
    "date_to": None,
    "latest": False,
    "search_queries_en": ["daily cost"],
}


def cite_daily_cost(request: ChatRequest) -> dict[str, Any]:
    source = re.search(r'<source id="(S\d+)"[^>]*section="Costs \(USD\)"', request.user)
    assert source is not None
    return {
        "status": "answered",
        "answer_markdown": f"The daily cost was **250,000.00** [{source.group(1)}].",
        "citations": [source.group(1)],
        "caveats": [],
    }


class Setup:
    def __init__(
        self, tmp_path: Path, analysis: dict[str, Any], answer: Responder | None = None
    ) -> None:
        index = build_test_index(tmp_path / "i.db", [make_document()], make_glossary(NPT))
        self.analyzer_model = FakeChatModel(lambda request: analysis, model="fake-analyzer")
        self.answer_model = FakeChatModel(answer or cite_daily_cost)
        self.service = QAService(
            index,
            Retriever(index, HybridSearch(index, None), budget_tokens=16000),
            Analyzer(self.analyzer_model),
            Answerer(self.answer_model),
        )


def test_an_answer_carries_html_citations_stages_and_usage(tmp_path: Path) -> None:
    setup = Setup(tmp_path, ANALYSIS)
    stages: list[str] = []
    answer = setup.service.ask("What was the daily cost in DDR 12?", on_stage=stages.append)
    assert answer.status == "answered"
    assert answer.verified
    assert stages == ["analyzing", "retrieving", "composing", "verifying"]
    assert answer.citations[0].label == "DDR #12 (2026-01-14)"
    assert answer.citations[0].section == "Costs (USD)"
    assert "<strong>250,000.00</strong>" in answer.html
    assert 'class="cite"' in answer.html
    assert [usage.model for usage in answer.usage] == ["fake-analyzer", "fake-chat"]
    assert answer.retrieval_mode == "full"


def test_out_of_scope_questions_get_the_canonical_message(tmp_path: Path) -> None:
    analysis = {**ANALYSIS, "language": "id", "scope": "out_of_scope", "report_numbers": []}
    setup = Setup(tmp_path, analysis)
    answer = setup.service.ask("Siapa presiden Indonesia saat ini?")
    assert answer.status == "out_of_scope"
    assert answer.markdown == message(MessageKind.OUT_OF_SCOPE, Language.ID)
    assert setup.answer_model.requests == []


def test_names_written_in_the_reports_override_an_out_of_scope_verdict(tmp_path: Path) -> None:
    analysis = {**ANALYSIS, "scope": "out_of_scope", "report_numbers": [], "doc_types": []}
    setup = Setup(tmp_path, analysis)
    answer = setup.service.ask("How high was the MAASP?")
    assert setup.answer_model.requests
    assert answer.status == "answered"


def test_questions_about_missing_reports_list_the_available_ones(tmp_path: Path) -> None:
    setup = Setup(tmp_path, {**ANALYSIS, "report_numbers": [99]})
    answer = setup.service.ask("What was the daily cost in DDR 99?")
    assert answer.status == "not_found"
    assert answer.reason == "unmatched_filter"
    assert answer.markdown.endswith("Available reports: DDR #12 (2026-01-14).")
    assert setup.answer_model.requests == []


def test_a_not_found_draft_becomes_the_canonical_message(tmp_path: Path) -> None:
    def not_found(request: ChatRequest) -> dict[str, Any]:
        return {"status": "not_found", "answer_markdown": "", "citations": [], "caveats": []}

    answer = Setup(tmp_path, ANALYSIS, not_found).service.ask("Bit serial number in DDR 12?")
    assert answer.status == "not_found"
    assert answer.markdown.startswith(message(MessageKind.NOT_FOUND, Language.EN))


def test_unverified_answers_are_regenerated_once_then_flagged(tmp_path: Path) -> None:
    def invents(request: ChatRequest) -> dict[str, Any]:
        reply = cite_daily_cost(request)
        return {**reply, "answer_markdown": reply["answer_markdown"] + " Total 987,654.32."}

    setup = Setup(tmp_path, ANALYSIS, invents)
    answer = setup.service.ask("What was the daily cost in DDR 12?")
    assert len(setup.answer_model.requests) == 2
    assert "987,654.32" in setup.answer_model.requests[1].user
    assert answer.status == "answered"
    assert not answer.verified
    assert any("987,654.32" in caveat for caveat in answer.caveats)


def test_model_failures_become_error_answers(tmp_path: Path) -> None:
    def rate_limited(request: ChatRequest) -> dict[str, Any]:
        raise ModelError("slow down", code="model_rate_limited")

    answer = Setup(tmp_path, ANALYSIS, rate_limited).service.ask("Daily cost DDR 12?")
    assert answer.status == "error"
    assert answer.reason == "model_rate_limited"
    assert answer.markdown == message(MessageKind.MODEL_ERROR, Language.EN)


@pytest.mark.parametrize("missing", ["index", "api_key"])
def test_setup_problems_return_guidance(tmp_path: Path, missing: str) -> None:
    index = SearchIndex(tmp_path / "missing.db")
    if missing == "api_key":
        index = build_test_index(tmp_path / "i.db", [make_document()])
    retriever = Retriever(index, HybridSearch(index, None), budget_tokens=16000)
    service = QAService(index, retriever, Analyzer(None), None)
    answer = service.ask("Berapa daily cost DDR 12?")
    assert answer.status == "error"
    assert answer.reason == ("no_index" if missing == "index" else "no_api_key")
    kind = MessageKind.NO_INDEX if missing == "index" else MessageKind.NO_API_KEY
    assert answer.markdown == message(kind, Language.ID)


def test_an_answer_that_still_cites_nothing_after_the_retry_is_not_shown(
    tmp_path: Path,
) -> None:
    def uncited(request: ChatRequest) -> dict[str, Any]:
        text = "The well was drilled safely and on budget."
        return {"status": "answered", "answer_markdown": text, "citations": [], "caveats": []}

    setup = Setup(tmp_path, ANALYSIS, uncited)
    answer = setup.service.ask("How did the drilling go in DDR 12?")
    assert len(setup.answer_model.requests) == 2
    assert answer.status == "not_found"
    assert answer.reason == "uncited"
