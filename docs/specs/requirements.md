# Requirements — WellScope

**Status:** approved v1.0 · **Format:** EARS (`WHEN … THE <component> SHALL …`, `IF … THEN …`,
`WHILE …`) · **Source:** technical-test brief (traced in §5).

WellScope is a chat application that answers questions **only** from daily well reports (Daily
Drilling Report, DDR; Daily Geological Operations Summary, DGOS) and an Oil & Gas glossary.

## 1. Components

| Name | Role |
|---|---|
| Ingestor | Discovers, classifies and parses source files; writes JSON and the database |
| PdfParser | Extracts visible text, layout, key-value pairs and tables from PDF reports |
| GlossaryParser | Converts the glossary DOCX into structured entries |
| QualityGate | Validates parsed documents with domain invariants and cross-document checks |
| Retriever | Resolves report references and retrieves glossary entries and document context |
| Analyzer | Understands a question (scope, intent, language, filters) |
| ScopePolicy | Decides whether to answer, refuse, or report missing information |
| Answerer | Produces a cited answer from the retrieved context |
| Verifier | Checks citations and numbers before an answer is shown |
| ChatAPI / WebUI / CLI | Delivery: HTTP + SSE API, browser UI, command line |

## 2. Functional requirements

### FR-1 Ingestion
*As a reviewer, I want one command to parse all documents, so that their content becomes
answerable.*

1. WHEN `wellscope ingest` runs, THE Ingestor SHALL discover PDF and DOCX files recursively under
   the configured data directory, independent of folder and file names.
2. WHEN a file is discovered, THE Ingestor SHALL classify it by content signature as `DDR`,
   `DGOS`, `GLOSSARY` or `GENERIC`.
3. THE Ingestor SHALL write one JSON document per report, a glossary JSON, a manifest and a
   quality report into the configured output directory.
4. THE Ingestor SHALL build the SQLite database only from the JSON output and swap it atomically.
5. WHEN a new file of a similar format is added and ingest is re-run, THE system SHALL make its
   content answerable without code changes and without restarting the server.
6. IF one file fails to parse, THEN THE Ingestor SHALL quarantine it with a reason code and
   continue with the remaining files.

### FR-2 Report parsing
1. THE PdfParser SHALL ignore text that is invisible when the page is rendered (same colour as
   its background, or painted over by a later shape).
2. THE PdfParser SHALL extract DDR header fields, depth/days/costs, status narratives, the
   operations table including rows continued across pages, and the next-day narrative appended to
   the last operation.
3. THE PdfParser SHALL extract DGOS well data, operation update, progress summary, location, rig
   information, remarks, casing and shoe depths, and formation tops.
4. THE PdfParser SHALL keep every visible key-value pair, table and page text in a generic part of
   the JSON, including content with no typed field.
5. THE PdfParser SHALL store the raw source string next to every normalised value.
6. WHEN a DDR is parsed, THE QualityGate SHALL check that operation hours total 24 and that
   NPT-flagged hours equal the reported daily NPT, and SHALL record any mismatch as a finding.
7. THE QualityGate SHALL record cross-document conflicts (for example, different spud dates)
   without altering source values.

### FR-3 Glossary knowledge base
1. THE GlossaryParser SHALL turn every glossary row into an entry with term, aliases, expansion,
   description and status (`confirmed`, `to_be_confirmed`, `unknown`).
2. THE GlossaryParser SHALL skip alphabetical separator rows.
3. WHEN a term has several meanings, THE system SHALL present all of them.
4. WHEN a user asks for a term or for the abbreviation of a phrase, THE Retriever SHALL match
   exact terms, aliases, near spellings and expansions.

### FR-4 Question answering
1. WHEN a user submits an in-scope question, THE system SHALL answer only from ingested documents
   and the glossary.
2. THE Answerer SHALL cite the supporting sources (document, page, section) of every answer.
3. WHEN a question references a report number, a date or "the latest" report, THE Retriever SHALL
   resolve it against report periods (DDR: 00:00 to 06:00 next day; DGOS: 06:00 to 06:00).
4. THE system SHALL answer in the language of the question (Indonesian or English) and quote
   numbers, units and codes exactly as written in the source.
5. WHEN sources conflict, THE Answerer SHALL report every value with its citation.
6. WHEN a field exists but is empty, THE Answerer SHALL state that it is not recorded.
7. WHEN a question is a follow-up, THE Analyzer SHALL rewrite it as a standalone question using at
   most the last three turns.

### FR-5 Scope and refusal
1. IF a question is not about the ingested documents or glossary, THEN THE ScopePolicy SHALL
   return the canonical `OUT_OF_SCOPE` message in the language of the question.
