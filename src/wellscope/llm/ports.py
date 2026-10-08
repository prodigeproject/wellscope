"""Model ports owned by the application; adapters (OpenAI, fakes) implement them."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """A structured-output request: the reply must match ``schema`` (JSON Schema)."""

    system: str
    user: str
    schema_name: str
    schema: dict[str, Any]
    max_output_tokens: int = 1200


@dataclass(frozen=True, slots=True)
class ChatResult:
    """Parsed JSON reply plus usage, for tracing and cost accounting."""

    content: dict[str, Any]
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class ChatModel(Protocol):
    """A language model that answers with JSON matching a schema."""

    @property
    def model(self) -> str:
        """Model identifier used for tracing and pricing."""
        ...

    def complete(self, request: ChatRequest) -> ChatResult:
        """Run one request; raises ``ModelError`` on failure."""
        ...


class Embedder(Protocol):
    """Turns texts into vectors for semantic search."""

    @property
    def model(self) -> str:
        """Embedding model identifier (vectors from different models never mix)."""
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in input order; raises ``ModelError`` on failure."""
        ...
