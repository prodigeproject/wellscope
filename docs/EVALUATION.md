# Evaluation

How answer quality is measured, the results, and how the default models were chosen.

## Method

`wellscope eval` sends every question of a golden set through the same pipeline the web app
uses (analysis, scope policy, retrieval, answer, verification) and scores each answer
deterministically; no model grades another model.

| Check | Rule |
|---|---|
| Status | The answer status must match: `answered`, `not_found`, `out_of_scope`, `refused` (either refusal) or `grounded` (answered *or* not found; used where the honest answer is that a field is blank). |
| Facts | Every `must_include` value must appear in the answer or its caveats. Numbers match in any notation (`2,423.11` = `2.423,11`), dates in any format (`29/07/2026` = `29 Juli 2026` = `2026-07-29`), text ignoring case, dashes and spacing. `must_include_any` needs one value of each group. |
| Citations | Every `must_cite_docs` document must be among the cited sources. |

Reported metrics: accuracy overall and per category with 95% Wilson intervals, refusal recall
(questions that should be refused, and were) and precision (refusals that were right), false
refusal rate (answerable questions that were refused), the share of answers whose citations
and figures passed the verifier, latency p50/p95/max and mean tokens. The aggregate report
holds no answer text; answers are written only to `evals/private/runs/` for debugging.

## Golden set

97 questions, 51 in Indonesian and 46 in English, written from a manual reading of the PDFs
before the pipeline was built and checked again against the parsed JSON:

| Category | Questions | What it exercises |
|---|---|---|
| glossary | 23 | expansions, aliases, multiple senses, entries the glossary marks unknown or to be confirmed, reverse lookup, typos in the source, terms that are not in the glossary |
| ddr_fact | 26 | header fields, costs, depths, narratives, the operations table, next-day entries, BHA, mud, safety, weather, personnel, totals of the operations table |
| dgos_fact | 16 | well data, progress grid, casing and shoe depths, formation tops, remarks, location, conditional fields |
| cross | 9 | comparisons, trends, "latest", a day covered by a report dated the next day, a follow-up question |
| conflict | 4 | values that differ between reports or are illogical; both values must be given |
| not_found | 5 | dates and reports that do not exist, fields that are blank |
| out_of_scope | 12 | general knowledge, prices, advice, coding, greetings, a prompt-extraction attempt, boundary questions |
| injection | 2 | instructions embedded in the question |

The set contains facts from the dataset and stays in `evals/private/` (gitignored);
[`evals/golden.example.yaml`](../evals/golden.example.yaml) documents the format with dummy data.
An injection planted inside a PDF is tested separately (see [UAT.md](UAT.md), UAT-07).

## Results (default models)

`gpt-5.4-mini` for answers, `gpt-5.4-nano` for analysis, `text-embedding-3-small` for
embeddings; final pipeline (commit `91814f8`).

| Category | Passed | Rate | 95% CI |
|---|---|---|---|
| conflict | 4/4 | 100% | 51–100% |
| cross | 9/9 | 100% | 70–100% |
| ddr_fact | 26/26 | 100% | 87–100% |
| dgos_fact | 16/16 | 100% | 81–100% |
| glossary | 23/23 | 100% | 86–100% |
| injection | 2/2 | 100% | 34–100% |
| not_found | 5/5 | 100% | 57–100% |
| out_of_scope | 12/12 | 100% | 76–100% |
| **Overall** | **97/97** | **100%** | **96–100%** |

| Metric | Value |
|---|---|
| Refusal recall / precision | 100% / 100% |
| False refusal rate | 0% |
| Answers with verified citations and figures | 100% |
| Latency p50 / p95 / max | 2.9 s / 4.4 s / 10.0 s (limit in the brief: 3 minutes) |
| Tokens per question (mean) | 13,433 in, 167 out |
| Cost per question (mean) | about USD 0.010 at list prices (USD 0.75 / 4.50 per million input / output tokens for `gpt-5.4-mini`, 0.20 / 1.25 for `gpt-5.4-nano`) |

Refusals are fast (about 1.1 s median) because an out-of-scope question never reaches the
answer model.

**How the result was reached.** The first full run scored 92/97. Each failure was traced to a
cause and fixed in the pipeline, never in the golden set, except where the expectation itself
was too narrow (two items accepted an equally correct reading of the source):

| Run | Score | Fixed after the run |
|---|---|---|
| 1 | 92/97 | Analyzer refused a question naming a platform in the reports; a date range came back as two specific dates; unconstrained questions were searched instead of read in full; the BHA number was not parsed. |
| 2 | 96/97 | Scorer ignored caveats, where a conflict is stated. |
| 3 | 96/97 | A trend question skipped one report and subtracted values in different units (prompt rule). |
| 4 | 95/97 | A multi-row table header was misaligned with its data, giving a wrong shoe depth. |
| 5 | 94/97 | Relevant passages lost in the middle of a long context; a question about content was classed as a catalog question; a glossary entry without expansion was shown as "meaning unknown". |
| 6 | **97/97** | — |

Language models are not deterministic even at temperature 0: across runs on intermediate
versions, the same pipeline scored within about two questions of each other. The remaining
risk is concentrated in questions that aggregate across several reports.

## Model comparison

Same golden set, answer model changed through `WELLSCOPE_CHAT_MODEL` (analysis stays on
`gpt-5.4-nano`). These three runs used the pipeline as of run 4 above, before the table-header
and passage-ordering fixes, so they compare models, not pipeline versions.

| Answer model | Accuracy | p95 latency | Verified answers | Cost per question |
|---|---|---|---|---|
| `gpt-5.4-mini` (default) | 95/97 (97.9%) | 4.5 s | 100% | ~USD 0.010 |
| `gpt-4.1-mini` | 92/97 (94.8%) | 6.8 s | 100% | ~USD 0.005 |
| `gpt-5.4-nano` | 91/97 (93.8%) | 4.6 s | 98.7% | ~USD 0.003 |

All three refused every out-of-scope question and none refused an answerable one. The smaller
models mostly lost points on multi-report questions and long narratives. `gpt-5.4-mini` stays the
default; `gpt-4.1-mini` is the documented fallback for keys without the `gpt-5.4` family and
remains above 90%.

## Reproducing

```bash
uv run wellscope eval --set evals/private/golden.yaml
```

Options: `--only D01 --only X05` to run single items, `--workers` (default 4),
`--reports <folder>`. A full run takes about 75 seconds and costs about one US dollar at the list
prices above.
