# Changelog

All notable changes to the Delivery Engine are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.6.0] - 2026-07-31

### Fixed
- `generate_playbook.py` restored to the repository root. It was
  accidentally relocated to `historical/` in the v1.0 root cleanup
  (commit `9136868`, which bundled it with genuinely local-only dev
  scripts), while the engine's own runner error
  (`src/delivery_engine/runner.py:200`) and USER_GUIDE.md's worked
  example continued to reference it at root — a documentation-coverage
  audit found the mismatch. `src/delivery_engine/generator.py` (the
  module behind the script) stayed in `src/` throughout and was never
  untested; only the root CLI entry point was mis-relocated.

### Added
- USER_GUIDE.md documentation for `generate_report.py` (the
  deterministic visual report, step 21) and for `generate_trend.py`
  together with `run_project.py --lineage` (the across-runs trend
  report over `run_001..run_NNN` lineage, steps 22–23) — both scripts
  existed and worked but had no documentation coverage in README.md,
  QUICKSTART.md, or USER_GUIDE.md before this entry.
- Build Step 25: the playbook generator now surfaces the step-24
  model-stage keys (`metric_ci`, `split`, `n_splits`) as fixed,
  commented suggestion lines inside a drafted model stage — never as
  active keys, so a generated draft still loads and means exactly what
  a pre-step-25 draft meant. `metric_ci` is suggested whenever a model
  stage is drafted; `split`/`n_splits` only when the profile classifies
  a `timestamp_column` (the generator's own feasibility-gating pattern,
  extended). See `docs/decisions/STEP25_DECISIONS.md` and
  PROJECT_CHARTER.md's v1.6 amendment. 6 new tests
  (`tests/test_step25.py`) — the first content coverage the
  model-stage branch of the generator's template has ever had; no
  existing test required updating.

## [1.5.0] - 2026-07-30

### Added
- Model-stage evidence honesty (build step 24), grounded in a governed
  forward-deployed engagement on real semiconductor wafer-fabrication
  data (UCI SECOM). Three changes, all opt-in — a playbook declaring
  none of the new keys reproduces byte-identical findings, verified by
  re-running every shipped example with a committed golden and
  comparing findings digests.
  - **Metric confidence intervals** (`metric_ci`, model-stage key,
    default `false`). When enabled, adds Wilson score 95% confidence
    intervals (Brown, Cai & DasGupta 2001) for recall and precision, so
    a point estimate from a handful of positive cases is not read as
    more precise than it is — the same failure G3 (step 18) exists to
    prevent one layer up. Reuses `stats.wilson_interval` (newly
    promoted from a private `_wilson` helper) rather than a second
    implementation. Alpha is the playbook's pre-registered `[stats]`
    alpha when a stats stage exists, else a disclosed engine default
    (0.05). A zero denominator (no positive cases, or the model
    predicted none) is a disclosed skip, never a crash, never a
    fabricated interval.
  - **Evaluation-split honesty** (`split` = `random` | `time_ordered` |
    `walk_forward`, default `random`; `n_splits`, legal only with
    `walk_forward`). A random split on time-ordered data measures
    something deployment never experiences. `time_ordered` holds out
    the last portion of a stably time-sorted dataset; `walk_forward`
    runs `TimeSeriesSplit` and evaluates a fresh pipeline per fold.
    Findings carry every fold's train/test size, positive count and
    metrics, plus a mean/min/max summary per metric in one dict, so the
    range sits structurally beside the mean. The ordering column comes
    from the plan's classified `timestamp_column` — never guessed,
    never row order; declaring a non-random split with no classified
    timestamp column is a clean feasibility refusal naming the remedy.
  - **Identifier-aware injected-numbers scanning** (bug fix, no new
    playbook key). `verify_artifact_numbers` no longer misreads digits
    inside a known column name (e.g. `sensor_060`) as an unprovenanced
    numeric claim — the scanner previously crashed the narrative stage
    for any dataset with digit-bearing column names. A token is
    exempted only when it exactly matches a column name from the
    approved plan AND contains at least one non-digit character (a
    column literally named `95` cannot launder a bare `95`); the number
    regex itself is untouched, so a bare `p95` (not a column name) is
    still caught exactly as step 17 intended.
- 27 new tests across the three changes (`tests/test_step24.py`).

### Fixed
- The model-stage audit-log message unconditionally read
  `findings['n_train']`/`['n_test']`, which don't exist for
  `walk_forward`'s per-fold findings shape.

## [1.4.0] - 2026-07-25

### Added
- Diagnostic record gains an `encoding` block: `stdout_encoding`,
  `stderr_encoding`, `filesystem_encoding`, `preferred_encoding`, and
  `default_encoding`. Kept separate from the PEP 508 environment block
  so those eight standard field names keep meaning exactly what PEP 508
  says. `stdout_encoding` is the field that earns its place — the engine
  prints em-dashes and box-drawing characters, so a cp1252 stdout raises
  `UnicodeEncodeError` from the engine's own `print` calls, producing a
  traceback that names a print statement rather than an encoding.
  Schema version moves 1.0 → 1.1. 5 new tests.

