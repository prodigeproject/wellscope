# ADR-0005: Model selection driven by evaluation

- **Status:** Accepted (defaults confirmed by the evaluation in `docs/EVALUATION.md`) ·
  **Date:** 2026-10-08

## Context

Reviewers run the app with their own OpenAI key, so model access may differ. A latency probe
(one full report as context) measured roughly 2 s for `gpt-5.4-mini`/`gpt-5.4-nano`, 4–6 s for
`gpt-4.1`/`gpt-4.1-mini` and 4 s for `gpt-5.5`; all except `gpt-5-mini` accepted `temperature=0`.

## Decision

- Answer model: `gpt-5.4-mini` (reasoning effort `none`, temperature 0).
- Analysis model: `gpt-5.4-nano`.
- Embeddings: `text-embedding-3-small`.
- All three are configurable in `.env`; `gpt-4.1-mini` is the documented fallback and
  `wellscope doctor` checks access.
- Defaults are confirmed or changed only with evaluation data (accuracy, p95 latency, cost).

## Alternatives considered

- `gpt-4.1-mini` everywhere — broadly available and cheapest per token, but slower.
- `gpt-5.5` for answers — strongest on hard raw-text questions, about six times the cost.
- One model for every stage — simpler, but analysis would pay answer-model prices.

## Consequences

- (+) Fast and inexpensive with structured context; switching models is configuration only.
- (−) Newer models may be missing on some keys; mitigated by the fallback and `doctor`.

## Validation

`wellscope eval --models …` comparison table in `docs/EVALUATION.md`.
