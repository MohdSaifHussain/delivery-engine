"""delivery_engine.stats - the deterministic statistical inference stage.

Step 15. The engine's findings so far are DESCRIPTIVE (counts, rates,
metrics). This stage upgrades them to INFERENTIAL: is a difference real,
how uncertain is a rate - computed deterministically, hashed into the
Findings Store, and narrated (never computed) by AI stages.

Every method choice is traced to a primary source:

- Wilson score interval for proportions, NOT the Wald interval.
  Brown, Cai & DasGupta, "Interval Estimation for a Binomial
  Proportion", Statistical Science 16(2), 2001, document the Wald
  interval's erratic coverage; the NIST/SEMATECH e-Handbook of
  Statistical Methods (sec. 7.2.4.1) recommends score-based intervals.
  Implementation: statsmodels.stats.proportion.proportion_confint(
  method="wilson") - statsmodels official documentation.

- Fisher's exact test for 2x2 contingency tables (scipy.stats
  .fisher_exact, official scipy documentation): exact p-value, no
  large-sample approximation, which sidesteps the Yates-correction
  debate entirely for the 2x2 case.

- Pearson chi-square test of independence for r x c tables larger than
  2x2 (scipy.stats.chi2_contingency, correction=False - Yates'
  correction applies only to 2x2 per scipy's own documentation).
  Validity per Cochran's rule as stated in the NIST/SEMATECH
  e-Handbook: no expected frequency below 1 and at least 80% of
  expected frequencies >= 5. Violations never silently pass - the
  finding carries cochran_rule_met = false.

- Cramer's V as the contingency effect size, computed from the Pearson
  statistic (correction=False) for every table: V = sqrt(chi2 / (n *
  (min(r, c) - 1))). Reported ALWAYS alongside the p-value: the ASA
  Statement on p-values (Wasserstein & Lazar, The American
  Statistician 70(2), 2016, principle 5) - a p-value does not measure
  the size of an effect.

- Mann-Whitney U for numeric two-group comparison (scipy.stats
  .mannwhitneyu, alternative="two-sided", method="auto" - scipy picks
  the exact distribution for small untied samples, the corrected
  normal approximation otherwise; the choice is a deterministic
  function of the data). Non-parametric BY DESIGN: v1 refuses to offer
  the parametric t-test at all, because it would demand a normality
  assumption the engine cannot certify - the same
  refusal-with-rationale posture as OpsKit's Simpson's-paradox refusal
  on averages. Effect size: rank-biserial correlation r = 1 - 2U/(n1
  * n2) (Kerby, "The simple difference formula", Comprehensive
  Psychology, 2014).

- Benjamini-Hochberg false-discovery-rate control across ALL hypothesis
  tests the stage runs (Benjamini & Hochberg, JRSS-B 57(1), 1995;
  implementation statsmodels.stats.multitest.multipletests(
  method="fdr_bh")). Running many uncorrected tests is the classic
  analyst loophole; the stage closes it structurally.

Constitutional posture (mirrors the model stage, step 10):

- ALPHA IS PRE-REGISTERED. It comes from the playbook's [stats] table,
  approved with the plan at Human Gate 1 - chosen before anyone has
  seen a p-value. It is recorded in the hashed findings.
- SIGNIFICANCE NEVER GATES. Feasibility failures (missing columns,
  degenerate data, nothing testable) stop a must_pass stage; p-values
  never do. A pipeline that stops or proceeds on significance is
  p-hacking machinery, and the engine refuses to be one.
- Skipped tests are RECORDED with reasons, never silent. If every
  candidate test is skipped, the stage has produced no inference and
  fails feasibility.
- All floats are rounded to 6 decimal places before storing (the
  step-10 contract): same data -> same findings -> same hash.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Final

# The declared test suites a playbook may request (rule V14) live in
# the constitution - delivery_engine.playbook - as the single source of
# truth (the KNOWN_KIT_TOOLS precedent). Re-exported here for unit use.
from delivery_engine.playbook import KNOWN_STAT_TESTS as KNOWN_STAT_TESTS

__all__ = ["KNOWN_STAT_TESTS", "StatsError", "run_inference"]

ALPHA_DEFAULT: Final[float] = 0.05
STAT_DECIMALS: Final[int] = 6
MIN_GROUP_N: Final[int] = 5          # smallest group size worth testing
COCHRAN_MIN_EXPECTED: Final[float] = 1.0
COCHRAN_SHARE_GE_5: Final[float] = 0.8
MDE_POWER: Final[float] = 0.8            # step 18: declared power for MDE
GROUPING_MIN_DISTINCT: Final[int] = 20   # step 18: pseudoreplication scan
GROUPING_MIN_REPEAT: Final[float] = 5.0  # avg rows per group to flag



class StatsError(Exception):
    """A stats-stage problem, stated cleanly: what, where, what to do."""


def _require_libs() -> None:
    try:
        import scipy  # noqa: F401
        import statsmodels  # noqa: F401
    except ImportError:
        raise StatsError(
            "The statistical inference stage requires scipy and "
            "statsmodels. Install them with: pip install "
            "'delivery-engine[stats]'. A must_pass stage fails loudly on "
            "a missing dependency; it never silently skips."
        ) from None


def _round(x: float) -> float:
    return round(float(x), STAT_DECIMALS)


def _positive_class(levels: list[str]) -> str:
    """Disclosed deterministic rule: the lexicographically LAST of the
    two observed levels is the positive class. Not a guess - the rule
    and both levels are recorded in the findings, and the AI narrative
    names them."""
    return sorted(levels)[1]


def _wilson(count: int, nobs: int, alpha: float) -> tuple[float, float]:
    from statsmodels.stats.proportion import proportion_confint

    lo, hi = proportion_confint(count, nobs, alpha=alpha, method="wilson")
    return _round(float(lo)), _round(float(hi))


def _cramers_v(table: Any) -> float:
    """Cramer's V from the Pearson statistic, correction=False."""
    from scipy.stats import chi2_contingency

    chi2, _, _, _ = chi2_contingency(table, correction=False)
    n = float(table.to_numpy().sum())
    r, c = table.shape
    k = min(r, c) - 1
    if n <= 0 or k <= 0:
        return 0.0
    return _round(float((chi2 / (n * k)) ** 0.5))


