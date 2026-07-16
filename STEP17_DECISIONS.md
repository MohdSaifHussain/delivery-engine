# STEP 17 DECISIONS — The Universal Descriptive Math Layer

**Date:** 16 July 2026 · **Charter:** amended to v0.13 · **Gates at
close:** 257 tests passed, `ruff` clean, `mypy --strict` zero errors.

## What this step is

Step 15 answers "is this difference real?" (inference). Step 17
answers "what is the SHAPE of every column?" (description): skewness,
kurtosis, confidence intervals for the mean, tail percentiles, robust
outliers, distribution fit, entropy, temporal gaps and trends. It
requires no target column, so with the `universal_audit` archetype the
engine now runs a full quantitative audit on ANY dataset the planner
can classify — the "universal math layer" of the v2.0 spec, built the
constitutional way: a governed stage over plan-approved columns, not a
flag that bypasses the plan.

## The methods, each traced to a primary source

| Decision | Source |
|---|---|
| Bias-adjusted sample skewness G1 and excess kurtosis G2 | Joanes & Gill, *Comparing measures of sample skewness and kurtosis*, The Statistician 47(1), 1998 — the scipy `bias=False` estimators (also pandas/Excel defaults) |
| t-interval for the mean, 95% a declared constant, small-n noted | NIST/SEMATECH e-Handbook §7.2.2.1; `scipy.stats.t.interval` |
| Empirical tail percentiles p95/p99, `linear` interpolation pinned | numpy documented default; in risk contexts, the historical-simulation VaR levels (Jorion, *Value at Risk*, 3rd ed.) — noted in the findings, neutrally named |
| MAD modified z-score outliers, scale 0.6745, threshold 3.5 | Iglewicz & Hoban, *How to Detect and Handle Outliers*, ASQC 1993; NIST/SEMATECH e-Handbook |
| MAD == 0 → declared skip, never a division by zero | the modified z-score is undefined on a majority-constant column; the engine says so |
| Lilliefors test for normality and (via log x) lognormality | Lilliefors, JASA 62(318), 1967; `statsmodels.stats.diagnostic.lilliefors` |
| Weibull: fitted params + KS distance, **explicitly no p-value** | Lilliefors 1967 — a KS p is invalid with estimated parameters, and no standard Lilliefors table exists for the Weibull; the omission and its reason live in the findings |
| Best fit = smallest KS distance | a disclosed selection rule, not a significance claim |
| Shannon entropy (bits) + normalized entropy + 1% rare cutoff | Shannon, *A Mathematical Theory of Communication*, 1948; the cutoff a fixed disclosed constant |
| Temporal max gap + daily-count trend | `scipy.stats.linregress` (classical simple regression; its p is valid — no null parameters estimated from the data) |
| 6-decimal rounding before hashing | the step-10 contract |

## The constitutional positions (rule V15)

1. **The engine never improvises a method.** `math_checks` is declared
   from a fixed list (`numeric_shape`, `outliers`, `distribution_fit`,
   `categorical_entropy`, `temporal`, `all`); the list lives in the
   constitution (`playbook.py`).
2. **No post-hoc thresholds.** The MAD scale and threshold, the rare
   cutoff, the CI level, the percentile method, MIN_N — all fixed
   constants written into the hashed findings under `constants`,
   chosen in code and never after seeing results.
3. **Columns come from the plan** approved at Human Gate 1 — the
   original spec's `analyze_numbers = true` auto-detection would have
   bypassed that gate; this design keeps the flag (which checks run)
   while the plan keeps the columns (what they run on).
4. **Descriptive values never gate**; feasibility does. Skips carry
   written reasons; an all-skipped stage fails feasibility.

## Planted-answer discipline

Every verification value in `tests/test_step17.py` is an independent
re-derivation inside the test file: the Joanes & Gill G1/G2 formulas
by hand; the t-interval from the published critical value
t(0.975, df=9) = 2.2621571628; numpy's linear percentile
re-implemented; the MAD modified z-score by hand; Shannon entropy from
exact fractions (uniform-4 = exactly 2 bits; ½/¼/¼ = exactly 1.5
bits); a deterministic inverse-CDF grid (no RNG anywhere) standing in
for perfectly normal and perfectly lognormal samples, which the
Lilliefors-based fitter must identify.

## Loophole hunt — found and closed

- **M2 (design gap, fixed):** a 0/1 column is classified both
  `numeric_column` and `binary_target`; profiling its "skewness" and
  fitting distributions to it is noise dressed as analysis. Binary
  columns are now excluded from the numeric suite, the exclusion is
  disclosed in `column_selection`, and inference on them remains where
  it belongs — the stats stage. Regression test committed.
- **M4 (accounting gap, fixed):** NaN drop counts existed for numeric
  columns only; categorical entries now carry `n_dropped_nan` and
  temporal entries `n_dropped_unparseable_or_nan`. Silent drops are
  the loophole; counts are the fix.
- **M7 (robustness gap, fixed):** a Weibull MLE fit that fails to
  converge is now a recorded absence with the exception text, pinned
  at KS distance 1.0 — the theoretical maximum — so a failed fit can
  never be selected as best. Never a crash, never silent.
- **M8 (found by the demo run, fixed):** constant daily counts make
  Pearson's r mathematically undefined (zero variance in y), and
  scipy returns NaN — which would have sat in hashed evidence as a
  lie of precision. The engine now records slope 0.0 plus
  `trend_r_undefined_reason` and omits `trend_r` entirely; the
  narrative says "correlation undefined: constant daily counts". The
  regression asserts `json.dumps(findings, allow_nan=False)` — no NaN
  value anywhere in sealed findings, ever. (A secondary lesson from
  the same fix: an earlier scripted edit silently no-op'd because a
  lint autofix had changed the target text — replaced with a verified
  targeted edit; substitutions are now grep-verified before rerunning
  gates.)
- **Narrative claims scan (the charter working as designed):** the
  literal tokens "p95" and "p99" in my own report prose contained
  un-injected digits and failed `verify_artifact_numbers` on the first
  end-to-end run; backticked as structural references before the test
  could pass — the second time this scan has caught the engine's own
  author (see STEP15_DECISIONS).

## What was built

- `src/delivery_engine/mathkit.py` — the descriptive module (unit
  surface `run_math`).
- `playbook.py` — `StageKind.MATH`, `KNOWN_MATH_CHECKS`, `math_checks`
  stage key, rule V15.
- `executor.py` — `_run_math_stage` (disclosed column selection with
  the binary exclusion, feasibility-only gating, hashed findings).
- `artifacts.py` — the Distribution & shape narrative section and the
  math line in the evidence trail.
- `handoff.py` — the QA spot-check bound to the sealed math digest.
- `playbooks/universal_audit.toml` — the sixth archetype; requires
  only an id column.
- `tests/test_step17.py` — 29 tests: planted answers, V15
  constitution, end-to-end, re-performability, hunt regressions (M2, M4, M7, M8).

## Open items (declared, not hidden)

- Change-point detection for temporal columns (beyond max-gap and
  linear trend) — the standing step-18-adjacent candidate.
- Non-CSV sources (the consistent v1 line across model, stats, math).
- Step 18 (two-tier output + domain vocabulary) remains deferred by
  decision — it is a migration, to be planned as one.
