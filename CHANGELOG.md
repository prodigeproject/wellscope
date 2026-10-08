# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-10-09

### Added
- `wellscope ingest`: discovery and content-based classification of PDF and DOCX files;
  visibility-aware, template-driven parsing of DDR and DGOS reports (fields with raw text,
  operations, next-day narrative, remarks, tables with flattened column names, sections, page
  text); generic fallback for other PDFs; glossary parser; quality gate; JSON outputs with
  published JSON Schemas; SQLite index with FTS5 and embeddings, rebuilt atomically; embedding
  cache.
- Question answering: analysis with deterministic report references, scope policy with
  canonical refusals in Indonesian and English, report resolution by number, type, date, period
  and recency, glossary matching, hybrid search, budgeted nonce-delimited context, grounded
  answers with citations, verification of citations, figures, times and dates, computed
  operation totals, sanitised HTML.
- Web app and API: streamed answers with progress, sources panel, full-report viewer, glossary
  browser, light and dark themes; security headers and CSP, request limits, rate limiting,
  trusted hosts, no upload endpoint.
- `wellscope serve`, `ask`, `eval`, `doctor --online` and `schema` commands.
- Evaluation harness with a deterministic scorer and aggregate reports.
- Documentation: README, planning, resolution, evaluation, acceptance tests, release decision,
  security, technical debt, data quality, specification and ADRs.

### Fixed during evaluation
- Values clipped at cell borders are restored; BHA numbers in section titles are read; table
  headers spanning rows or columns no longer shift values by one column.
- Day questions use report periods; totals come from computed passages; a period from the
  analysis no longer becomes two specific dates; names written in the reports count as a domain
  signal; the best passages lead a long context.
