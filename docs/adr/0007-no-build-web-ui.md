# ADR-0007: No-build web UI with server-side sanitised rendering

- **Status:** Accepted · **Date:** 2026-10-08

## Context

Reviewers must run the app from the README alone. Each extra prerequisite (Node, a bundler,
Docker) is a failure point. The UI must still look professional, be accessible and resist XSS from
model output and document text.

## Decision

- Static HTML, CSS and JavaScript ES modules served by FastAPI; no build step.
- A design-token system (CSS custom properties) with light and dark themes.
- Answers are rendered on the server: Markdown with raw HTML disabled, then an allow-list
  sanitiser (nh3); the browser inserts only sanitised fragments. Content Security Policy:
  `default-src 'self'`, no inline scripts, `frame-ancestors 'none'`.

## Alternatives considered

- React + Vite + TypeScript — richer ecosystem but needs Node and a build (or committed build
  output).
- HTMX + Jinja — close second; rich interactions still need custom JavaScript.
- Streamlit, Chainlit or Gradio — fastest, but generic look and limited control over CSP.

## Consequences

- (+) Python is the only prerequisite; rendering is unit-testable with XSS payloads.
- (−) More hand-written UI code; mitigated by small modules and JSDoc type annotations.

## Validation

API tests for headers and sanitisation; accessibility checklist in `docs/UAT.md`.
