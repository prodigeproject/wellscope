# ADR-0009: Code decides the facts, the model writes the sentence

- **Status:** Accepted · **Date:** 2026-10-09

## Context

Language models are not deterministic, even at temperature 0: across full evaluation runs the
same pipeline failed different questions each time (two of 97 per run). Each time the right
sources were in the context. The model was what varied:

- It reworded a question ("what drill" became "what drilling").
- It picked one of two conflicting values and explained the other away.
- It summarised an operation without the detail asked about.

An answer that is right only most of the time is not good enough for well data.

## Decision

Every step whose outcome can be computed is computed in code from the parsed JSON. The model
only chooses which retrieved facts answer the question and writes them as sentences. Each layer
narrows what the model can get wrong:

| Layer | Deterministic step | What it removes from the model |
|---|---|---|
| Parsing | Template parsing of every field, table and operation into JSON; quality checks | Reading PDFs |
| Question | Report numbers, dates, periods and "latest" taken from the question by rules, overriding the model; a question without a conversation is never reworded | Misreading which report or day is meant |
| Retrieval | Report resolver by number, type, date and period; whole reports when they fit | Choosing which report to read |
| Facts | Operation totals computed; cross-report conflicts detected at ingest; abbreviated labels given their everyday name | Arithmetic and recognising synonyms |
| Answer | Conflict caveats listing every value, written from the conflict records | Deciding which conflicting value is "right" |
| Check | Verifier: every figure, date and time must come from the cited sources; one retry, then a visible label; an uncited answer is not shown | Inventing or mis-copying figures |
| Scope | Canonical refusal and not-found texts; a domain signal from the glossary and the reports overrides a wrong refusal | Inconsistent refusals |

## Alternatives considered

- **Bigger model.** It narrows the variance but does not remove it, and costs about six times
  as much (ADR-0005).
- **Self-consistency.** Ask several times and take the majority. It costs several times as
  much and is still probabilistic.
- **Answer cache.** The same question gets the same answer. It gives consistency, but a wrong
  first answer is then repeated, and question text would be stored on disk. Kept as an option
  for a multi-user deployment.
- **Template answers only.** Fully deterministic, but cannot answer free-form questions such
  as "what happened between 16:15 and 19:00?".

## Consequences

- (+) The facts in an answer no longer depend on the model: the numbers are checked, every
  conflict is stated, and refusals use fixed texts. What still varies between runs is the
  wording, and which details a summary keeps.
- (+) Each new failure class is fixed once, in code, with a test, instead of by tuning prompts.
- (−) More code paths to maintain; each one is covered by unit tests.

## Validation

Golden set (`docs/EVALUATION.md`):

- Failures traced to the model (D13, X05, C01) became deterministic fixes.
- Each fix was re-run three times on the affected items, all passing.
- A full run confirms the whole set.
