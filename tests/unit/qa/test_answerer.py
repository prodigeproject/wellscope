from __future__ import annotations

import re
from typing import Any

import pytest

from wellscope.domain.messages import Language
from wellscope.errors import ModelError
from wellscope.llm.fakes import FakeChatModel
from wellscope.qa.answerer import Answerer
from wellscope.retrieval.models import Source

SOURCES = (Source("S1", "ddr-32", "DDR #32", "Costs (USD)", 1, "- Daily Cost: 348,640.02"),)
REPLY: dict[str, Any] = {
    "status": "answered",
    "answer_markdown": "348,640.02 USD [S1]",
    "citations": ["S1"],
    "caveats": [],
}


def test_sources_are_nonce_delimited_and_the_language_is_named() -> None:
    model = FakeChatModel(lambda request: REPLY)
    draft, result = Answerer(model).answer("Berapa daily cost?", Language.ID, SOURCES)
    request = model.requests[0]
    nonce = re.search(r'nonce="([0-9a-f]{16,})"', request.user)
    assert nonce is not None
    assert nonce.group(1) in request.system
    assert "Indonesian" in request.system
    assert "<question>Berapa daily cost?</question>" in request.user
    assert draft.citations == ("S1",)
    assert result.model == "fake-chat"


def test_each_request_uses_a_fresh_nonce() -> None:
    model = FakeChatModel(lambda request: REPLY)
    answerer = Answerer(model)
    answerer.answer("q", Language.EN, SOURCES)
    answerer.answer("q", Language.EN, SOURCES)
    first, second = (re.findall(r'nonce="(\w+)"', r.user)[0] for r in model.requests)
    assert first != second


def test_verification_feedback_is_sent_when_regenerating() -> None:
    model = FakeChatModel(lambda request: REPLY)
    Answerer(model).answer("q", Language.EN, SOURCES, feedback="number 9 is not in [S1]")
    assert "number 9 is not in [S1]" in model.requests[0].user


def test_a_reply_that_breaks_the_schema_is_a_model_error() -> None:
    model = FakeChatModel(lambda request: {"status": "sure"})
    with pytest.raises(ModelError) as raised:
        Answerer(model).answer("q", Language.EN, SOURCES)
    assert raised.value.code == "model_bad_output"