def _mde_two_group(n1: int, n2: int, alpha: float) -> dict[str, Any]:
    """Step 18 (G3): the minimum detectable effect at the pre-registered
    alpha and declared power - the honest companion to every p-value.
    Low-power analyses inflate both false negatives and false positives
    (Button et al. via the reproducibility literature), and a
    'not significant' without an MDE invites the misreading 'no effect'.

    Closed forms, normal approximation:
    - proportions: MDE in Cohen's h units, h = (z_{1-a/2} + z_power) *
      sqrt(1/n1 + 1/n2) (Cohen, Statistical Power Analysis, 1988)
    - Mann-Whitney: MDE in rank-biserial units via the large-sample
      normal approximation of U: r = (z_{1-a/2} + z_power) *
      sqrt((n1 + n2 + 1) / (3 * n1 * n2))
    Deterministic: z from the standard normal quantile function.
    """
    from scipy.stats import norm

    z = float(norm.ppf(1 - alpha / 2.0)) + float(norm.ppf(MDE_POWER))
    return {
        "power": MDE_POWER,
        "mde_cohens_h": _round(z * (1.0 / n1 + 1.0 / n2) ** 0.5),
        "mde_rank_biserial": _round(
            z * ((n1 + n2 + 1) / (3.0 * n1 * n2)) ** 0.5
        ),
        "note": (
            "smallest effect this test could reliably detect at the "
            "pre-registered alpha and the declared power; a "
            "non-significant result rules out effects above this size, "
            "not the existence of an effect"
        ),
    }


