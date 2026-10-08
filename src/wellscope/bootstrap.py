"""Composition root: builds adapters from settings for the CLI and the web app."""

from __future__ import annotations

import openai

from wellscope.config import Settings
from wellscope.indexing import IndexProjector
from wellscope.llm.openai_adapter import OpenAIEmbedder
from wellscope.llm.ports import Embedder
from wellscope.storage.vector_cache import VectorCache

OPENAI_MAX_RETRIES = 2


def openai_client(settings: Settings) -> openai.OpenAI | None:
    """Client with bounded retries (backoff on 429/5xx/timeouts), or ``None`` without a key."""
    key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    if not key:
        return None
    return openai.OpenAI(
        api_key=key, timeout=settings.llm_timeout_s, max_retries=OPENAI_MAX_RETRIES
    )


def embedder(settings: Settings) -> Embedder | None:
    """Embedding adapter, or ``None`` when no API key is configured."""
    client = openai_client(settings)
    return OpenAIEmbedder(client, settings.embedding_model) if client else None


def index_projector(settings: Settings) -> IndexProjector:
    """Index builder used by ``wellscope ingest``."""
    cache = VectorCache(settings.embedding_cache_path)
    return IndexProjector(settings.database_path, embedder(settings), cache)
