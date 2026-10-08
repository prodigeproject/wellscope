# ADR-0002: Visibility-aware, template-driven PDF parsing

- **Status:** Accepted · **Date:** 2026-10-08

## Context

Some reports carry text that is never rendered: white text on a white background and labels
painted over by later shapes. Plain extractors (poppler `pdftotext`, pypdf) interleave this text
with visible text character by character. White text is not always hidden either — section
headers are white on dark fills. Tables mix label-above-value cells, centred headers over wide
columns, rows that continue across pages, and narratives appended inside a table cell.

## Decision

1. **Visibility by painter's algorithm.** Walk layout objects in content-stream order; keep a
   character only if no later opaque filled shape covers it and its colour contrasts with the
   last fill beneath it.
2. **Geometry from rulings.** Column boundaries come from vertical ruling lines, rows from
   tolerance-based line clustering, and page bodies end at the detected footer.
3. **Form templates in YAML** describe signatures, sections, labels/aliases and tables.
4. **Lossless generic capture** keeps all visible key-value pairs, tables and page text.
5. **Invariants** (operation hours total 24; NPT hours match the header) guard the parser.

Library: **pdfplumber** (MIT) — exposes characters, colours, shapes and object order.

## Alternatives considered

- Colour-only filtering — removes visible white-on-dark headers.
- Raster "ink" check — keeps hidden text that overlaps visible text.
- Header-text column boundaries — misassign values (centred headers, left-shifted values).
- PyMuPDF — fast, but AGPL licensing; Docling/Unstructured — heavy ML dependencies;
  LLM extraction — cost, non-determinism, risk of invented numbers.

## Consequences

- (+) Clean, deterministic extraction in well under a second per page; no model cost at ingest.
- (+) Format variations are handled by templates; unknown forms still yield searchable text.
- (−) Clipping paths and transparency are approximated; a `visible_ratio` metric flags pages for
  review.

## Validation

Synthetic PDFs cover hidden, occluded and white-on-dark text; dataset tests assert both
invariants on the real reports.
