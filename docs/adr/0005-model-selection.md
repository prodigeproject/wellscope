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

Golden set of 97 questions, answer model varied with `WELLSCOPE_CHAT_MODEL`
(`docs/EVALUATION.md`): `gpt-5.4-mini` 95/97 at p95 4.5 s and about USD 0.010 per question;
`gpt-4.1-mini` 92/97 at 6.8 s and USD 0.005; `gpt-5.4-nano` 91/97 at 4.6 s and USD 0.003. All three
refused every out-of-scope question with no false refusal. The defaults are confirmed; the
final pipeline scores 97/97 with them.
