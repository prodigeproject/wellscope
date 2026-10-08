"""Deterministic, offline stand-ins for model adapters (used by tests and demos)."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Sequence
from typing import Any

from wellscope.domain.text import search_terms
from wellscope.llm.ports import ChatRequest, ChatResult

HASH_DIMENSIONS = 256

Responder = Callable[[ChatRequest], dict[str, Any]]


class HashEmbedder:
    """Feature-hashing embedder: texts sharing keywords get similar vectors."""

    def __init__(self, dimensions: int = HASH_DIMENSIONS) -> None:
        self._dimensions = dimensions

    @property
    def model(self) -> str:
        """Identifier that encodes the dimensionality."""
        return f"hash-{self._dimensions}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """L2-normalised bag-of-keywords vectors."""
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        for term in search_terms(text):
            digest = hashlib.sha256(term.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self._dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class FakeChatModel:
    """Replies through a scripted function and records every request."""

    def __init__(self, responder: Responder, model: str = "fake-chat") -> None:
        self._responder = responder
        self._model = model
        self.requests: list[ChatRequest] = []

    @property
    def model(self) -> str:
        """Identifier reported in traces."""
        return self._model

    def complete(self, request: ChatRequest) -> ChatResult:
        """Return the scripted reply for ``request``."""
        self.requests.append(request)
        return ChatResult(
            content=self._responder(request),
            model=self._model,
            input_tokens=len(request.system + request.user) // 4,
            output_tokens=50,
            latency_ms=1,
        )
