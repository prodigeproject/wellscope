# Resolution

Obstacles met while building WellScope, their root causes, how they were solved and the
evidence that the fix works; then the known limitations and the next improvements. Examples
use generic values; the dataset itself is not reproduced here.

## 1. Reading the PDFs

| # | Obstacle | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 1 | Plain text extraction of the geological summary produced unreadable strings and duplicated fields. | The PDF holds a hidden text layer: white text on white, and labels later painted over by filled shapes. Extractors ignore colour and drawing order. | A visibility filter that replays the content stream in order (painter's algorithm): a character is dropped when a later fill covers it or when it does not contrast with the fill beneath it. White text on a coloured header stays. | `tests/unit/ingestion/test_visibility.py` (synthetic PDFs for each case); the visible ratio of every page is stored and checked by the quality gate. |
| 2 | Operation descriptions landed in the wrong column. | Column positions were first taken from header text, but values sit left of their headers and one header is centred over a wide column. | Column bounds come from the table's vertical ruling lines. | Operation rows of every DDR total exactly 24.00 h (quality check `operations.hours_total`). |
| 3 | Rows went missing (a day totalled 20 or 23.75 hours). | Grouping words into lines by rounded positions split a row at the rounding boundary; a fixed bottom margin cut the row nearest the footer. | Tolerance-based line clustering; the table's bottom comes from the footer position. | The 24-hour invariant now holds on all reports; it was the check that exposed the bug. |
| 4 | Questions about 03:00 the next day failed. | The DDR carries the next day's 00:00–06:00 narrative inside the last operation cell, after a separator line. | The narrative is split into its own `next_day` entries; report periods run from 00:00 to 06:00 the next day (DDR) and from 06:00 the previous day (DGOS). | `tests/unit/ingestion/test_next_day.py`; golden questions about early-morning activity pass. |
| 5 | Neighbouring values glued together (`…REAMER1`) or were cut (`Fire and Aba`). | Long values overflow their cell in the file but are clipped by the cell border on the page, so the overflow lands next to the neighbour's text. | Spilled characters are removed from the neighbour and re-attached to the value they continue; words are split at a border only when their glyphs do not touch. | `tests/unit/ingestion/test_layout.py`; thirteen truncated values recovered in the sample data (company names, card categories, a drill type). |
| 6 | Key-value pairs paired the wrong label and value. | Some forms put the label above the value, others to its left; some sections hold several pairs on one line; a value can wrap to the next line. | Each word belongs to the smallest table cell around it; known labels from the template; continuation lines accepted only when aligned with the value. | `tests/unit/ingestion/test_kv.py`; every typed field of the sample reports checked against the PDFs. |
| 7 | A table header was read one column off, giving a wrong shoe depth. | Multi-row headers and header cells spanning several columns (a depth interval over its start and end) have fewer cells than the data rows. | Each column is named from the header cells above it, by geometry: `Prognosis Depth m TVDSS`, `DEPTH INTERVAL [1/2]`. Captions above a header are skipped. | `tests/unit/ingestion/test_grid.py`; the golden question about the shoe depth passes. |
| 8 | The BHA number could not be tied to its data. | It sits in the section title (`BHA no.# 8`), which no field captured. | Labels ending in `#` are self-delimited. | `tests/unit/ingestion/test_kv.py`. |
| 9 | Searching for `MDDF` or `17-1/2` missed passages. | Units glued to numbers (`2,349 mMDDF.`), trailing punctuation, Unicode fractions. | Text is normalised the same way for the index and for questions; the FTS5 tokenizer keeps `.`, `-` and `/` inside tokens. | `tests/unit/domain/test_text.py`, search tests. |

## 2. Answering