### Known limitations
- Binary document byte-stability (`.docx` / `.pptx` / `.xlsx`) is not
  held. Two runs on identical inputs produce different container
  hashes: OOXML carries ZIP entry timestamps and `docProps/core.xml`
  `dcterms:created` / `dcterms:modified`, both of which move per run.
  Document *content* is deterministic and every figure still traces to
  a hashed finding — only the container bytes vary. Declared rather
  than fixed; timestamp normalisation remains available as an additive
  change if byte-stability is ever required. See PROJECT_CHARTER.md
  amendment record v1.3.

### Changed
- The v2.0.0 python-docx/pptx migration is **withdrawn**. Rewriting a
  working subsystem for no user-facing difference is not what §4.5
  ("the engine stays small, tested, gated") is for, and the determinism
  argument that motivated it was incorrect. See PROJECT_CHARTER.md
  amendment record v1.3.

## [1.3.0] - 2026-07-25

### Added
- Diagnostic record: `diagnose.py` and `src/delivery_engine/diagnostics.py`.
  Writes `delivery-engine-diagnostic.json` describing what a bug report
  needs and cannot be guessed from a traceback: PEP 508 environment
  markers, versions of the packages that change engine behaviour
  (analystkit, duckdb, pandas, scikit-learn, scipy), and whether Node is
  on PATH. Written automatically when `run_project.py` fails with an
  unexpected error — the class of failure that occurs *before* the
  executor starts and therefore before any `audit_log.jsonl` exists.
  Also available on demand: `python diagnose.py`. 20 tests.
- Privacy by construction, not by policy: no usernames, hostnames,
  absolute paths, environment variables, or dataset content. Traceback
  frames are reduced to `basename.py:LINE in function` — the fault is
  located precisely, the user's directory structure stays private. The
  source file is recorded by extension only. Nothing is transmitted;
  the record is written locally and attaching it is the user's decision.

### Fixed
- `pyproject.toml` still carried the `0.1.0` scaffold version through
  v1.0.0, v1.1.0, and v1.2.0. Now 1.3.0. Found by the diagnostic on its
  first run: every bug report would have claimed 0.1.0 regardless of the
  release installed, making the field useless for triage.

## [1.2.0] - 2026-07-25

### Added
- Step 23 Human-Declared-Final: declare_final.py CLI entry point and
  src/delivery_engine/declaration.py. Tier-2 evidence-grade declaration
  grounded in EU AI Act Article 14 (human oversight, named and
  timestamped), NIST AI RMF MANAGE-4.1 (tamper-evident human
  confirmation), ISO/IEC 42001:2023 §6.1.2 (human review of AI
  outputs), and Maker-Checker / Four-Eyes principle (financial services
  governance). Shows reviewer a structured summary of key findings and
  disclosed limitations before accepting CONFIRMED input — the
  Northwell high-performing hospital pattern, not the Cigna rubber-stamp
  pattern. Writes tamper-evident declaration.json and regenerates
  manifest to include it. Non-gating: packages without a declaration
  are valid. 15 planted-answer tests including loophole hunt.
- churn_analysis example now includes declaration.json — first package
  declared final by Mohd Saif Hussain, Architect on 25 July 2026.
  Shows the feature working on real production data.

### Fixed
- analystkit v2.1.0 upgrade resolves all 13 pre-existing parquet test
  failures in test_step20. Native Apache Parquet support via DuckDB
  read_parquet, DuckDB excel extension for .xlsx (retiring pandas
  divergence), .xls refusal with clean error message.
  Full suite: 394 passed, 1 skipped, 0 failed — first fully green
  suite in the project's history.

### Changed
- PROJECT_CHARTER.md bumped to v1.1. Amendment record (v1.1) closes
  the human-declared-final open item carried from v0.18/v0.19.
  Records framework citations and cognitive support tool framing.
- CLAUDE.md updated: human-declared-final marked complete in roadmap,
  test count updated to 394.

## [1.1.0] - 2026-07-24

### Added
- Step 21 math charts: Descriptive statistics section in report.html shows
  numeric column distributions (mean, 95% CI range bar, best-fit name,
  outlier count) and categorical entropy bars. Renders only when
  findings/math.json is present. Pure function maintained. 9 new tests
  including injected-numbers proof. WCAG 2.2 AA aria-labels on all charts.
- G2 pseudoreplication disclosure in model stage (Forstmeier, Wagenmakers
  and Parker 2017, Biol Rev 92:1941-1968): records assumed_independent_units
  and warns that a flat CSV cannot prove row independence. Non-gating.
  Cited reference in findings.
- G3 minimum detectable effect in model stage (Cohen 1988, power=0.8,
  alpha=0.05): computes mde_cohen_h from n_test. Non-gating. Cited reference
  in findings. churn: G2 gate=False G3 mde=0.066761. paysim: G2 gate=False
  G3 mde=0.002221 (6.36M rows gives very high power).
- paysim_fraud run_example.py: first committed runner for the PaySim example.
  Writes to output/final/ structure matching all other examples. isFraud
  confirmed as target before run (isFlaggedFraud excluded). Pre-v1.1 flat
  package preserved to examples/historical/paysim_fraud_pre_v1.1/.
