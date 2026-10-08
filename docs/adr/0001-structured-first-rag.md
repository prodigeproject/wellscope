# ADR-0001: Structured-first retrieval-augmented generation

- **Status:** Accepted · **Date:** 2026-10-08

## Context

The reports are dense forms: key-value grids, multi-page tables and narratives. A spike fed the
raw text of one daily drilling report (≈ 6.6k tokens) to six OpenAI models and asked which
operations were non-productive. All six read the header facts correctly, but five of six attached
the NPT flag to the wrong table row; only the most expensive model answered correctly. The
geological summaries additionally contain a hidden text layer that corrupts plain text extraction.

## Decision

Parse every report into typed, validated structures first (JSON), then answer over a structured
rendering of those structures. The LLM explains and phrases; it does not reconstruct tables.

## Alternatives considered

- **Long context with raw text** — rejected: corrupted text and lost table semantics; cost grows
  linearly with the corpus.
- **Classic chunk-and-embed RAG** — rejected: fixed-size chunks split table rows; embeddings are
  weak on codes and numbers.
- **Agentic tool calling / text-to-SQL** — deferred: more latency, non-determinism and attack
  surface than the brief requires; listed as future work.
- **Hosted file search** — rejected: no control over hidden text and tables; data leaves our
  boundary; does not satisfy the parsing deliverable.

## Consequences

- (+) Small, fast models answer table questions reliably; every answer can cite a section or row.
- (+) The same structures feed JSON output, the database, retrieval and validation.
- (−) Parsing effort is front-loaded; unknown form families fall back to generic capture.

## Validation

Golden-set accuracy per category (`docs/EVALUATION.md`); parser invariants in the test suite.
