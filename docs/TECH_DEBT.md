# Technical debt register

Known shortcuts and gaps, their impact and likelihood (high, medium, low), and the plan to pay
them down. Reviewed at each release.

| ID | Debt | Impact | Likelihood | Plan |
|---|---|---|---|---|
| TD-01 | GitHub Actions does not start on the private repository, so CI (Linux and Windows matrix, gitleaks, CodeQL) has not run; the same checks run locally and in pre-commit | Medium | High until fixed | Enable Actions for the account or make the repository public; fix anything the Linux jobs find |
| TD-02 | `serve` and `doctor --online` are exercised only by hand and acceptance tests (CLI line coverage 65%; `ingest`, `ask`, `schema` and `eval` run in tests) | Low | Low | Start the app factory under a test server and fake the model checks |
| TD-03 | No Playwright end-to-end tests for the web app; checked by hand (UAT-09) | Medium | Medium | Add a browser test: ask, see stages, open a citation, toggle the theme, mobile drawer |
| TD-04 | The automated `wellscope uat` runner from the plan was not built; acceptance was run by hand and by tests | Low | Low | Script UAT-01/02/03/11 into one command that writes a dated report |
| TD-05 | Templates are hand-written YAML; a new report family needs a new template | Medium | Medium | Template wizard that proposes labels from one sample; model-assisted mapping reviewed against page text |
| TD-06 | Report periods are rules per family (DDR 00:00 to 06:00 next day, DGOS 06:00 to 06:00); generic PDFs get none, so date questions about them rely on the report date only | Medium | Medium | Move period rules into the templates; detect explicit "period" fields in generic documents |
| TD-07 | Token budgets use an estimate (3.5 characters per token) instead of the model's tokenizer | Low | Low | Use `tiktoken` when budgets get tight |
| TD-08 | Vectors are compared in memory with numpy; fine for thousands of passages | Low | Low | `sqlite-vec` or a vector index when the corpus reaches hundreds of thousands of passages |
| TD-09 | The embedding cache is never pruned | Low | Low | Prune entries unused for N ingests |
| TD-10 | When the browser disconnects, the pipeline stops at its next stage, but a model call already in flight completes (and is paid for) | Low | Medium | Stream the answer call and abort it on disconnect |
| TD-11 | The rate limiter is per process and keys on the client address | Medium if exposed | Low locally | Gateway rate limiting and authentication for any shared deployment |
| TD-12 | Every in-scope question makes two model calls; obvious glossary questions could skip the analysis call | Low | High | Deterministic fast path for "what does X mean" with an exact glossary hit |
| TD-13 | A calculated figure passes when it equals a sum, difference, running total or percentage of cited figures in the same or the previous sentence; an invented value that happens to equal such a result would pass | Low | Low | Ask the model to mark calculated values explicitly and check only those |
| TD-14 | Prompts were edited in place as `v1` during development | Low | Low | From the first release on, any prompt change gets a new version file and must pass the evaluation |
| TD-15 | The golden set holds dataset facts, so reviewers cannot re-run it exactly | Low | High | Publish a synthetic golden set built on generated reports |
| TD-16 | No OCR: scanned PDFs are quarantined | Medium for old archives | Low for this data | Optional OCR step with confidence scores, reviewed like other low-confidence parses |