def run_inference(
    source: str,
    stat_test: str,
    target: str,
    categorical_features: list[str],
    numeric_features: list[str],
    alpha: float,
) -> dict[str, Any]:
    """Runs the declared inference suite; returns findings for the store.

    Column selection is NOT made here: target and features arrive from
    the plan's classified kinds - the same classification the human
    approved at Human Gate 1 (the step-10 pattern). Same source + same
    plan + same alpha -> same findings -> same hash.
    """
    _require_libs()
    import pandas as pd

    if stat_test not in KNOWN_STAT_TESTS:
        raise StatsError(
            f"Unknown stat_test '{stat_test}'. "
            f"Valid: {sorted(KNOWN_STAT_TESTS)}."
        )
    if not (0.0 < alpha < 1.0):
        raise StatsError(
            f"alpha must be strictly between 0 and 1; got {alpha}. Alpha "
            f"is pre-registered in the playbook's [stats] table and "
            f"approved at Human Gate 1."
        )

    path = Path(source)
    if not path.exists():
        raise StatsError(f"Source not found: {path}")
    if path.suffix.lower() != ".csv":
        raise StatsError(
            f"Statistical inference v1 runs on CSV sources only; got "
            f"'{path.suffix}'. Other source types are a declared future "
            f"extension, not a silent failure."
        )
    df = pd.read_csv(path)

    # Loophole L4 (step 15 hunt): testing the target against itself is
    # circular nonsense that would otherwise die deep inside pandas with
    # an unreadable error. Refused cleanly, and duplicate feature
    # entries with it.
    feats = [*categorical_features, *numeric_features]
    if target in feats:
        raise StatsError(
            f"Target '{target}' is also listed as a feature - a column "
            f"cannot be tested for association with itself. The executor "
            f"excludes the target from features; a direct caller must too."
        )
    if len(feats) != len(set(feats)):
        dupes = sorted({c for c in feats if feats.count(c) > 1})
        raise StatsError(
            f"Duplicate feature column(s) {dupes} - each column is "
            f"tested once; duplicates would double-count it in the "
            f"Benjamini-Hochberg family."
        )

    for col in [target, *categorical_features, *numeric_features]:
        if col not in df.columns:
            raise StatsError(
                f"Column '{col}' from the approved plan does not exist in "
                f"the source. The source changed after planning - "
                f"re-profile and re-plan."
            )

    tgt = df[target].dropna().astype(str)
    levels = sorted(tgt.unique().tolist())
    if len(levels) != 2:
        raise StatsError(
            f"Target '{target}' has {len(levels)} non-null distinct "
            f"values; inference v1 requires exactly 2 (the plan "
            f"classified it binary_target - the source may have changed)."
        )
    positive = _positive_class(levels)

    findings: dict[str, Any] = {
        "stat_test": stat_test,
        "alpha": _round(alpha),
        "alpha_provenance": (
            "pre-registered in the playbook [stats] table; approved with "
            "the plan at Human Gate 1, before any p-value was computed"
        ),
        "target": target,
        "target_levels": levels,
        "positive_class": positive,
        "positive_class_rule": (
            "lexicographically last of the two observed levels - a "
            "disclosed deterministic rule, not a guess"
        ),
        "methods": {
            "proportion_interval": (
                "Wilson score (Brown, Cai & DasGupta 2001; NIST/SEMATECH "
                "e-Handbook 7.2.4.1; statsmodels proportion_confint)"
            ),
            "contingency_2x2": "Fisher exact test (scipy.stats.fisher_exact)",
            "contingency_rxc": (
                "Pearson chi-square, correction=False "
                "(scipy.stats.chi2_contingency); validity per Cochran's "
                "rule (NIST/SEMATECH e-Handbook)"
            ),
            "numeric_two_group": (
                "Mann-Whitney U, two-sided, method='auto' "
                "(scipy.stats.mannwhitneyu); parametric t-test refused in "
                "v1 - normality is an assumption this engine cannot certify"
            ),
            "effect_sizes": (
                "Cramer's V (contingency), rank-biserial r (Mann-Whitney; "
                "Kerby 2014) - always reported alongside p (ASA Statement "
                "on p-values, 2016, principle 5)"
            ),
            "multiple_comparisons": (
                "Benjamini-Hochberg FDR across all hypothesis tests in "
                "this stage (Benjamini & Hochberg 1995; statsmodels "
                "multipletests fdr_bh)"
            ),
        },
        "proportions": [],
        "tests": [],
        "skipped": [],
    }

    want_props = stat_test in ("proportion_ci", "full_inference")
    want_chi2 = stat_test in ("chi2_independence", "full_inference")
    want_mwu = stat_test in ("mann_whitney", "full_inference")

    # ── Wilson intervals on the positive rate ────────────────────────────
    if want_props:
        n_all = len(tgt)
        k_all = int((tgt == positive).sum())
        lo, hi = _wilson(k_all, n_all, alpha)
        findings["proportions"].append({
            "scope": "overall",
            "n": n_all,
            "count_positive": k_all,
            "rate": _round(k_all / n_all),
            "ci_low": lo,
            "ci_high": hi,
            "confidence": _round(1.0 - alpha),
        })
        for col in categorical_features:
            sub = df[[col, target]].dropna().astype(str)
            for level in sorted(sub[col].unique().tolist()):
                grp = sub[sub[col] == level][target]
                n = len(grp)
                if n < MIN_GROUP_N:
                    findings["skipped"].append({
                        "what": f"proportion_ci {col}={level}",
                        "reason": f"group n={n} < MIN_GROUP_N={MIN_GROUP_N}",
                    })
                    continue
                k = int((grp == positive).sum())
                lo, hi = _wilson(k, n, alpha)
                findings["proportions"].append({
                    "scope": f"{col}={level}",
                    "n": n,
                    "count_positive": k,
                    "rate": _round(k / n),
                    "ci_low": lo,
                    "ci_high": hi,
                    "confidence": _round(1.0 - alpha),
                })
        findings["proportions_note"] = (
            "intervals are INDIVIDUAL (per-estimate) Wilson intervals, "
            "not simultaneous confidence bands - declared, not hidden"
        )

    # Hypothesis tests accumulate raw p-values here, then one BH pass.
    raw_p: list[float] = []

    # ── target x categorical: Fisher exact (2x2) / chi-square (r x c) ────
    if want_chi2:
        for col in categorical_features:
            sub = df[[col, target]].dropna().astype(str)
            table = pd.crosstab(sub[col], sub[target])
            r, c = table.shape
            n_used = int(table.to_numpy().sum())
            n_dropped = int(len(df) - len(sub))
            if r < 2 or c < 2:
                findings["skipped"].append({
                    "what": f"independence {target} x {col}",
                    "reason": f"table is {r}x{c}; a test needs >= 2 levels "
                              f"on both margins",
                })
                continue
            entry: dict[str, Any] = {
                "kind": "independence",
                "columns": [target, col],
                "table_shape": [r, c],
                "n_used": n_used,
                "n_dropped_nan": n_dropped,
                "effect_size_cramers_v": _cramers_v(table),
            }
            if (r, c) == (2, 2):
                from scipy.stats import fisher_exact

                odds, p = fisher_exact(table.to_numpy(), alternative="two-sided")
                entry["method"] = "fisher_exact_two_sided"
                entry["odds_ratio"] = _round(float(odds))
                entry["p_value"] = _round(float(p))
                margins = table.sum(axis=1).to_numpy()
                mde = _mde_two_group(int(margins[0]), int(margins[1]),
                                     alpha)
                entry["mde"] = {"power": mde["power"],
                                "cohens_h": mde["mde_cohens_h"],
                                "note": mde["note"]}
            else:
                from scipy.stats import chi2_contingency

                chi2, p, dof, expected = chi2_contingency(
                    table, correction=False
                )
                exp = expected.ravel()
                cochran = bool(
                    exp.min() >= COCHRAN_MIN_EXPECTED
                    and (exp >= 5).mean() >= COCHRAN_SHARE_GE_5
                )
                entry["method"] = "pearson_chi2_no_correction"
                entry["chi2"] = _round(float(chi2))
                entry["dof"] = int(dof)
                entry["p_value"] = _round(float(p))
                entry["cochran_rule_met"] = cochran
                if not cochran:
                    entry["validity_warning"] = (
                        "expected frequencies violate Cochran's rule "
                        "(NIST/SEMATECH); the asymptotic p-value is "
                        "unreliable for this table"
                    )
            raw_p.append(float(entry["p_value"]))
            findings["tests"].append(entry)

    # ── target groups x numeric: Mann-Whitney U ──────────────────────────
    if want_mwu:
        for col in numeric_features:
            sub = df[[col, target]].dropna()
            g_lo = sub[sub[target].astype(str) == levels[0]][col]
            g_hi = sub[sub[target].astype(str) == levels[1]][col]
            n1, n2 = len(g_lo), len(g_hi)
            if n1 < MIN_GROUP_N or n2 < MIN_GROUP_N:
                findings["skipped"].append({
                    "what": f"mann_whitney {col} by {target}",
                    "reason": f"group sizes {n1}/{n2}; both must be >= "
                              f"MIN_GROUP_N={MIN_GROUP_N}",
                })
                continue
            if float(sub[col].nunique()) <= 1:
                findings["skipped"].append({
                    "what": f"mann_whitney {col} by {target}",
                    "reason": "column has no variation (a constant "
                              "cannot separate groups)",
                })
                continue
            from scipy.stats import mannwhitneyu

            res = mannwhitneyu(
                g_lo, g_hi, alternative="two-sided", method="auto"
            )
            u = float(res.statistic)
            rank_biserial = _round(1.0 - (2.0 * u) / (n1 * n2))
            findings["tests"].append({
                "kind": "mann_whitney",
                "columns": [target, col],
                "groups": {levels[0]: n1, levels[1]: n2},
                "n_dropped_nan": int(len(df) - len(sub)),
                "method": "mann_whitney_u_two_sided_auto",
                "u_statistic": _round(u),
                "p_value": _round(float(res.pvalue)),
                "effect_size_rank_biserial": rank_biserial,
                "median_" + levels[0]: _round(float(g_lo.median())),
                "median_" + levels[1]: _round(float(g_hi.median())),
                "mde": {
                    "power": (_m := _mde_two_group(n1, n2, alpha))["power"],
                    "rank_biserial": _m["mde_rank_biserial"],
                    "note": _m["note"],
                },
            })
            raw_p.append(float(res.pvalue))

    # ── one Benjamini-Hochberg family across every test this stage ran ───
    if raw_p:
        from statsmodels.stats.multitest import multipletests

        reject, p_adj, _, _ = multipletests(
            raw_p, alpha=alpha, method="fdr_bh"
        )
        for entry, adj, rej in zip(findings["tests"], p_adj, reject,
                                   strict=True):
            entry["p_adjusted_bh"] = _round(float(adj))
            entry["significant_at_alpha"] = bool(rej)
        findings["bh_family_size"] = len(raw_p)
        findings["bh_note"] = (
            "significance flags use Benjamini-Hochberg-adjusted p-values "
            "across the full family of tests this stage ran; raw p-values "
            "are reported for re-performance, never for the flag. A "
            "reported 0.0 means the value is below the 6-decimal rounding "
            "contract's resolution (p < 1e-06), not literally zero."
        )

    ran_anything = bool(findings["proportions"] or findings["tests"])
    if not ran_anything:
        skips = "; ".join(
            f"{s['what']}: {s['reason']}" for s in findings["skipped"]
        ) or "no candidate columns"
        raise StatsError(
            f"No inference could be produced ({skips}). A stats stage "
            f"that computed nothing has no findings to seal - this is a "
            f"feasibility failure, not a statistical judgment."
        )
    return findings
