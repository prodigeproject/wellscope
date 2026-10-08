"""OpenAI adapters: structured chat through the Responses API, and embeddings.

Requests use ``store=False`` so prompts and documents are not retained by the provider. Some
models reject ``temperature`` or ``reasoning``; when one does, the adapter lowers the reasoning
effort to ``low`` or drops the parameter, retries, and remembers the change for later calls
(safely across threads), so any chat model configured by a reviewer works unchanged. Every
provider failure surfaces as a ``ModelError`` with a stable code.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Any

import openai

from wellscope.errors import ModelError
from wellscope.llm.ports import ChatRequest, ChatResult

logger = logging.getLogger(__name__)
EMBEDDING_BATCH = 64
MILLISECONDS = 1000
FALLBACK_EFFORT = "low"
# Each optional parameter may be relaxed twice (effort lowered, then dropped), plus the success.
MAX_ATTEMPTS = 5


class OpenAIChatModel:
    """Chat model with JSON-schema structured output."""

    def __init__(
        self, client: openai.OpenAI, model: str, *, reasoning_effort: str | None = "none"
    ) -> None:
        self._client = client
        self._model = model
        self._lock = threading.Lock()
        self._optional: dict[str, Any] = {"temperature": 0}
        if reasoning_effort:
            self._optional["reasoning"] = {"effort": reasoning_effort}

    @property
    def model(self) -> str:
        """Configured model name."""
        return self._model

    def complete(self, request: ChatRequest) -> ChatResult:
        """Send ``request``, relaxing optional parameters the model rejects."""
        started = perf_counter()
        response = self._create(request)
        try:
            content = json.loads(response.output_text)
        except (json.JSONDecodeError, TypeError) as error:
            raise ModelError("model returned invalid JSON", code="model_bad_output") from error
        usage = response.usage
        return ChatResult(
            content=content,
            model=response.model,
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
            latency_ms=int((perf_counter() - started) * MILLISECONDS),
        )

    def _create(self, request: ChatRequest) -> Any:
        for _ in range(MAX_ATTEMPTS):
            with self._lock:
                optional = dict(self._optional)
            try:
                return self._send(request, optional)
            except openai.BadRequestError as error:
                if not self._relax(str(error), optional):
                    raise _model_error(error) from error
            except openai.OpenAIError as error:
                raise _model_error(error) from error
        raise ModelError("the model rejected the request parameters", code="model_error")

    def _send(self, request: ChatRequest, optional: Mapping[str, Any]) -> Any:
        return self._client.responses.create(
            model=self._model,
            store=False,
            input=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": request.schema_name,
                    "schema": request.schema,
                    "strict": True,
                }
            },
            max_output_tokens=request.max_output_tokens,
            **optional,
        )

    def _relax(self, message: str, sent: Mapping[str, Any]) -> bool:
        """Lower the reasoning effort or drop the rejected parameter; False if none matches."""
        rejected = next((name for name in sent if name in message), None)
        if rejected is None:
            return False
        with self._lock:
            effort = sent[rejected].get("effort") if rejected == "reasoning" else None
            if effort is not None and effort != FALLBACK_EFFORT:
                self._optional[rejected] = {"effort": FALLBACK_EFFORT}
            else:
                self._optional.pop(rejected, None)
        logger.info("model %s rejected %s; retrying with it relaxed", self._model, rejected)
        return True


class OpenAIEmbedder:
    """Embeddings in batches."""

    def __init__(self, client: openai.OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    @property
    def model(self) -> str:
        """Configured embedding model."""
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in input order."""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBEDDING_BATCH):
            batch = list(texts[start : start + EMBEDDING_BATCH])
            try:
                response = self._client.embeddings.create(model=self._model, input=batch)
            except openai.OpenAIError as error:
                raise _model_error(error) from error
            vectors.extend(item.embedding for item in sorted(response.data, key=lambda d: d.index))
        return vectors


def _model_error(error: openai.OpenAIError) -> ModelError:
    """Map provider errors to stable codes without leaking request details."""
    if isinstance(error, openai.AuthenticationError):
        return ModelError("the API key was rejected", code="model_auth")
    if isinstance(error, openai.NotFoundError | openai.PermissionDeniedError):
        return ModelError(
            "the configured model is not available to this key", code="model_unavailable"
        )
    if isinstance(error, openai.RateLimitError):
        return ModelError("the model provider is rate limiting requests", code="model_rate_limited")
    if isinstance(error, openai.APITimeoutError):
        return ModelError("the model provider timed out", code="model_timeout")
    return ModelError(f"model request failed ({type(error).__name__})", code="model_error")