2. IF a question is about supported topics but the information is absent, THEN THE system SHALL
   return the canonical `NOT_FOUND` message followed by the list of available reports.
3. THE canonical messages SHALL be fixed strings that direct the user back to supported topics.
4. THE system SHALL NOT answer from general knowledge, including Oil & Gas knowledge that is not
   in the data.

### FR-6 Verification
1. THE Verifier SHALL reject citations that do not refer to a provided source.
2. THE Verifier SHALL reject numbers in an answer that are absent from the cited sources after
   format normalisation.
3. IF verification fails, THEN THE system SHALL regenerate once with feedback and, if it fails
   again, SHALL mark the answer as unverified.

### FR-7 User interface
1. THE WebUI SHALL show the document catalog, the chat thread and the sources of a selected answer.
2. WHILE an answer is being produced, THE WebUI SHALL display the current processing stage.
3. THE WebUI SHALL show an explicit status per answer: answered, not found, out of scope,
   unverified or error.
4. THE WebUI SHALL be operable by keyboard alone, meet WCAG 2.1 AA contrast and render without
   horizontal scrolling at 375 px width.

### FR-8 Command line
1. THE CLI SHALL provide `ingest`, `serve`, `ask`, `eval`, `doctor` and `schema` commands.
   (A `uat` command was planned and deferred: acceptance is documented in `docs/UAT.md`, TD-04.)
2. WHEN `doctor` runs, THE CLI SHALL report configuration, model access, data directories and
   index freshness without printing secrets.

## 3. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Latency: p95 ≤ 20 s and maximum ≤ 60 s per answer (brief limit: 180 s). |
| NFR-2 | Portability: runs on Windows, macOS and Linux with Python ≥ 3.11 by following only the README; Node and Docker are not required. |
| NFR-3 | Determinism: identical inputs produce identical ingest output; LLM calls use temperature 0 where the model supports it. |
| NFR-4 | Maintainability: limits of `docs/STANDARDS.md` §2; `mypy --strict`; ≥ 85% coverage of core packages. |
| NFR-5 | Observability: every request has a request id and a trace of stage timings, token usage and estimated cost. |
| NFR-6 | Cost: ≤ USD 0.02 per question on average. |
| NFR-7 | Accuracy on the golden set: ≥ 90% factual, ≥ 95% glossary, 100% out-of-scope refusal, ≤ 5% false refusal. |

## 4. Security requirements

| ID | Requirement |
|---|---|
| SEC-1 | THE system SHALL read the API key only from the environment or `.env`, and SHALL never log or return it. The repository SHALL contain no secrets, datasets or parsed outputs. |
| SEC-2 | THE Answerer SHALL treat document text as data; instructions inside documents or questions SHALL NOT change system behaviour. |
| SEC-3 | THE WebUI SHALL render only sanitised HTML, and the Content Security Policy SHALL forbid inline scripts. |
| SEC-4 | THE ChatAPI SHALL limit question length (1,000 characters), request rate per client, model output size and call duration. |
| SEC-5 | THE query path SHALL open the database read-only; THE ChatAPI SHALL expose no upload or ingest endpoint and SHALL bind to 127.0.0.1 by default. |
| SEC-6 | Dependencies SHALL be locked; CI SHALL scan for vulnerable dependencies and leaked secrets. |
| SEC-7 | Errors returned to clients SHALL NOT contain stack traces or internal paths and SHALL include a request id. |

## 5. Traceability to the brief

| Brief item | Covered by |
|---|---|
| Document-grounded chat with a UI | FR-4, FR-7 |
| Consistent out-of-scope refusal that redirects the user | FR-5 |
| Glossary knowledge base | FR-3 |
| Parsing code for PDF and DOCX into structured data | FR-1, FR-2, FR-3 |
| JSON storage | FR-1.3 |
| Re-runnable with one command for new PDFs; immediately answerable | FR-1.5 |
| Testing with other PDFs of a similar format | FR-1.2, FR-2.4, FR-1.6 |
| README documents the JSON structure with dummy data | `README.md` |
| Run from README only; key in `.env` with `.env.example` | NFR-2, SEC-1 |
| Dataset and JSON not uploaded; README explains locations | SEC-1, `README.md` |
| Response time ≤ 3 minutes | NFR-1 |
| Planning and Resolution documentation | `docs/PLANNING.md`, `docs/RESOLUTION.md` |
| Nice to have: real database | FR-1.4 (SQLite) |

## 6. Out of scope (v1)

Authentication and multi-tenancy, uploading files through the UI, OCR for scanned PDFs, PostgreSQL,
agentic tool use and text-to-SQL. Each is discussed as future work in `docs/RESOLUTION.md`.
