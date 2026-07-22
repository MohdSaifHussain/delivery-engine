# STEP 23 DECISIONS — The Deterministic Across-Runs Trend Report

**Date:** 19 July 2026 · **Charter:** amended to v0.19 · **Gates at
close:** 368 tests passed (+21), `ruff` clean, `mypy --strict` zero
errors.

## What this step is

Step 22 preserves the iterative cleaning lifecycle as an ordered chain
of sealed runs (`run_001 .. run_NNN`). Step 23 reads that chain and
renders ONE picture of the remediation journey: how validation
exceptions shrink and data-quality scores climb from the first messy
attempt to the latest. It is the "comparison feature" the single-run
report (Step 21) made people want once they could see one run at a
time. New `generate_trend.py` runs it against a dataset's output area.

## The governing constraint: read and draw, never compute

The report draws the VALUES from each run and lets the reader see the
movement. It never computes a delta, a percentage improvement, or a
"23% better" claim. Computing a cross-run difference would be the AI
authoring a figure — exactly what the injected-numbers rule forbids —
so the improvement is VISUAL (the bars move across attempts), not an
authored number. This is the constitutional line of the step, and it is
proven by test: the exception-difference `1312 - 312 = 1000` and the
completeness-difference `100 - 90 = 10%` are asserted ABSENT from the
output.

## Design positions

1. **Pure function of the runs.** `build_trend_html(runs, ...)` is
   deterministic: the same sealed runs produce byte-identical HTML
   (proven by test). The generation date is display metadata in the
   footer, outside the determinism contract, exactly as in Step 21. The
   trend is therefore itself re-performable evidence of the
   remediation.

2. **Every point is a hashed finding.** Each run contributes only
   numbers already in its sealed store — `total_exceptions`,
   `rules_evaluated`, the DAMA dimension scores. Nothing is derived. The
   per-run table carries each run's validate-findings digest so any
   point traces back to its sealed run.

3. **A mirror, not a cheerleader.** If the data got WORSE across runs
   (exceptions rose), the report shows that honestly and never claims
   improvement — proven by a hunt regression. The trend reflects
   whatever the runs actually recorded.

4. **Not-scored stays not-scored.** A DAMA dimension the engine did not
   score in a run (accuracy, timeliness → None) is omitted for that run,
   never plotted as a 0% point — the same honesty as the single-run
   report.

5. **Incomplete runs are skipped, not guessed.** A stopped run folder
   with no sealed findings is left out of the trend rather than
   fabricated — proven by test.

6. **Sorted by run number, not disk order.** The trend reads runs
   through `existing_runs` (Step 22), so runs created out of order on
   disk still appear in numeric sequence.

7. **Shares the single-run report's visual language.** `trend.py`
   imports the palette, CSS, and helpers from `report.py` rather than
   duplicating them, so the two artifacts stay visually consistent and
   cannot drift apart.

## Loophole hunt — found and closed (with regressions)

- **H1 (verified safe, regressed):** worsening data (exceptions rising)
  renders honestly with no "improvement" claim — the mirror property.
- **H2 (verified safe, regressed):** a run with every DAMA dimension
  unscored renders a valid document without crashing (no points
  plotted).
- **H3 (verified safe, regressed):** a hostile dataset-area name is
  HTML-escaped — no injection.
- **H4 (verified safe, regressed):** extreme scale (9,999,999 vs 0
  exceptions) never produces negative or overflowing bar widths.
- **H5 (verified safe):** runs created out of numeric order on disk
  appear in sorted order in the trend.

## What was built

- `src/delivery_engine/trend.py` — pure functions: per-run findings →
  inline SVG trend (exceptions-per-run bars, DAMA-scores-across-runs
  line chart) → self-contained HTML; the per-run table; reuses
  `report.py`'s style. `_read_run` pulls only hashed values from a
  sealed package.
- `generate_trend.py` — thin CLI wrapper; injects the generation date.
- `tests/test_step23.py` — 21 tests: planted per-run values, the
  no-computed-delta proofs, the every-number-traces proof, determinism,
  single-run and not-scored edge cases, package-area integration with
  clean errors, and the four hunt regressions.

Verified end-to-end on REAL engine output: two `--lineage` runs sealed
into `run_001`/`run_002`, then `trend_from_area` read them and produced
`trend.html` — the full Step 22 → Step 23 pipeline works on genuine
sealed packages, not only synthetic fixtures.

## What this completes

The roadmap that began when the iterative-cleaning insight surfaced
(Step 21 session) is now built end to end:
- **Step 21** — the single-run visual report.
- **Step 22** — run lineage: the cleaning lifecycle preserved as
  sequenced immutable runs.
- **Step 23** — the trend report: the lifecycle drawn as one picture.

## Open item (declared, not hidden)

- **Human-declared final** (carried from Step 22): the "all-green =
  final" signal must be a NAMED HUMAN's decision, not the engine's. The
  engine reports the green state as fact; a person declares a run final.
  Still a small, self-contained follow-on — not built here, not
  silently folded in.
