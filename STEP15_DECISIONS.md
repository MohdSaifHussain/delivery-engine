# STEP 15 DECISIONS — The Statistical Evidence Layer

**Date:** 15 July 2026 · **Charter:** amended to v0.11 · **Gates at close:**
212 tests passed, `ruff` clean, `mypy --strict` zero errors.

## What this step is

The engine's findings through step 14 are DESCRIPTIVE: counts, rates,
deltas, model metrics. Step 15 upgrades them to INFERENTIAL: *is the
difference between segments real, or noise? how uncertain is this
rate?* — computed deterministically, sealed into the hashed Findings
Store, and narrated (never computed) by AI stages. This is the point of
the whole architecture applied to statistics: the mathematics is real,
the numbers are traceable, and the judgment stays human.

The deliberate scope line, recorded: **statistics in, heavy ML out.**
Hyperparameter search, AutoML, and non-deterministic training fight the
charter's re-performability core and are out of scope by design. The
fixed-seed baseline (step 10) remains the right amount of ML for a
governance engine.

## The methods, each traced to a primary source

| Decision | Source |
|---|---|
| Wilson score interval for every proportion, never Wald | Brown, Cai & DasGupta, *Interval Estimation for a Binomial Proportion*, Statistical Science 16(2), 2001; NIST/SEMATECH e-Handbook §7.2.4.1; `statsmodels.stats.proportion.proportion_confint(method="wilson")` |
| Fisher's exact test for 2×2 tables (exact p, no Yates debate) | scipy.stats.fisher_exact official documentation |
| Pearson chi-square, `correction=False`, for r×c > 2×2 | scipy.stats.chi2_contingency official documentation (Yates applies only to 2×2) |
| Cochran's-rule validity flag on every asymptotic chi-square | NIST/SEMATECH e-Handbook (expected ≥ 1 everywhere; ≥ 80% of cells ≥ 5) — violations flagged, never hidden |
| Mann-Whitney U for numeric two-group comparison; parametric t-test **refused** in v1 | scipy.stats.mannwhitneyu (two-sided, `method="auto"` — a deterministic function of the data); the refusal mirrors OpsKit's Simpson's-paradox posture: normality is an assumption the engine cannot certify |
| Effect size ALWAYS beside every p-value: Cramér's V, rank-biserial r | ASA Statement on p-values, Wasserstein & Lazar, The American Statistician 70(2), 2016, principle 5; Kerby 2014 (rank-biserial simple difference formula) |
| Benjamini-Hochberg FDR across the full family of tests a stage runs | Benjamini & Hochberg, JRSS-B 57(1), 1995; `statsmodels.stats.multitest.multipletests(method="fdr_bh")` |
| 6-decimal rounding before hashing | the step-10 contract, re-applied |

## The constitutional positions (rule V14)

1. **The engine never improvises a method.** `stat_test` is declared
   from a fixed list (`proportion_ci`, `chi2_independence`,
   `mann_whitney`, `full_inference`); the list lives in the
   constitution (`playbook.py`), the KNOWN_KIT_TOOLS precedent.
2. **Alpha is pre-registered.** It comes from the playbook's `[stats]`
   table — part of what the human approves at Human Gate 1, fixed
   before any p-value is computed, range-checked in (0, 1), booleans
   refused, and a `[stats]` table with no stats stage to apply it to is
   refused as a silent-typo hazard.
