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

**Refinements made with evaluation evidence** (see `docs/EVALUATION.md`):

- The context budget is 24k tokens, so a collection of the sample's size is always read in full;
  at 16k, questions without a report reference fell back to search and missed facts.
- In full-context mode the best search matches are moved to the front of the report passages;
  questions spanning several reports had missed facts in the middle of a long context.
- Totals of the operations table are computed during rendering and given as their own passage,
  because the model mis-added hours.
- Every source carries its report's period, so a day is answered from the report that covers it.

Result: 97/97 on the golden set, p95 latency 4.4 s.
