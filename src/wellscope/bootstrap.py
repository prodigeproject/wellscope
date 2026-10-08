"""Composition root: builds adapters from settings for the CLI and the web app."""

from __future__ import annotations

from dataclasses import dataclass

import openai
from fastapi import FastAPI

from wellscope.api.app import Services, create_app
from wellscope.config import Settings
from wellscope.indexing import IndexProjector
from wellscope.llm.openai_adapter import OpenAIChatModel, OpenAIEmbedder
from wellscope.llm.ports import ChatModel, Embedder
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


@dataclass(frozen=True)
class Models:
    """Model adapters built from settings; all ``None`` without an API key."""

    chat: ChatModel | None
    analyzer: ChatModel | None
    embedder: Embedder | None


def models(settings: Settings) -> Models:
    """The configured OpenAI models (none when no key is set)."""
    client = openai_client(settings)
    if client is None:
        return Models(chat=None, analyzer=None, embedder=None)
    return Models(
        chat=OpenAIChatModel(client, settings.chat_model),
        analyzer=OpenAIChatModel(client, settings.analyzer_model),
        embedder=OpenAIEmbedder(client, settings.embedding_model),
    )


def index_projector(settings: Settings) -> IndexProjector:
    """Index builder used by ``wellscope ingest``."""
    cache = VectorCache(settings.embedding_cache_path)
    return IndexProjector(settings.database_path, models(settings).embedder, cache)


def qa_service(settings: Settings, index: SearchIndex | None = None) -> QAService:
    """Question-answering service over the index at ``settings.database_path``."""
    built = models(settings)
    index = index or SearchIndex(settings.database_path)
    search = HybridSearch(index, built.embedder)
    retriever = Retriever(index, search, settings.context_token_budget)
    answerer = Answerer(built.chat) if built.chat else None
    return QAService(index, retriever, Analyzer(built.analyzer), answerer)


def web_app(settings: Settings) -> FastAPI:
    """The web application served by ``wellscope serve``."""
    index = SearchIndex(settings.database_path)
    services = Services(
        qa=qa_service(settings, index),
        index=index,
        model_configured=openai_client(settings) is not None,
    )
    return create_app(settings, services)