3. **Significance never gates.** The step-10 principle ("metric values
   never gate") extended: a must_pass stats stage fails on FEASIBILITY
   (missing dependency, plan/source drift, degenerate target, nothing
   testable) and never on p-values. A pipeline that stops or proceeds
   on significance is p-hacking machinery.
4. **Skips are evidence.** Every skipped test carries a written reason
   in the hashed findings; an all-skipped stage produced no inference
   and fails feasibility. Nothing is silently untested.
5. **Column selection is the plan's, not the stage's.** Target and
   features come from the classified kinds approved at Human Gate 1 —
   the same disclosed first-binary-target rule, wording and all, as the
   model stage.

## Planted-answer discipline, applied to statistics

Every verification value in `tests/test_step15.py` is computed by an
INDEPENDENT implementation inside the test file — never
library-vs-same-library:

- Wilson interval re-derived from the closed form with the published
  standard-normal constant 1.959963984540054;
- Fisher's two-sided p re-derived by brute-force hypergeometric
  enumeration over `math.comb`;
- the Mann-Whitney exact p pinned to the analytic complete-separation
  value 2 / C(12, 6), with rank-biserial exactly ±1;
- Benjamini-Hochberg re-implemented by hand per the 1995 procedure
  (sort, p·m/rank, backward monotonicity, cap at 1);
- the Pearson statistic re-derived from the textbook Σ(O−E)²/E formula.

## Loophole hunt — found and closed

- **L4 (real bug, fixed):** passing the target as its own feature
  crashed deep inside pandas with an unreadable buffer error. The
  executor's column filter prevented it in pipeline runs, but
  `run_inference` is a public unit surface. Now a clean refusal, with
  duplicate-feature entries refused alongside (they would double-count
  a column in the BH family). Regression tests committed.
- **L1 verified:** alpha is live, not decorative — a 99% interval is
  wider than a 95% interval on the same data.
- **L2 verified:** NaN drops are counted per test (`n_dropped_nan`),
  never silent.
- **L3 verified:** numeric binary targets (0/1) flow through the
  disclosed positive-class rule as strings.
- **L5 verified:** a one-level categorical is skipped with a reason
  while the rest of the suite still runs.
- **L6 verified + regression:** findings are row-order invariant —
  the same data shuffled produces the same hash.
- **L7 verified:** significance flags mirror the BH-adjusted p at the
  alpha boundary exactly (statsmodels `reject` is authoritative).
- **L8 verified:** digit-bearing column and level names ("tier 2
  segment", "plan 99") flow through; the narrative wraps every such
  reference in backticks, keeping the injected-numbers claims scan
  clean.
- **L9 verified:** an all-NaN feature yields a feasibility stop, not a
  crash.
- **L10 verified + regression:** Wilson bounds stay inside [0, 1] at
  the k=0 extreme — precisely where the Wald interval would go
  negative (the Brown/Cai/DasGupta point, demonstrated by test).
- **L11 (real bug, fixed):** the CI workflow installed
  `.[dev,ml,docs]` but not the new `stats` extra — every step-15 test
  would have failed on a missing scipy/statsmodels the moment this was
  pushed. Fixed to `.[dev,ml,docs,stats]` and verified by a fresh-venv
  clean-checkout simulation before commit (the step-12 precedent).
- **Narrative injected-numbers audit:** the new Statistical evidence
  section was itself hunted — "step 15", "ASA 2016", and method names
  containing digits (`pearson_chi2_no_correction`) would have violated
  charter 4.1's scan; prose was reworded and references backticked
  BEFORE the end-to-end test could pass. The e2e suite proves the
  section survives `verify_artifact_numbers`.

## What was built

- `src/delivery_engine/stats.py` — the inference module (unit surface
  `run_inference`).
- `playbook.py` — `StageKind.STATS`, `KNOWN_STAT_TESTS`, `stat_test`
  stage key, `[stats] alpha` parsing, rule V14.
- `executor.py` — `_run_stats_stage`, the step-10 runner pattern:
  disclosed target selection, feasibility-only gating, hashed findings,
  audit entry naming the semantics.
- `artifacts.py` — the narrative report's Statistical evidence section:
  every figure injected, every reference backticked, and the closing
  sentence the whole step stands on: *significance informed, and never
  gated, this pipeline.*
- `playbooks/segment_comparison.toml` — the fifth archetype.
- `pyproject.toml` — the `[stats]` extra (scipy, statsmodels).
- `tests/test_step15.py` — 34 tests: planted answers, V14
  constitution, executor semantics, end-to-end, loophole regressions.

## Open items (declared, not hidden)

- Simultaneous confidence bands (the per-level Wilson intervals are
  individual, and say so in the findings).
- Change-point detection for the ops_review CHANGE step — a natural
  step 16 candidate.
- Non-CSV sources for the stats stage (the model-stage v1 line,
  applied consistently).
