"""delivery_engine.mathkit - the universal descriptive math stage.

Step 17. The stats stage (step 15) answers "is this difference real?";
this stage answers "what is the SHAPE of every column?" - skewness,
kurtosis, tail percentiles, robust outliers, distribution fit, entropy,
temporal gaps and trends - deterministically, over the columns the
human approved at Human Gate 1, hashed into the Findings Store, and
narrated (never computed) by AI stages. It requires no target column,
so it runs on ANY dataset the planner can classify.

Every method traced to a primary source:

- Sample skewness G1 and excess kurtosis G2, bias-adjusted (Joanes &
  Gill, "Comparing measures of sample skewness and kurtosis", The
  Statistician 47(1), 1998 - the adjusted estimators scipy exposes as
  bias=False and pandas/Excel use by default). Implementation:
  scipy.stats.skew / scipy.stats.kurtosis with bias=False.

- t-interval for the mean (scipy.stats.t.interval with the standard
  error of the mean; the classical construction in the NIST/SEMATECH
  e-Handbook, sec. 7.2.2.1). Confidence fixed at 95% - a declared
  constant of the check, recorded in the findings; small samples
  (n < 30) carry a note that the interval leans on approximate
  normality of the mean.

- Empirical tail percentiles p95 / p99 (numpy.percentile, the
  documented default linear interpolation, pinned explicitly). In risk
  contexts these are the historical-simulation VaR levels (Jorion,
  Value at Risk, 3rd ed.); the findings use the neutral name and note
  the risk reading.

- Robust outlier detection by the MAD modified z-score: M_i = 0.6745 *
  (x_i - median) / MAD, flagged when |M_i| > 3.5 (Iglewicz & Hoban,
  "How to Detect and Handle Outliers", ASQC 1993, as recommended by the
  NIST/SEMATECH e-Handbook). When MAD == 0 (a majority-constant
  column), the check is SKIPPED WITH A REASON - the score is undefined
  and the engine says so rather than dividing by zero or improvising a
  fallback.

- Distribution fit with the estimated-parameter correction - THE
  design fix of this step. A Kolmogorov-Smirnov p-value is INVALID
  when the tested distribution's parameters were estimated from the
  same sample (Lilliefors, JASA 62(318), 1967). Therefore: normality
  and lognormality are tested with the proper Lilliefors test
  (statsmodels.stats.diagnostic.lilliefors; lognormality = Lilliefors
  on log(x) for strictly positive x). Weibull has no standard
  Lilliefors table, so the engine reports its fitted parameters
  (scipy.stats.weibull_min.fit, deterministic MLE) and the KS DISTANCE
  AS A FIT-QUALITY METRIC EXPLICITLY WITHOUT A P-VALUE, with the
  reason recorded in the findings. "Best fit" is the candidate with
  the smallest KS distance - a disclosed selection rule, not a
  significance claim.

- Shannon entropy in bits, H = -sum(p * log2 p) (Shannon, "A
  Mathematical Theory of Communication", Bell System Technical
  Journal, 1948), plus normalized entropy H / log2(k) and rare
  categories below a fixed, disclosed 1% frequency threshold.

- Temporal structure: maximum gap in days between consecutive distinct
  dates, and the linear trend of daily row counts via
  scipy.stats.linregress (classical simple regression; its p-value is
  valid - no parameters of the null are estimated from the data).

Constitutional posture (rule V15):

- The playbook declares WHICH checks run (math_checks, from a fixed
  list); the engine never improvises a method.
- Columns come from the plan's classified kinds, approved at Human
  Gate 1 - never auto-detected behind the human's back.
- All thresholds (MAD 3.5, rare 1%, CI 95%, percentile method) are
  fixed constants DISCLOSED INSIDE THE FINDINGS, chosen here and
  never after seeing results.
- Findings never gate; feasibility does. Skips carry written reasons;
  an all-skipped stage produced nothing and fails feasibility.
- 6-decimal rounding before hashing (the step-10 contract).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Final

from delivery_engine.playbook import KNOWN_MATH_CHECKS as KNOWN_MATH_CHECKS

__all__ = ["KNOWN_MATH_CHECKS", "MathError", "run_math"]

MATH_DECIMALS: Final[int] = 6
MAD_SCALE: Final[float] = 0.6745        # Iglewicz & Hoban / NIST
MAD_THRESHOLD: Final[float] = 3.5       # Iglewicz & Hoban / NIST
RARE_FREQ: Final[float] = 0.01          # disclosed rare-category cutoff
CI_CONFIDENCE: Final[float] = 0.95      # declared constant of the check
MIN_N: Final[int] = 8                   # below this, shape stats are noise
SMALL_N_NOTE: Final[int] = 30


class MathError(Exception):
    """A math-stage problem, stated cleanly: what, where, what to do."""


def _require_libs() -> None:
    try:
        import scipy  # noqa: F401
        import statsmodels  # noqa: F401
    except ImportError:
        raise MathError(
            "The descriptive math stage requires scipy and statsmodels. "
            "Install them with: pip install 'delivery-engine[stats]'. A "
            "must_pass stage fails loudly on a missing dependency; it "
            "never silently skips."
        ) from None


def _round(x: float) -> float:
    return round(float(x), MATH_DECIMALS)


def _numeric_shape(x: Any) -> dict[str, Any]:
    import numpy as np
    from scipy import stats as sps

    n = len(x)
    mean = float(np.mean(x))
    entry: dict[str, Any] = {
        "n": n,
        "mean": _round(mean),
        "median": _round(float(np.median(x))),
        "std_sample": _round(float(np.std(x, ddof=1))),
        "skewness_g1_adjusted": _round(float(sps.skew(x, bias=False))),
        "excess_kurtosis_g2_adjusted": _round(
            float(sps.kurtosis(x, fisher=True, bias=False))
        ),
        "p95": _round(float(np.percentile(x, 95, method="linear"))),
        "p99": _round(float(np.percentile(x, 99, method="linear"))),
        "percentile_method": "linear (numpy documented default, pinned)",
        "tail_note": (
            "p95/p99 are empirical tail percentiles; in risk contexts "
            "these are the historical-simulation VaR levels (Jorion)"
        ),
    }
    sem = float(sps.sem(x, ddof=1))
    if sem > 0:
        lo, hi = sps.t.interval(CI_CONFIDENCE, df=n - 1, loc=mean,
                                scale=sem)
        entry["mean_ci_low"] = _round(float(lo))
        entry["mean_ci_high"] = _round(float(hi))
        entry["mean_ci_confidence"] = CI_CONFIDENCE
        entry["mean_ci_method"] = (
            "t-interval (NIST/SEMATECH e-Handbook 7.2.2.1)"
        )
        if n < SMALL_N_NOTE:
            entry["mean_ci_note"] = (
                f"n={n} < {SMALL_N_NOTE}: the interval leans on "
                f"approximate normality of the sample mean"
            )
    return entry


def _mad_outliers(x: Any) -> dict[str, Any] | None:
    """Returns the outlier entry, or None when MAD == 0 (undefined)."""
    import numpy as np

    med = float(np.median(x))
    mad = float(np.median(np.abs(x - med)))
    if mad == 0.0:
        return None
    mod_z = MAD_SCALE * (x - med) / mad
    flagged = int((abs(mod_z) > MAD_THRESHOLD).sum())
    return {
        "method": "MAD modified z-score (Iglewicz & Hoban 1993; NIST)",
        "scale_factor": MAD_SCALE,
        "threshold": MAD_THRESHOLD,
        "median": _round(med),
        "mad": _round(mad),
        "outlier_count": flagged,
        "outlier_share": _round(flagged / len(x)),
    }


def _distribution_fit(x: Any) -> dict[str, Any]:
    """Lilliefors for normal/lognormal; Weibull KS distance without a
    p-value (estimated parameters invalidate the KS p - Lilliefors
    1967). Best fit = smallest KS distance, a disclosed rule."""
    import numpy as np
    from scipy import stats as sps
    from statsmodels.stats.diagnostic import lilliefors

    candidates: dict[str, dict[str, Any]] = {}

    d_norm, p_norm = lilliefors(x, dist="norm")
    candidates["normal"] = {
        "ks_distance": _round(float(d_norm)),
        "lilliefors_p": _round(float(p_norm)),
        "params": {"loc": _round(float(np.mean(x))),
                   "scale": _round(float(np.std(x, ddof=1)))},
    }

    if float(np.min(x)) > 0:
        logx = np.log(x)
        d_ln, p_ln = lilliefors(logx, dist="norm")
        candidates["lognormal"] = {
            "ks_distance": _round(float(d_ln)),
            "lilliefors_p": _round(float(p_ln)),
            "params": {"log_loc": _round(float(np.mean(logx))),
                       "log_scale": _round(float(np.std(logx, ddof=1)))},
            "note": "Lilliefors applied to log(x) (x strictly positive)",
        }
        try:
            shape, loc, scale = sps.weibull_min.fit(x, floc=0.0)
            d_wb = float(sps.kstest(
                x, "weibull_min", args=(shape, loc, scale)
            ).statistic)
            candidates["weibull"] = {
                "ks_distance": _round(d_wb),
                "params": {"shape": _round(float(shape)),
                           "loc": 0.0,
                           "scale": _round(float(scale))},
                "p_value_omitted_reason": (
                    "KS p-values are invalid when parameters are "
                    "estimated from the same sample (Lilliefors 1967) "
                    "and no standard Lilliefors table exists for the "
                    "Weibull; the distance is reported as a fit-quality "
                    "metric only"
                ),
            }
        except Exception as exc:
            candidates["weibull_fit_failed"] = {
                "ks_distance": 1.0,  # worst possible - never best fit
                "reason": f"MLE fit did not converge: {exc}"[:200],
            }

    best = min(candidates, key=lambda k: candidates[k]["ks_distance"])
    return {
        "candidates": candidates,
        "best_fit": best,
        "best_fit_rule": (
            "smallest KS distance among the fitted candidates - a "
            "disclosed selection rule, not a significance claim"
        ),
    }


def _categorical_entropy(values: Any) -> dict[str, Any]:
    counts = values.value_counts()
    n = int(counts.sum())
    k = len(counts)
    probs = [c / n for c in counts]
    h = -sum(p * math.log2(p) for p in probs if p > 0)
    rare = sorted(
        str(level) for level, c in counts.items() if c / n < RARE_FREQ
    )
    return {
        "n": n,
        "distinct": k,
        "entropy_bits": _round(h),
        "entropy_normalized": _round(h / math.log2(k)) if k > 1 else 0.0,
        "entropy_source": "Shannon 1948, base 2",
        "rare_threshold": RARE_FREQ,
        "rare_categories": rare[:25],
        "rare_count": len(rare),
    }


def _temporal(dates: Any) -> dict[str, Any] | None:
    """Gap and trend over a timestamp column; None when < 3 distinct
    days (no structure to measure)."""
    import numpy as np
    import pandas as pd
    from scipy import stats as sps

    days = pd.to_datetime(dates, errors="coerce").dropna().dt.normalize()
    if days.nunique() < 3:
        return None
    per_day = days.value_counts().sort_index()
    distinct = per_day.index
    gaps = np.diff(distinct.values).astype("timedelta64[D]").astype(int)
    day_index = (
        (distinct - distinct[0]).days.to_numpy(dtype=float)
    )
    counts = per_day.to_numpy(dtype=float)
    entry: dict[str, Any] = {
        "first_day": str(distinct[0].date()),
        "last_day": str(distinct[-1].date()),
        "distinct_days": len(distinct),
        "max_gap_days": int(gaps.max()) if len(gaps) else 0,
        "trend_method": (
            "scipy.stats.linregress on day index vs daily row count"
        ),
    }
    if float(np.std(counts)) == 0.0:
        # Constant daily counts: the slope is exactly 0 and Pearson's
        # r is mathematically undefined (0/0). A NaN in hashed evidence
        # is a lie of precision - the engine records the definition.
        entry["trend_slope_rows_per_day"] = 0.0
        entry["trend_r_undefined_reason"] = (
            "daily counts are constant; the correlation coefficient is "
            "undefined (zero variance in y)"
        )
    else:
        reg = sps.linregress(day_index, counts)
        entry["trend_slope_rows_per_day"] = _round(float(reg.slope))
        entry["trend_r"] = _round(float(reg.rvalue))
        entry["trend_p"] = _round(float(reg.pvalue))
    return entry


def run_math(
    source: str,
    math_checks: str,
    numeric_features: list[str],
    categorical_features: list[str],
    timestamp_features: list[str],
) -> dict[str, Any]:
    """Runs the declared descriptive suite; returns findings for the
    store. Columns arrive from the plan's classified kinds - the same
    classification the human approved at Human Gate 1. Same source +
    same plan -> same findings -> same hash."""
    _require_libs()
    import pandas as pd

    if math_checks not in KNOWN_MATH_CHECKS:
        raise MathError(
            f"Unknown math_checks '{math_checks}'. "
            f"Valid: {sorted(KNOWN_MATH_CHECKS)}."
        )
    path = Path(source)
    # Step 20: the single reader (see delivery_engine.sources).
    from delivery_engine.sources import SourceError, load_dataframe

    try:
        df = load_dataframe(str(path))
    except SourceError as exc:
        raise MathError(str(exc)) from exc

    feats = [*numeric_features, *categorical_features, *timestamp_features]
    if len(feats) != len(set(feats)):
        dupes = sorted({c for c in feats if feats.count(c) > 1})
        raise MathError(
            f"Duplicate feature column(s) {dupes} - each column is "
            f"profiled once."
        )
    for col in feats:
        if col not in df.columns:
            raise MathError(
                f"Column '{col}' from the approved plan does not exist "
                f"in the source. The source changed after planning - "
                f"re-profile and re-plan."
            )

    findings: dict[str, Any] = {
        "math_checks": math_checks,
        "constants": {
            "mad_scale": MAD_SCALE,
            "mad_threshold": MAD_THRESHOLD,
            "rare_frequency": RARE_FREQ,
            "ci_confidence": CI_CONFIDENCE,
            "min_n": MIN_N,
            "note": (
                "all thresholds are fixed constants of the method, "
                "declared here and never chosen after seeing results"
            ),
        },
        "numeric": {},
        "outliers": {},
        "distribution_fit": {},
        "categorical": {},
        "temporal": {},
        "skipped": [],
    }
    # Step 20 (H1): if the single reader found timezone-aware columns,
    # the caveat travels into the hashed findings - day-level results
    # are computed on UTC calendar days, and the analyst sees that here
    # rather than in a review.
    tz_note = df.attrs.get("timezone_note")
    if tz_note:
        findings["source_timezone_note"] = tz_note

    def want(check: str) -> bool:
        return math_checks in (check, "all")

    for col in numeric_features:
        x = df[col].dropna().astype(float).to_numpy()
        n = len(x)
        if n < MIN_N:
            findings["skipped"].append({
                "what": f"numeric {col}",
                "reason": f"n={n} < MIN_N={MIN_N}: shape statistics on "
                          f"this few points are noise",
            })
            continue
        if float(pd.Series(x).nunique()) <= 1:
            findings["skipped"].append({
                "what": f"numeric {col}",
                "reason": "column has no variation",
            })
            continue
        n_dropped = int(len(df) - n)
        if want("numeric_shape"):
            entry = _numeric_shape(x)
            entry["n_dropped_nan"] = n_dropped
            findings["numeric"][col] = entry
        if want("outliers"):
            out = _mad_outliers(x)
            if out is None:
                findings["skipped"].append({
                    "what": f"outliers {col}",
                    "reason": "MAD is zero (majority-constant column); "
                              "the modified z-score is undefined "
                              "(Iglewicz & Hoban)",
                })
            else:
                findings["outliers"][col] = out
        if want("distribution_fit"):
            findings["distribution_fit"][col] = _distribution_fit(x)

    if want("categorical_entropy"):
        for col in categorical_features:
            vals = df[col].dropna().astype(str)
            if len(vals) == 0:
                findings["skipped"].append({
                    "what": f"categorical {col}",
                    "reason": "no non-null values",
                })
                continue
            entry = _categorical_entropy(vals)
            entry["n_dropped_nan"] = int(len(df) - len(vals))
            findings["categorical"][col] = entry

    if want("temporal"):
        for col in timestamp_features:
            t = _temporal(df[col])
            if t is None:
                findings["skipped"].append({
                    "what": f"temporal {col}",
                    "reason": "fewer than 3 distinct days - no gap or "
                              "trend structure to measure",
                })
            else:
                import pandas as pd

                parsed = pd.to_datetime(df[col], errors="coerce")
                t["n_dropped_unparseable_or_nan"] = int(
                    parsed.isna().sum()
                )
                findings["temporal"][col] = t

    produced = any(
        findings[k] for k in
        ("numeric", "outliers", "distribution_fit", "categorical",
         "temporal")
    )
    if not produced:
        skips = "; ".join(
            f"{s['what']}: {s['reason']}" for s in findings["skipped"]
        ) or "no candidate columns for the declared checks"
        raise MathError(
            f"No descriptive findings could be produced ({skips}). A "
            f"math stage that computed nothing has no findings to seal "
            f"- this is a feasibility failure."
        )
    return findings
