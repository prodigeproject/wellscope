# Go / no-go

Two decisions: whether this build is ready to submit (release gates), and whether an operator
of drilling campaigns should adopt a tool like this (business case).

## 1. Release gates

Gates were fixed before implementation. Hard gates must all pass; soft gates are weighted.

### Hard gates

| Gate | Criterion | Result |
|---|---|---|
| HG1 Runnability | A fresh clone set up by following only the README answers questions, on Windows and Linux | **Pass on Windows** (UAT-01). Linux not run by hand: no Linux machine was available and GitHub Actions, whose workflow includes Linux jobs, does not start on the private repository yet. |
| HG2 Ingest | `wellscope ingest` exits 0; every output file validates against its schema | Pass (UAT-02) |
| HG3 New PDFs | A new PDF becomes answerable with one command, no code change, no restart | Pass (UAT-03) |
| HG4 Refusals | 100% of out-of-scope questions get the canonical message | Pass: refusal recall 100%, including injection attempts (UAT-06) |
| HG5 Secrets and data | No key in the history; no dataset, parsed JSON or brief in the repository | Pass (UAT-10) |
| HG6 Latency | Maximum ≤ 60 s on the golden set (brief: 3 minutes) | Pass: 10.0 s (UAT-08) |
| HG7 Documentation | README with all required sections; planning and resolution documents | Pass (UAT-12) |
| HG8 Security | No open critical or high finding | Pass: dependency audit clean, history scan clean, review findings fixed ([SECURITY.md](SECURITY.md)) |

### Soft gates

| Gate | Target | Result | Weight | Score |
|---|---|---|---|---|
| SG1 Report-fact accuracy (DDR, DGOS, cross-report, conflicts) | ≥ 90% | 55/55, 100% (95% CI 93.5–100%) | 30 | 30 |
| SG2 Glossary accuracy | ≥ 95% | 23/23, 100% (CI 86–100%) | 15 | 15 |
| SG3 False refusals | ≤ 5% | 0% | 10 | 10 |
| SG4 Citation validity on answered questions | 100% | 100% verified | 10 | 10 |
| SG5 Latency p95 | ≤ 20 s | 4.4 s | 10 | 10 |
| SG6 Test coverage | ≥ 85% | 93% (lines, whole package) | 10 | 10 |
| SG7 Interface and accessibility checklist | Pass | Pass, 200% zoom not tested | 10 | 9 |
| SG8 Cost per question | ≤ USD 0.02 | about USD 0.010 | 5 | 5 |
| **Total** | | | **100** | **99** |

### Decision

**Conditional GO — submit.** Every hard gate passes except the Linux half of HG1, which could
not be executed. The risk is judged low: all dependencies ship Linux wheels, paths are handled
with `pathlib`, and the Windows-specific code (UTF-8 console, file-replace retries, MIME types)
is harmless elsewhere. Condition: the CI workflow's Linux jobs run once GitHub Actions is
enabled for the repository; any failure is fixed before further releases.

```
Decision: CONDITIONAL GO          Date: 2026-10-09
Hard gates: HG1 (Windows) · HG2 · HG3 · HG4 · HG5 · HG6 · HG7 · HG8 pass; HG1 (Linux) open
Soft gates: 99/100
Known limitations: RESOLUTION.md §4
```

## 2. Business case

All figures below are **illustrative assumptions** to be validated in a pilot, except the model
cost per question (measured in the evaluation).

### Value drivers

1. **Time to find facts.** Engineers, supervisors and geologists look up values across dozens
   of multi-page daily reports by hand. A cited answer in seconds replaces minutes of searching.
2. **Decision risk.** A missed fact (an earlier tool failure, a mud-weight trend, a data
   conflict) can lead to non-productive time. Daily rig costs in the sample reports are in the
   hundreds of thousands of US dollars, so an hour of rig time costs tens of thousands.
3. **Handover and onboarding.** Crews rotating shifts and new staff catch up on a well's status
   quickly, in Indonesian or English.

### Base case

| Parameter | Value | Basis |
|---|---|---|
| Active users | 12 | Assumption: one drilling campaign team |
| Adoption | 60% | Assumption |
| Questions per active user per day | 8 | Assumption |
| Working days per year | 240 | Assumption |
| Minutes saved per question | 4 | **Key assumption**, to be measured in the pilot |
| Loaded labour cost | USD 45 per hour | Assumption |
| Model cost per question | USD 0.010 | Measured (EVALUATION.md) |
| Hosting | USD 40 per month | Assumption: one small server |
| Maintenance | 0.1 FTE, about USD 9,000 per year | Assumption |
| Production hardening (authentication, deployment, monitoring) | 4 weeks, about USD 7,500 once | Assumption |

- Questions per year: 12 × 0.6 × 8 × 240 = **13,824**
- Value per year: 13,824 × 4/60 h × USD 45 = **USD 41,472**
- Year-one cost: 7,500 + 9,000 + 480 + 13,824 × 0.010 (= 138) = **USD 17,118**
- Year-one net: **USD 24,354**, a return of about **142%**
- Payback: 7,500 ÷ ((41,472 − 9,000 − 480 − 138) ÷ 12) ≈ **2.8 months**
- Model usage is under 1% of the cost; people (maintenance) dominate.

### Sensitivity to minutes saved per question

| Minutes saved | Value per year | Year-one net | Pilot decision |
|---|---|---|---|
| 1 | USD 10,368 | −USD 6,750 | No-go |
| 1.65 | USD 17,118 | USD 0 | Break-even |
| 2 | USD 20,736 | USD 3,618 | Marginal |
| **4 (base)** | **USD 41,472** | **USD 24,354** | **Go** |
| 8 | USD 82,944 | USD 65,826 | Strong go |

Other levers: adoption at 30% halves the value (the base case becomes marginal); a model ten
times more expensive adds about USD 1,250 per year and does not change the decision. If
accuracy fell below about 90%, users would re-check answers by hand and the time saved would
shrink; that is why accuracy is a release gate rather than just a metric.

### Recommendation

**Conditional GO for a four-week pilot** with one well team. Measure (a) minutes saved per
question with a before-and-after time study, (b) accuracy on users' real questions, (c) weekly
adoption. Proceed to production if (a) ≥ 2 minutes, (b) ≥ 90% and (c) ≥ 50%.

Not counted: avoided non-productive time. Avoiding a single rig hour per year would cover a
large part of the year-one cost.

## 3. Explicit non-claims

- WellScope is **not** claimed to reduce non-productive time; that is a hypothesis for a pilot.
- The measured accuracy applies to the sample dataset and this golden set; accuracy on other
  report formats has not been measured.
- Typed parsing is claimed for the DDR and DGOS form families of the sample (templates `ddr@1`
  and `dgos@1`); other PDFs are answerable through generic capture with less structure.
- Prompt-injection defences reduce the risk; they do not remove it.
- This is not a multi-user production system: no authentication, no high availability, a
  per-process rate limiter.
- Business figures are illustrative assumptions, except the measured model cost.
