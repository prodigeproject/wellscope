from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from tests.support.documents import make_document
from tests.support.index import build_test_index
from wellscope.errors import ModelError
from wellscope.llm.fakes import HashEmbedder
from wellscope.retrieval.search import HybridSearch, reciprocal_rank_fusion


class BrokenEmbedder(HashEmbedder):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise ModelError("down", code="model_timeout")


def test_rrf_rewards_items_ranked_well_by_several_lists_and_keeps_ties_stable() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]])
    assert [item for item, _ in fused] == ["b", "a", "d", "c"]
    assert [item for item, _ in reciprocal_rank_fusion([["x"], ["y"]])] == ["x", "y"]


def test_hybrid_search_fuses_keyword_and_vector_rankings(tmp_path: Path) -> None:
    embedder = HashEmbedder()
    index = build_test_index(tmp_path / "i.db", [make_document()], embedder=embedder)
    hits = HybridSearch(index, embedder).search(["reamer attempt"], None, 3)
    assert hits[0] == "ddr-well-a-1-0012:operation:1"


def test_hybrid_search_degrades_to_keywords_when_vectors_are_unusable(tmp_path: Path) -> None:
    index = build_test_index(tmp_path / "i.db", [make_document()], embedder=HashEmbedder())
    assert HybridSearch(index, BrokenEmbedder()).search(["reamer"], None, 3)
    assert HybridSearch(index, HashEmbedder(dimensions=8)).search(["reamer"], None, 3)
    assert HybridSearch(index, None).search(["reamer"], None, 3)
