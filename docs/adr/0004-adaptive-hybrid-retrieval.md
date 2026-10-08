# ADR-0004: Adaptive context assembly with hybrid retrieval

- **Status:** Accepted · **Date:** 2026-10-08

## Context

Most questions target one report ("in report 32…", "on 9 August…"); others are general ("which
rig?") or comparative ("how did depth change?"). Questions may be in Indonesian while documents
are in English, and many answers hinge on codes and numbers (`D18`, `12-1/4"`, `10.0 ppg`).

## Decision

1. Resolve report references (number, date by report period, "latest") to document ids.
2. If the resolved reports fit the token budget, include their **whole structured rendering**.
3. Otherwise run hybrid search — FTS5 BM25 over normalised text plus embedding similarity — fused
   with reciprocal rank fusion (k = 60), and add a catalog card summarising all reports.
4. Always include glossary matches for detected terms.

FTS5 tokenizer: `porter unicode61 remove_diacritics 2 tokenchars '.-/'`, so `17-1/2` and
`10.0ppg` stay whole while English words are stemmed. Index text is normalised (unit prefixes
split, trailing punctuation removed, unicode fractions expanded).

## Alternatives considered

- Top-k chunks only — misses facts spread across a report.
- BM25 only — fails on Indonesian questions and paraphrases.
- Vectors only — weak on codes and numbers.
- Cross-encoder or LLM rerankers — extra install weight or latency; kept as a tuning lever.

## Consequences

- (+) Per-report questions have no retrieval misses; general questions remain answerable.
- (+) If embeddings are unavailable, BM25 plus English query rewriting still works.
- (−) Resolver logic needs thorough tests (periods differ between report families).

## Validation

Retrieval and resolver unit tests; golden-set accuracy by category.