| # | Obstacle | Root cause | Solution | Evidence |
|---|---|---|---|---|
| 10 | The model summed operation hours wrongly (seven entries added to the wrong total). | Language models are unreliable at arithmetic over many rows. | Totals of the operations table (overall, NPT, per rig status, code, phase and activity, with merged time ranges) are computed at render time and given as their own passage; the prompt says to use them. | `tests/unit/domain/test_operation_totals.py`; the standby-hours golden question passes. |
| 11 | "What happened on <day>?" returned *not found* for a day covered by a report dated the next day. | The model did not know a DGOS dated D describes D−1 06:00 to D 06:00. | Every source tag carries its report's period; the resolver matches days by period; the prompt explains both report types. | `tests/unit/retrieval/test_temporal.py`; golden item passes. |
| 12 | A question naming a nearby platform was refused as out of scope. | The analysis model judged it general knowledge. | Capitalised names that occur in the reports (platforms, formations, companies) count as a domain signal that overrides an out-of-scope verdict; the answer model can still refuse. | `tests/unit/qa/test_service.py`; false refusal rate 0% on the golden set. |
| 13 | "From July to September" matched no report. | The analysis model returned the range ends as two specific dates. | A period takes precedence over specific dates from the model; the prompt separates them. Dates the user typed are parsed deterministically and always win. | `tests/unit/qa/test_analyzer.py`. |
| 14 | Facts in the middle of a long context were missed in questions spanning several reports. | Long-context attention is weaker in the middle. | When reports are given in full, the best search matches are moved to the front; catalog questions also receive the best passages. | Golden questions on trends and lists across reports pass. |
| 15 | Correct calculated values were flagged as unverified. | The verifier only accepted numbers present in the cited sources. | Values derived from cited numbers (sums, differences, ratios, percentages) are accepted; times and dates are checked as times and dates. | `tests/unit/qa/test_verifier.py`. |
| 16 | A glossary entry without an expansion was described as "meaning unknown". | The renderer treated a missing expansion as unknown although the glossary marked the entry confirmed with a description. | "Meaning unknown" only when the glossary says so or gives nothing. | `tests/unit/domain/test_rendering.py`. |

## 3. Environment and delivery

| # | Obstacle | Root cause | Solution |
|---|---|---|---|
| 17 | `UnicodeEncodeError` printing `½` or `°` in a Windows console. | Console code page cp1252; `python -I` ignores `PYTHONIOENCODING`. | The CLI reconfigures stdout and stderr to UTF-8 at start. |
| 18 | Replacing the index failed while the web app was running (Windows). | Windows refuses to replace a file another process holds open. | Readers use short-lived read-only connections; the writer builds a temporary file and retries the atomic replace. |
| 19 | The web app's scripts did not load on some Windows machines. | The Windows registry can map `.js` to `text/plain`, which browsers refuse for module scripts. | The app registers `text/javascript` and `text/css` explicitly. |
| 20 | GitHub Actions runs end with a start-up failure, including GitHub's own Dependabot jobs. | An account-level restriction on the private repository: GitHub reports no job at all, and its own Dependabot jobs fail the same way; the pinned action versions exist. | The same checks run locally and in pre-commit (lint, types, tests with an 85% coverage gate, dependency audit). The workflows will run once Actions is enabled for the account or the repository is public. |

## 4. Independent review

After the evaluation reached 97/97, a separate reviewer read the code adversarially and
reproduced each finding with throwaway scripts. Every finding was fixed test first:

| # | Severity | Finding | Fix |
|---|---|---|---|
| R1 | High | The verifier passed wrong figures: a token counted as a small count when either reading was at most 10 (`2,345`, `9.9`), the question was evidence, and pairs of any two numbers in the answer accepted about one random integer in five. | Only plain integers up to 10 are counts; evidence is the cited sources' text, label and period; calculated values must come from figures in the same or the previous sentence. |
| R2 | High | One undated report next to a dated one aborted the whole ingest (a date compared with a string in a sort). | A total order: type, undated last, date, id. |
| R3 | Medium | An answer still citing nothing after the retry was shown as answered. | It is replaced by the not-found message. |
| R4 | Medium | A second rejected model parameter escaped as a raw provider error; concurrent calls could drop the same parameter twice. | Step-wise relaxation in a loop, under a lock; every failure becomes a `ModelError`; evaluation items are isolated. |
| R5 | Medium | A disconnected stream released its concurrency slot while the model call went on. | The slot is held until the worker stops; the pipeline stops at its next stage. |
| R6 | Medium | "laporan 3 hari terakhir" was read as report number 3. | Numbers followed by time units or last/latest/first are not report numbers. |
| R7 | Medium | Enter while an answer streamed cancelled it and dropped the new question. | Enter waits; only the Stop button cancels. |
| R8 | Medium | A mistyped data folder wiped every output and swapped in an empty index. | A missing or empty data folder is an error and the outputs stay untouched. |
| R9 | Low–medium | Server errors bypassed the security headers and lost the request id in the log. | The request guard renders them. |
| R10 | Low | Any capitalised word found in the reports overrode an out-of-scope verdict. | Only code-like names (`TAPIS-C`, `K-28`, `D18`) count. |
| R11 | Low | A term repeated across glossary tables produced duplicate ids and a failed index build. | Ids are numbered until unique. |
| R12 | Low | A slow full-report response could overwrite a newer one. | Stale responses are ignored. |

