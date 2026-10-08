# ADR-0006: Layered scope policy with canonical messages

- **Status:** Accepted · **Date:** 2026-10-08

## Context

Out-of-scope questions must be refused with a consistent message that redirects users to supported
topics. Some cases are subtle: "weather at the rig on 19 July" is in scope, "weather in Jakarta
today" is not; "capital of Malaysia" is out of scope although Malaysia appears in the data. General
Oil & Gas knowledge absent from the documents must not be used.

## Decision

1. The analyzer classifies scope (`in_scope`, `out_of_scope`, `unsafe`) using a written policy
   with examples.
2. A pure decision table combines that verdict with deterministic signals (exact glossary term,
   explicit report reference, catalog entity). A strong signal overrides an `out_of_scope`
   verdict; `unsafe` always refuses.
3. The answer stage may still return `not_found` when the sources lack the answer.
4. User-facing refusals are **two fixed messages per language**: `OUT_OF_SCOPE` (topic outside the
   data) and `NOT_FOUND` (supported topic, information absent, followed by a deterministic list of
   available reports). Both name supported topics with examples.

## Alternatives considered

- Embedding-similarity threshold — thresholds do not transfer between corpora and normalised
  scores hide out-of-scope questions.
- Keyword allow-list — many false refusals, fails on Indonesian paraphrases.
- Letting the answer model decide in one prompt — wording drifts; not measurable as "consistent".

## Consequences

- (+) Refusal text is exactly testable; reason codes are logged and shown as UI badges.
- (−) One additional small-model call per question (≈ 1–2 s).

## Validation

Policy unit tests; golden-set refusal precision/recall and false-refusal rate.
