from __future__ import annotations

from wellscope.domain.glossary import GlossaryEntry
from wellscope.retrieval.glossary_index import GlossaryHit, GlossaryIndex


def gloss(term: str, *aliases: str, expansion: str | None = None) -> GlossaryEntry:
    return GlossaryEntry(
        id=f"gl-{term.lower()}",
        term=term,
        aliases=aliases or (term,),
        expansion=expansion,
        source_row=1,
    )


INDEX = GlossaryIndex(
    [
        gloss("NPT", expansion="Non-Productive Time"),
        gloss("POH / POOH", "POH", "POOH", expansion="Pull Out Of Hole"),
        gloss("LOT", expansion="Leak-Off Test"),
        gloss("in", expansion="inch"),
    ]
)


def mentioned(text: str) -> list[tuple[str, bool]]:
    return [(hit.entry.term, hit.strong) for hit in INDEX.mentions(text)]


def looked_up(term: str) -> tuple[str, str] | None:
    hit: GlossaryHit | None = INDEX.lookup(term)
    return (hit.entry.term, hit.kind) if hit else None


def test_exact_case_mentions_are_strong_and_lower_case_mentions_are_weak() -> None:
    assert mentioned("Berapa NPT di DDR 32?") == [("NPT", True)]
    assert mentioned("what is npt") == [("NPT", False)]


def test_aliases_and_expansions_are_recognised() -> None:
    assert mentioned("When did they POOH?") == [("POH / POOH", True)]
    assert mentioned("total non productive time") == [("NPT", True)]


def test_stopword_aliases_and_partial_words_are_not_mentions() -> None:
    assert mentioned("What happened in the lot?") == [("LOT", False)]
    assert mentioned("pilot NPTX") == []


def test_lookup_resolves_terms_named_by_the_analyzer() -> None:
    assert looked_up("NPT") == ("NPT", "exact")
    assert looked_up("pooh") == ("POH / POOH", "alias")
    assert looked_up("leak off test") == ("LOT", "expansion")
    assert looked_up("Non-Productive Tme") == ("NPT", "fuzzy")
    assert looked_up("weather") is None


def test_aliases_starting_with_a_symbol_match_inside_names() -> None:
    index = GlossaryIndex([gloss("-1", expansion=None), gloss("NPT")])
    assert [hit.entry.term for hit in index.mentions("What does WELL-1 mean?")] == ["-1"]
    assert index.mentions("a 12-1/4 in hole") == []
