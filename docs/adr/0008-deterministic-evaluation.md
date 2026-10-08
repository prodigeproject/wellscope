# ADR-0008: Deterministic evaluation and golden-set governance

- **Status:** Accepted · **Date:** 2026-10-08

## Context

Accuracy is the main assessment criterion, and model choice must be justified with data. The
dataset and its parsed output must not be published, yet a golden question set naturally contains
facts from that dataset.

## Decision

- A golden set (YAML) of bilingual questions across categories: glossary, report facts,
  cross-document/temporal, data conflicts, missing data, out-of-scope and injection.
- Scoring is deterministic: required facts (format-insensitive numeric matching), expected cited
  documents, expected status, and exact match of canonical refusal text.
- Metrics: accuracy per category with Wilson 95% intervals, refusal precision/recall,
  false-refusal rate, citation validity, p50/p95 latency, tokens and cost per question.
- The real golden set lives in `evals/private/` (git-ignored). The repository contains the schema,
  a dummy example and aggregate results only.

## Alternatives considered

- LLM-as-judge as the primary metric — costly, noisy and itself fallible; used only as a secondary
  signal for narrative answers.
- Committing the full golden set — reproducible, but republishes dataset facts.

## Consequences

- (+) Repeatable, cheap evaluation; results can gate releases.
- (−) Reviewers cannot reproduce our exact score without the private set, but can run their own.

## Validation

`wellscope eval` produces `docs/EVALUATION.md` aggregates and gates the release decision.
