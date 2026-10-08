from __future__ import annotations

from datetime import date, datetime

from tests.support.documents import make_catalog_entry
from wellscope.domain.glossary import GlossaryEntry
from wellscope.qa.analyzer import Scope
from wellscope.qa.extractors import extract_references
from wellscope.qa.policy import decide_scope, has_domain_signal
from wellscope.retrieval.glossary_index import GlossaryHit

CATALOG = [make_catalog_entry("ddr-32", "DDR", 32, date(2026, 7, 19), datetime(2026, 7, 19))]
NPT = GlossaryEntry(id="gl-npt", term="NPT", aliases=("NPT",), source_row=1)


def signal(question: str, hits: list[GlossaryHit] | None = None) -> bool:
    references = extract_references(question, default_year=2026)
    return has_domain_signal(question, references, hits or [], CATALOG)


def test_unsafe_questions_are_refused_even_with_domain_words() -> None:
    decision = decide_scope(Scope.UNSAFE, strong_signal=True)
    assert not decision.allowed
    assert decision.reason == "unsafe"


def test_out_of_scope_is_refused_without_a_domain_signal() -> None:
    decision = decide_scope(Scope.OUT_OF_SCOPE, strong_signal=False)
    assert not decision.allowed
    assert decision.reason == "out_of_scope"


def test_a_strong_domain_signal_overrides_an_out_of_scope_verdict() -> None:
    decision = decide_scope(Scope.OUT_OF_SCOPE, strong_signal=True)
    assert decision.allowed
    assert decision.reason == "domain_signal"
    assert decide_scope(Scope.IN_SCOPE, strong_signal=False).allowed


def test_domain_signals_are_report_references_exact_terms_and_catalog_names() -> None:
    assert signal("Berapa daily cost DDR 32?")
    assert signal("When was BARAKUDA-1 spudded?")
    assert signal("Is it NPT?", [GlossaryHit(NPT, "alias")])
    assert not signal("is it npt?", [GlossaryHit(NPT, "alias", strong=False)])
    assert not signal("Siapa presiden Indonesia saat ini?")
