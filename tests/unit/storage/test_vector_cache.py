from __future__ import annotations

from pathlib import Path

import pytest

from wellscope.storage.vector_cache import VectorCache, text_hash


def test_vectors_round_trip_per_model(tmp_path: Path) -> None:
    cache = VectorCache(tmp_path / "cache" / "embeddings.db")
    key = text_hash("daily cost")
    cache.put_many("model-a", {key: [0.25, -1.5]})
    assert cache.get_many("model-a", [key, text_hash("other")]) == {key: [0.25, -1.5]}
    assert cache.get_many("model-b", [key]) == {}


def test_float32_storage_keeps_embedding_precision(tmp_path: Path) -> None:
    cache = VectorCache(tmp_path / "embeddings.db")
    cache.put_many("m", {"k": [0.1234567]})
    assert cache.get_many("m", ["k"])["k"][0] == pytest.approx(0.1234567, rel=1e-6)


def test_text_hash_is_stable_and_content_sensitive() -> None:
    assert text_hash("a") == text_hash("a")
    assert text_hash("a") != text_hash("a ")
