# STEP 18 DECISIONS — Analyst-Error Guardrails

**Date:** 17 July 2026 · **Charter:** amended to v0.14 · **Gates at
close:** 272 tests passed, `ruff` clean, `mypy --strict` zero errors.

## What this step is

Six controls against the ways analysts actually fail — chosen from
published research, not intuition, and two of them motivated by
failures observed first-hand in this engine's own production runs
(the fraud-run AUC-1.0 leakage and the 5,000-cardholders-as-500,000-
independent-rows pattern). The controls are additive: no schema break,
no existing-test change, every existing playbook gains them for free.

## The research this step answers

| Documented failure | Source | The control |
|---|---|---|
| Human computational error is constant; self-checking doesn't fix it; field audits find errors in the great majority of operational spreadsheets; experience doesn't lower error rates; developers are systematically overconfident | Panko, *What We Know About Spreadsheet Errors* (5.2% avg cell error rate across 13 studies); Panko & Sprague 1999 (no novice/expert difference); EuSpRIG corpus (Fidelity, Fannie Mae) | The engine's founding thesis, plus **G4**: a structured human checklist in the handoff — structured inspection catches what self-checking does not |
| Undisclosed analytic flexibility inflates false positives; details contingent on data invalidate p-values even without conscious fishing | Simmons, Nelson & Simonsohn 2011; Gelman & Loken (American Scientist) | Already held by V14 (pre-registered alpha, BH-FDR, significance never gates) — validated, nothing new needed |
| Unaccounted pseudoreplication (non-independence of data points) produces incorrect p-values | Forstmeier, Wagenmakers & Parker 2017 | **G2**: deterministic grouping-column scan over the approved profile; findings state p-values are not cluster-robust when repeated-measures structure exists |
| Low-power studies inflate both false negatives and false positives; "not significant" is misread as "no effect" | reproducibility literature (Button et al. line); remedy literature emphasizing effect sizes and CIs | **G3**: minimum detectable effect beside every two-group test — Cohen's h closed form (Cohen 1988) for proportions, normal-approximation rank-biserial for Mann-Whitney, at the pre-registered alpha and a declared power constant |
| Target leakage — the answer key riding into the features | observed first-hand: the July 2026 fraud run, `fraud_type` ⟺ `is_fraud`, ROC-AUC 1.0 | **G1**: per-feature association sentinel (Cramér's V / absolute point-biserial), fixed disclosed threshold, loud warning, never gates |
| Data lineage gaps — inability to trace where data came from and whether it changed — named among critical 2026 governance risks | Info-Tech *Data Priorities 2026* (40.9% of leaders: governance a top priority); 2026 AI-governance literature | **G5**: SHA-256 + byte-size fingerprint of the input, streamed, recorded in manifest and audit before any stage runs |
| AI hallucination in analytics; the published remedy is documenting assumptions and communicating uncertainty instead of presenting outputs as absolute facts | 2026 practitioner literature on analytics challenges; BARC Trend Monitor 2026 tracing hallucinations to poorly governed data | **G6**: the Limitations & assumptions narrative section — assembled from recorded caveats only, never fabricated, never suppressed |

## Design decisions worth recording

1. **Warnings never gate.** G1 and G2 are disclosures, not stops. A
   near-perfect association can be a legitimate duplicate encoding; a
   grouping column can be benign. The constitutional line holds:
   feasibility gates, findings never do — the engine makes patterns
   impossible to miss and leaves the verdict human.
2. **Every threshold is a fixed, disclosed constant** — the leakage
   threshold, the grouping-scan minimums, the MDE power — written into
   code and echoed in the hashed findings, chosen before any data was
   seen (the V15 posture, reapplied).
3. **G6 computes nothing.** The Limitations section is a *reader* of
   the findings store: timeliness below 1, unscored accuracy,
   independence warnings, MDE presence, skip counts, Cochran
   violations, leakage flags. The closing sentence of the section is
   the rule itself: absent caveats are absent because nothing was
   recorded, not because nothing was checked.
4. **MDE scope is honest.** Closed forms exist cleanly for two-group
   tests; r×c chi-square MDE (noncentral-χ² inversion) is declared a
   future extension rather than approximated silently.
5. **G5 streams.** `file_sha256` reads 64 KB chunks — a 91 MB DataCo
   file fingerprints without memory pressure.

## Planted-answer discipline

- G1: datasets with a categorical answer-key (`fraudish`/`none` ⟺
  target) and a numeric answer-key (`target × 100`) must be flagged at
  association 1.0 by the correct measure; a clean feature must not be;
  the flagged run still completes (never gates) and reproduces the
  AUC ≥ 0.99 pattern from production.
- G3: the Cohen's h MDE re-derived in the test from the published
  normal quantiles z₀.₉₇₅ = 1.959963984540054 and z₀.₈ =
  0.8416212335729143; the Mann-Whitney MDE re-derived from the
  normal-approximation formula; stricter alpha must raise the MDE.
- G2: 200 rows planted across exactly 40 households (average 5.0 rows
  per entity — precisely the disclosed scan thresholds) must be
  disclosed with those exact numbers; a flat dataset must produce
  `warning: null` and an empty candidate list.
- G5: the manifest fingerprint must equal an independent
  `file_sha256` of the source; different sources must produce
  different fingerprints.
- G6: the caveats present must match the findings recorded, and a run
  without a grouping column must NOT carry the independence caveat —
  fabrication is tested in both directions.

## Loophole hunt — found and closed

- **H5 (real gap, fixed):** a source file that vanished between Human
  Gate 1 and execution died with a raw `FileNotFoundError` from deep
  inside the fingerprint hash — no audit entry, no engine voice. Now
  an audited `ExecutionStopped` naming the file, the likely cause, and
  the remedy. Regression committed.
- **Verified:** the fingerprint is chunk-streamed (no memory blowup on
  large sources); manifest reproducibility holds with the fingerprint
  present (same source, same manifest hashes); the G6 section passes
  the injected-numbers claims scan in every end-to-end run; the
  independence scan is guarded when no profile stage exists; the
  leakage scan skips zero-variance columns rather than dividing by
  zero.

## What was built

- `model.py` — the leakage sentinel (`LEAKAGE_THRESHOLD`, per-feature
  associations, `leakage_warnings` in findings).
- `stats.py` — `_mde_two_group` (Cohen 1988 closed forms), MDE
  attached to Fisher and Mann-Whitney entries; grouping-scan constants.
- `executor.py` — the source fingerprint (with the H5 guard) recorded
  in audit and passed to the manifest; the pseudoreplication scan in
  the stats stage runner.
- `audit.py` — `write_manifest(..., source_fingerprint=...)`.
- `handoff.py` — the three-question analyst-bias checklist.
- `artifacts.py` — the Limitations & assumptions section.
- `tests/test_step18.py` — 15 tests: planted leaks, hand-derived MDEs,
  planted pseudoreplication, fingerprint identity and difference,
  caveat presence AND absence, checklist, re-performability, H5.

## Open items (declared, not hidden)

- r×c chi-square MDE via noncentral-χ² inversion.
- Cluster-robust inference (the remedy G2 discloses the need for) —
  a candidate step of its own.
- The playbook generator (the approved-draft design) remains the
  other queued step.
