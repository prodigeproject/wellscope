# Tasks — WellScope

Each task links to requirements (`_Req:_`) and is done when its tests pass (see
`docs/STANDARDS.md` §9). Checked boxes reflect the current state of `main`.

## P0 — Specification
- [x] 0.1 Engineering standards, requirements (EARS), design, tasks, ADRs. _Req: all_

## P1 — Scaffold and parsing
- [ ] 1.1 Project scaffold: packaging, lint/type/test tooling, pre-commit, CI, settings, logging,
      errors, CLI skeleton with `doctor`, architecture tests. _Req: NFR-2, NFR-4, SEC-1, SEC-6, FR-8_
- [ ] 1.2 Normalisation of numbers, units, fractions, dates and time ranges (property tests).
      _Req: FR-2.5_
- [ ] 1.3 Visibility filter (painter's algorithm) with synthetic PDF tests. _Req: FR-2.1_
- [ ] 1.4 Layout primitives: words, line clustering, rulings, columns, cells. _Req: FR-2.2, FR-2.3_
- [ ] 1.5 Glossary parser (separators, aliases, statuses, multiple senses). _Req: FR-3.1, FR-3.2_
- [ ] 1.6 Classifier and form templates. _Req: FR-1.2_
- [ ] 1.7 DDR parser incl. operations, next-day narrative and sections. _Req: FR-2.2, FR-2.4_
- [ ] 1.8 DGOS parser incl. summary grid, casing and formation tops. _Req: FR-2.3, FR-2.4_
- [ ] 1.9 Generic parser fallback. _Req: FR-2.4, FR-1.6_
- [ ] 1.10 Quality gate (invariants, cross-document conflicts). _Req: FR-2.6, FR-2.7_
- [ ] 1.11 Ingest pipeline, JSON store, manifest, schema export, contract test. _Req: FR-1.1–1.6_

## P2 — Storage, retrieval and question answering
- [ ] 2.1 SQLite projection with FTS5, chunks, atomic swap and index version. _Req: FR-1.4, FR-1.5_
- [ ] 2.2 Embeddings with content-hash cache; hybrid search with RRF. _Req: FR-4.1_
- [ ] 2.3 Report resolver (numbers, periods, latest) and glossary index. _Req: FR-4.3, FR-3.3, FR-3.4_
- [ ] 2.4 LLM ports, OpenAI adapter, fakes, versioned prompts. _Req: NFR-3, NFR-5_
- [ ] 2.5 Analyzer with deterministic extractors and follow-up rewrite. _Req: FR-4.7_
- [ ] 2.6 Scope policy and canonical messages. _Req: FR-5.1–5.4_
- [ ] 2.7 Context assembly (budget, nonce delimiters, escaping) and answerer. _Req: FR-4.1–4.6, SEC-2_
- [ ] 2.8 Verifier (citations, numbers, one regeneration). _Req: FR-6.1–6.3_
- [ ] 2.9 Safe HTML rendering and `wellscope ask`. _Req: SEC-3, FR-8.1_

## P3 — API and user interface
- [ ] 3.1 FastAPI app: security headers, CSP, error envelope, limits, rate limit. _Req: SEC-3–5, SEC-7_
- [ ] 3.2 Endpoints: chat (SSE), catalog, sources, glossary, health. _Req: FR-7.1, FR-7.2_
- [ ] 3.3 Design tokens and components (light/dark, accessible). _Req: FR-7.3, FR-7.4_

## P4 — Evaluation
- [ ] 4.1 Golden set format, runner, deterministic scoring, aggregate report. _Req: NFR-1, NFR-6, NFR-7_
- [ ] 4.2 Model comparison and tuning; model ADR updated with data. _Req: NFR-7_

## P5 — Hardening and documentation
- [ ] 5.1 Security review, dependency and secret scans, fixes. _Req: SEC-1–7_
- [ ] 5.2 README, PLANNING, RESOLUTION, UAT, GO_NO_GO, SECURITY, TECH_DEBT, DATA_QUALITY. _Req: brief_
- [ ] 5.3 UAT runner and fresh-clone verification. _Req: NFR-2_
