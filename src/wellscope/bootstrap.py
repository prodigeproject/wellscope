"""Composition root: builds adapters from settings for the CLI and the web app."""

from __future__ import annotations

import openai

from wellscope.config import Settings
from wellscope.indexing import IndexProjector
from wellscope.llm.openai_adapter import OpenAIChatModel, OpenAIEmbedder
from wellscope.llm.ports import Embedder
from wellscope.qa.analyzer import Analyzer
from wellscope.qa.answerer import Answerer
from wellscope.qa.service import QAService
from wellscope.retrieval.retriever import Retriever
from wellscope.retrieval.search import HybridSearch
from wellscope.storage.index_reader import SearchIndex
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


def qa_service(settings: Settings) -> QAService:
    """Question-answering service over the index at ``settings.database_path``."""
    client = openai_client(settings)
    index = SearchIndex(settings.database_path)
    embedder = OpenAIEmbedder(client, settings.embedding_model) if client else None
    retriever = Retriever(index, HybridSearch(index, embedder), settings.context_token_budget)
    if client is None:
        return QAService(index, retriever, Analyzer(None), None)
    analyzer = Analyzer(OpenAIChatModel(client, settings.analyzer_model))
    answerer = Answerer(OpenAIChatModel(client, settings.chat_model))
    return QAService(index, retriever, analyzer, answerer)