- examples/index.html: white-background interactive gallery with 7 example
  cards, filter bar by archetype, completeness dots with hover tooltips,
  smooth filter animations. Correct relative paths to all report.html files.
- CLAUDE.md: constitutional governance file for Claude Code sessions.
  Contains architecture principles, build commands, code conventions, what
  NOT to do, v1.1 roadmap, end-of-session sync instructions for Windows.

### Fixed
- Timeliness metric: profiler sentinel value 0.0 (no date column) now renders
  as not scored instead of a misleading amber 0% bar. Identical treatment to
  accuracy. One regression guard added (test_h5_timeliness_zero_shows_not_scored).
- paysim_fraud gallery links updated after output/final restructure.
- CLAUDE.md: baseline.py corrected to model.py (actual filename).

### Changed
- All 7 examples re-run on v1.1 engine; all report.html files regenerated.
  universal_audit now shows Descriptive statistics section with math charts.
  churn_analysis and paysim_fraud baseline.json include G2/G3 disclosure fields.
- paysim_fraud restructured from flat package to output/final/ subfolder,
  consistent with all other examples.

### Added
- 7 complete, verified example packages covering the full analyst workflow:
  `audit_data_quality`, `churn_analysis` (Kaggle Telco, 7,043 rows),
  `customer_profiling`, `paysim_fraud` (6.36M rows), `segment_comparison`,
  `transaction_monitoring`, `universal_audit`
- Step 21 deterministic visual report (`report.html`) for every example
- `examples/historical/` archive: W3C PROV-aligned provenance record of earlier
  packages, step-prefixed and indexed by a standards-compliant README
- `historical/` folder at repo root: development scripts preserved with context,
  not deleted
- `docs/decisions/` folder: 18 engineering decision records moved from root
- `Dockerfile` + `.dockerignore`: multi-stage build mirroring CI exactly
  (Python 3.12 + Node 24); 367/368 tests pass in a clean container
- Scoped `.gitignore` exception (`!examples/*/output/**`) so curated example
  outputs ship in the repo and are visible to visitors without running anything
- `customer_profiling` example: 7th example, descriptive audit via
  `universal_audit` archetype on a 400-row customer table
- `churn_analysis` updated to Kaggle Telco Customer Churn dataset (ROC-AUC
  0.845, recall 0.546) replacing the synthetic 1.0 placeholder
- Segment comparison and universal audit stubs built into complete examples
- `docs/decisions/` and `historical/` as new organizational folders
- "Run with Docker" section in README

### Changed
- `examples/README.md`: updated to reflect 7 examples, historical archive,
  and current results; removed "output not yet included" stub notices
- `docs/how-the-examples-grew-up.md`: restructured into 4 stages reflecting
  the full v1.0 arc
- `examples/churn_analysis/README.md`: updated for Telco dataset
- Repo root cleaned: dev scripts and STEP decision files moved to
  organized subfolders

### Fixed
- `.gitignore` previously hid all `examples/*/output/` content from git,
  making the showcase packages invisible to visitors; fixed with a scoped
  un-ignore rule

## [0.19.0] - 2026-07-17

Step 23: deterministic across-runs trend report. Reads `run_NNN` lineage
and draws the remediation journey (exceptions shrinking, quality climbing).
Injected-numbers-only, never computes a cross-run delta. Charter v0.19,
368 tests.

## [0.18.0] - 2026-07-15

Step 22: run lineage. Sequenced immutable `run_NNN` folders, anchored on
run number not date, never overwrites. Charter v0.18, 347 tests.

## [0.17.0] - 2026-07-10

Step 21: deterministic visual report. Self-contained HTML from hashed
findings store. Green >= 99.9%, amber below, not-scored never drawn as zero.
Charter v0.17, 331 tests.

## [0.16.0] - 2026-07-05

Step 20: source adapters and Single-Reader Principle. Charter v0.16,
310 engine tests / 75 kit tests.

## [0.15.0] - 2026-07-01

Step 19: deterministic playbook generator, hardened `run_project.py` runner,
USER_GUIDE.md. Charter v0.15, 291 tests.

## [0.14.0] - 2026-06-25

Step 18: Analyst-Error Guardrails G1-G6, leakage sentinel,
pseudoreplication detection. Charter v0.14, 272 tests.

## [0.13.0] - 2026-06-18

Steps 15-17: stats stage (Wilson CIs, Fisher/chi-square, Mann-Whitney,
BH FDR, pre-registered alpha V14), preview+handoff, math stage /
universal_audit archetype. Charter v0.13, 257 tests.

## [0.10.0] - 2026-06-01

Steps 1-14: core executor, findings store, SHA-256 verification,
Human Gates 1 and 2, baseline model stage, multi-format document output,
four archetypes (churn, DQ, ops, transaction monitoring). Charter v0.10,
177 tests.

[Unreleased]: https://github.com/MohdSaifHussain/delivery-engine/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/MohdSaifHussain/delivery-engine/releases/tag/v1.0.0
