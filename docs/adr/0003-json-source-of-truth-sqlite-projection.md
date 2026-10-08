# ADR-0003: JSON as source of truth, SQLite as projection

- **Status:** Accepted · **Date:** 2026-10-08

## Context

The brief requires JSON output and suggests a real database as a nice-to-have, provided reviewers
need no extra setup. Retrieval needs keyword search, vector similarity and structured filters.

## Decision

- Parsed documents are written as versioned JSON (`schema_version`, source hash, parser version).
- A SQLite database (standard library) is built **only** from that JSON: typed tables, an FTS5
  index for BM25 and float32 embedding blobs searched with NumPy.
- The database is written to a temporary file and swapped atomically; the server checks the index
  version per request, so new data is answerable without a restart.
- The query path opens the database read-only.

## Alternatives considered

- JSON only — no indexing; the nice-to-have would be missed.
- PostgreSQL + pgvector via docker-compose — adds Docker as a prerequisite and failure point.
- DuckDB or a vector database — no benefit over SQLite at this scale; extra dependencies.

## Consequences

- (+) Zero setup; a deleted database is rebuilt with one command.
- (−) Brute-force vector search is linear; adequate up to roughly 10^5 chunks, after which
  `sqlite-vec` or pgvector would be adopted.

## Validation

Integration tests rebuild the database from JSON and compare query results.