A second pass (a security and compliance audit, plus tracing the two remaining evaluation
failures to their cause) found five more:

| # | Severity | Finding | Fix |
|---|---|---|---|
| R13 | Medium | The analyzer rewrote questions that needed no rewriting and could change their meaning ("what drill was conducted" became "what drilling was conducted", so the answer gave the drilling event instead of the safety drill). | Only follow-ups are rewritten; a question without a conversation keeps its exact words. |
| R14 | Low | Abbreviated labels did not match questions in plain words: a DDR records mud weight as "Density (ppg)" in the mud table, so a trend question skipped it. | Passages and the catalog give such labels their everyday name ("Density (ppg) (mud weight)", "Drill type (safety drill conducted)"). |
| R15 | Low | No overall time limit: with retries, one answer could in theory exceed the three minutes of the brief. | The web app ends an answer not ready after 170 s with a *try again* message; the worker stops at its next stage. |
| R16 | Low | The server trusted `X-Forwarded-For` from local clients, so a local caller could rotate its rate-limit key. | Proxy headers are ignored; the `server` header is no longer sent. |
| R17 | Low | Report labels (which can come from a PDF title) reached the analyzer prompt unescaped. | Escaped like the question and the history. |
| R18 | Medium | Whether a data conflict was stated depended on the model: in one run it picked one spud date and called the other a mistake. | Conflict caveats are written by code from the cross-report checks whenever the question or answer touches the field; model caveats on the same conflict are replaced ([ADR-0009](adr/0009-deterministic-facts-model-for-language.md)). |

## 5. Known limitations

- **Formats.** Templates cover the DDR and DGOS layouts of the sample. A report from another
  system is ingested as a generic document (page text and ruled tables): answerable, but without
  typed fields, report periods or quality checks.
- **Scanned PDFs** without a text layer cannot be read (no OCR).
- **Model variance.** Answers can differ between runs even at temperature 0; the residual risk
  is highest for questions aggregating over many reports.
- **Scale.** Reports are read in full when they fit 24k tokens (about four DDRs); beyond that,
  hybrid search is used, which can miss a fact a full read would find. Vectors are compared in
  memory, fine for thousands of passages, not millions.
- **Prompt injection** defences reduce the risk but cannot eliminate it.
- **Single-user deployment.** No authentication; the rate limiter is per process; meant for a
  local machine or a trusted network.
- **Visibility filter** handles fills and colours, not clipping paths or transparency groups in
  general; text clipped by a cell is treated as part of its value.

## 6. Next improvements

| Improvement | Value |
|---|---|
| A table-aware query path (text to SQL over `operations` and `fields` in the index) | Exact aggregation across many reports instead of reading them |
| A template wizard: learn a new form's labels from one example | New report families without editing YAML |
| A parser fallback that asks a model to map unknown forms into the JSON schema, reviewed against the page text | Better structure for unfamiliar layouts |
| Re-ranking with a cross-encoder for large collections | Fewer search misses beyond the full-context budget |
| OCR for scanned reports | Coverage of older archives |
| Authentication, per-user rate limits, audit log, container image | Multi-user deployment |
| An answer cache keyed by index version and question | Lower cost for repeated questions |
| Scheduled evaluation on fresh questions from users | Detect regressions after model or prompt changes |
