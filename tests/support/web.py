"""Web app wiring for API tests: a real index with scripted models."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from wellscope.api.app import Services, create_app
from wellscope.config import Settings
from wellscope.domain.glossary import GlossaryEntry
from wellscope.llm.fakes import FakeChatModel
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


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "output_dir": tmp_path / "processed",
        "allowed_hosts": ["testserver", "127.0.0.1", "localhost"],
        "rate_limit_per_min": 60,
    }
    return Settings(**(values | overrides))


def make_client(settings: Settings, index: SearchIndex) -> TestClient:
    retriever = Retriever(index, HybridSearch(index, None), budget_tokens=16000)
    service = QAService(
        index,
        retriever,
        Analyzer(FakeChatModel(lambda request: ANALYSIS, model="fake-analyzer")),
        Answerer(FakeChatModel(cite_daily_cost)),
    )
    services = Services(qa=service, index=index, model_configured=True)
    return TestClient(create_app(settings, services))
