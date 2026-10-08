from __future__ import annotations

from collections.abc import Sequence

from wellscope.config import Settings
from wellscope.errors import ModelError
from wellscope.indexing import IndexProjector
from wellscope.llm.fakes import HashEmbedder
from wellscope.pipeline import run_ingest
from wellscope.storage.index_reader import SearchIndex
from wellscope.storage.vector_cache import VectorCache


class CountingEmbedder(HashEmbedder):
    def __init__(self) -> None:
        super().__init__()
        self.embedded = 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded += len(texts)
        return super().embed(texts)


class FailingEmbedder(HashEmbedder):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise ModelError("provider down", code="model_timeout")


def projector(settings: Settings, embedder: HashEmbedder | None) -> IndexProjector:
    cache = VectorCache(settings.embedding_cache_path)
    return IndexProjector(settings.database_path, embedder, cache)


def test_ingest_builds_a_searchable_index_and_reuses_cached_embeddings(
    settings: Settings,
) -> None:
    embedder = CountingEmbedder()
    result = run_ingest(settings, projector(settings, embedder))
    index = SearchIndex(settings.database_path)
    assert index.version() == result.manifest.index_version
    assert [entry.doc_type for entry in index.catalog()] == ["GENERIC"]
    assert index.keyword_search(["oil"], None, 3)
    assert index.embedding_model() == embedder.model
    embedded = embedder.embedded
    assert embedded > 0
    run_ingest(settings, projector(settings, embedder))
    assert embedder.embedded == embedded


def test_ingest_falls_back_to_keyword_search_when_embeddings_fail(settings: Settings) -> None:
    result = run_ingest(settings, projector(settings, FailingEmbedder()))
    assert any("model_timeout" in note for note in result.notes)
    index = SearchIndex(settings.database_path)
    assert index.embedding_model() is None
    assert index.keyword_search(["oil"], None, 3)


def test_ingest_without_an_api_key_builds_a_keyword_only_index(settings: Settings) -> None:
    result = run_ingest(settings, projector(settings, None))
    assert any("OPENAI_API_KEY" in note for note in result.notes)
    assert SearchIndex(settings.database_path).keyword_search(["oil"], None, 3)
