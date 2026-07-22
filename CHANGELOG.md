# Changelog

All notable changes to the Delivery Engine are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-07-22

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
