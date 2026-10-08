from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest

from wellscope.errors import ModelError
from wellscope.llm.fakes import HashEmbedder
from wellscope.llm.openai_adapter import OpenAIChatModel, OpenAIEmbedder
from wellscope.llm.ports import ChatRequest

REQUEST = ChatRequest(system="s", user="u", schema_name="answer", schema={"type": "object"})


def bad_request(message: str) -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.test/v1/responses"))
    return openai.BadRequestError(message, response=response, body=None)


class FakeResponses:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def reply(text: str) -> SimpleNamespace:
    usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    return SimpleNamespace(output_text=text, usage=usage, model="m-1")


def model_with(outcomes: list[Any]) -> tuple[OpenAIChatModel, FakeResponses]:
    responses = FakeResponses(outcomes)
    client = SimpleNamespace(responses=responses)
    return OpenAIChatModel(client, "m-1", reasoning_effort="none"), responses  # type: ignore[arg-type]


def test_chat_sends_store_false_strict_schema_and_parses_json() -> None:
    model, responses = model_with([reply('{"answer": "ok"}')])
    result = model.complete(REQUEST)
    assert result.content == {"answer": "ok"}
    call = responses.calls[0]
    assert call["store"] is False
    assert call["text"]["format"]["strict"] is True
    assert call["temperature"] == 0


def test_chat_retries_once_without_a_rejected_parameter_and_remembers() -> None:
    error = bad_request("Unsupported parameter: 'temperature' is not supported with this model.")
    model, responses = model_with([error, reply("{}"), reply("{}")])
    model.complete(REQUEST)
    model.complete(REQUEST)
    assert "temperature" in responses.calls[0]
    assert "temperature" not in responses.calls[1]
    assert "temperature" not in responses.calls[2]


def test_chat_reports_invalid_json_as_a_model_error() -> None:
    model, _ = model_with([reply("not json")])
    with pytest.raises(ModelError) as raised:
        model.complete(REQUEST)
    assert raised.value.code == "model_bad_output"


def test_chat_maps_unknown_bad_requests_to_model_errors() -> None:
    model, _ = model_with([bad_request("context length exceeded")])
    with pytest.raises(ModelError) as raised:
        model.complete(REQUEST)
    assert raised.value.code == "model_error"


def test_embedder_batches_and_keeps_input_order() -> None:
    def create(model: str, input: list[str]) -> SimpleNamespace:
        data = [SimpleNamespace(index=i, embedding=[float(len(t))]) for i, t in enumerate(input)]
        return SimpleNamespace(data=list(reversed(data)))

    client = SimpleNamespace(embeddings=SimpleNamespace(create=create))
    embedder = OpenAIEmbedder(client, "e-1")  # type: ignore[arg-type]
    texts = ["a" * n for n in range(1, 140)]
    assert embedder.embed(texts) == [[float(n)] for n in range(1, 140)]


def test_hash_embedder_is_deterministic_and_keyword_sensitive() -> None:
    embedder = HashEmbedder()
    first, second, other = embedder.embed(["daily cost report", "daily cost report", "weather"])
    assert first == second
    assert sum(a * b for a, b in zip(first, other, strict=True)) == 0
