# Engineering Standards (v0.1)

These standards are the project "constitution". Every rule is enforced by a tool or a test where
possible; the **Enforced by** column says how. A deviation requires an ADR (`docs/adr/`) or an
entry in `docs/TECH_DEBT.md`.

## 1. Architecture and structure

| Rule | Enforced by |
|---|---|
| `src/` layout, single package `wellscope`. | packaging |
| Ports and adapters: `domain` is pure (no I/O, no framework imports); `ingestion`, `retrieval` and `qa` are application services; `storage`, `llm`, `api` and `web` are adapters. | `tests/architecture/test_import_rules.py` |
| One responsibility per module, named after the concept it owns. No `utils.py`/`helpers.py` dumping grounds. | review |
| Configuration is read only through `wellscope.config.Settings`; no `os.environ` elsewhere. | review + grep test |
| JSON is the source of truth; the SQLite database is a rebuildable projection. | design |

## 2. Size budget (LOC)

| Rule | Limit | Enforced by |
|---|---|---|
| Lines per module (including docstrings) | ≤ 300 | `tests/architecture/test_source_size.py` |
| Statements per function | ≤ 30 (≈ 40 lines) | ruff `PLR0915` |
| Cyclomatic complexity | ≤ 10 | ruff `C901` |
| Branches per function | ≤ 12 | ruff `PLR0912` |
| Arguments per function | ≤ 6 | ruff `PLR0913` |
| Line length | ≤ 100 | ruff `E501` |

## 3. Coding conventions

- Full type hints; `mypy --strict` must pass. No `Any` at module boundaries.
- Immutable data by default: `@dataclass(frozen=True, slots=True)` for internal values, Pydantic
  models (`frozen=True`, `extra="forbid"`) at I/O boundaries.
- Parsing and normalisation are pure functions; I/O and network calls live at the edges.
- No magic numbers or strings: use named constants, form templates (`*.yaml`) or settings.
- Logging through `logging` with structured fields; `print` is reserved for CLI presentation.
- Comments explain *why*, not *what*. Every module starts with a one-to-three-line docstring;
  public functions and classes have Google-style docstrings when the name alone is not enough.

## 4. Error handling

- Raise specific exceptions from the `wellscope.errors` hierarchy; never use a bare `except`.
- A failure is either handled with a reason code (and logged) or propagated; never swallowed.
- Clients receive a generic message plus a `request_id`; stack traces and paths stay in logs.

## 5. Security

| Rule | Enforced by |
|---|---|
| Secrets come from environment/`.env` only, typed as `SecretStr`, never logged or returned. | review, log redaction test |
| No datasets, parsed output, databases, `.env` or keys in git. | `.gitignore`, pre-commit key hook, gitleaks (CI) |
| SQL is always parameterised; FTS queries are escaped. | review, unit tests |
| No `eval`, `exec`, `pickle`, `shell=True`. | ruff `S` rules |
| LLM output and document text are untrusted: rendered through a sanitiser, never `innerHTML` raw. | XSS unit tests, CSP |
| Dependencies are locked and audited. | `uv.lock`, pip-audit, Dependabot |

## 6. Testing

- Test-driven for core logic (`domain`, `ingestion`, `retrieval`, `qa`): write the failing test
  first. Invariants (for example "operation hours total 24") are tests, not comments.
- Names describe behaviour: `test_<subject>_<behaviour>[_when_<condition>]`; Arrange-Act-Assert;
  one behaviour per test.
- Unit tests never touch the network: use `FakeChatModel` and `HashEmbedder`.
- Tests that need the real dataset are marked `@pytest.mark.dataset` and skip when it is absent.
- Coverage of core packages ≥ 85% (CI gate). No simulated or always-passing gates.

## 7. Documentation

- `README.md` is enough to install, configure, ingest and run on a clean machine.
- Significant decisions are ADRs (`docs/adr/`, MADR-lite). Specs live in `docs/specs/` and keep
  traceability (requirement → task → test).
- JSON output contracts are generated from Pydantic models into `docs/schemas/` and checked by a
  contract test.
- Diagrams use Mermaid. At most twelve documents under `docs/`; each has one purpose.

## 8. Git and review

- Conventional Commits (`feat`, `fix`, `test`, `docs`, `refactor`, `chore`, `ci`); small commits.
- One branch per phase, merged through a pull request with green CI.
- Commits are authored as the project identity; no generated-by trailers.

## 9. Definition of Done

A change is done when its tests were written first and pass, ruff and mypy are clean, the size
budget holds, documentation and traceability are updated, and every new TODO has a
`docs/TECH_DEBT.md` entry.
