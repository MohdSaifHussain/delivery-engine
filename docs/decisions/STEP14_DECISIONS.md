# STEP 14 DECISIONS — the developer-experience layer

**Date:** 14 July 2026 · **Scope:** compatibility report module,
/examples/ with committed output, QUICKSTART.md, charter v0.10.

## 1. Why this step (positioning, from a real JD)

Saif grounded the step in a live Scotiabank JD (Senior Analyst, GBM
Audit COO): quarterly continuous-monitoring reporting packages,
"compile, cleanse, and report data in a meaningful way, and investigate
data inconsistencies" — near-literal descriptions of what the engine
does. The positioning written into QUICKSTART and README: a first-level
accelerator and cognitive assistant with workpaper discipline, NOT a
replacement for enterprise tools (TMS, PowerBI, GRC). Internal audit is
the sharpest audience: re-performance is their term of art, and the
engine is its software embodiment.

## 2. Playbook Compatibility Report (the only engine code)

delivery_engine/compatibility.py: build_compatibility_report(findings,
playbook_dir, source) -> markdown. Design rules: it REUSES
planner.classify_columns and planner.check_requirements — zero
duplicated logic, so the report cannot drift from planner behaviour
(pinned by a test that a QUALIFIES verdict plans successfully). Pure
function: byte-identical output for identical inputs (tested). It
informs, never gates — enforcement stays in the planner.

## 3. Examples (three audiences, real committed output)

- transaction_monitoring/: 2,000-row Kaggle card-transaction sample;
  the full composition incl. Human Gate 2 two-phase flow; TM archetype
  bumped to v1.1.0 declaring formats [markdown, docx, pptx, xlsx].
  DECISION: pdf deliberately NOT in default formats — it hard-requires
  LibreOffice, and a must-produce format stops the pipeline when its
  tool is missing. Local users with LibreOffice add it per QUICKSTART.
- churn_analysis/: 400-row planted-signal dataset (churned iff
  tenure < 12) — the committed baseline findings show roc_auc 1.0,
  reproducibly. The strongest one-glance proof of deterministic ML.
- audit_data_quality/: 793-row audit-issues register with a planted
  ~8% null owner_team; the automated-workpaper story for the audit
  audience. Each example: run_example.py, README, and the REAL output
  package committed (compatibility report, findings, audit log,
  manifest, documents) so a stranger reads results before running code.

## 4. QUICKSTART.md

Install SOP (one pip line + one npm line), 60-second first run, run-on-
your-data via the compatibility report front door, write-your-own-
playbook walkthrough (descriptions documented as routing surfaces per
the step 9 rule), and the explicit AI-level table: zero-AI is a
first-class fully-deterministic mode; narrative-AI never writes numbers;
no third level by design.

## 5. Gates

178/178 locally (171 prior + 7 new: qualifying and failing verdicts with
planted counts, purity, planner-agreement, column-kinds section, empty
library refusal, formats line), ruff clean, mypy strict zero errors
across 12 source files. All three examples executed end-to-end in the
build environment; committed outputs are real runs.

## 6. Changed files

- src/delivery_engine/compatibility.py (new)
- tests/test_step14.py (new)
- playbooks/transaction_monitoring_review.toml (v1.1.0, formats)
- examples/ (new: 3 examples + READMEs + committed output)
- QUICKSTART.md (new), README.md (Start here section)
- PROJECT_CHARTER.md (v0.10)
