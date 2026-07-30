"""delivery_engine.model - the deterministic baseline model stage.

Charter v0.6 conscious amendment: the original diagram placed "Baseline
Model" under the bounded AI slots ("code generated, run
deterministically"). v1 deliberately goes further: NO code is generated.
Training a baseline classifier over columns the planner already
classified is a deterministic problem wearing an AI costume (the charter
4.6 lesson, applied again). The strongest sandbox is executing no
generated code at all - section 11's sandboxing question is answered by
deferral: custom AI-authored training code, if it ever arrives, comes
behind Human Gate 2 like drafted rules do.

Determinism, sourced: scikit-learn's own common-pitfalls documentation
(scikit-learn.org/stable/common_pitfalls.html, "Controlling randomness")
states that for reproducible results across executions every
random_state=None must be removed, and passing INTEGERS is the safest,
preferred option. Both the stratified splitter and the estimator here
take the same fixed integer seed, and the seed is recorded in the
findings so a reviewer can re-perform training exactly.

The injected-numbers rule holds by construction: this module computes
metrics deterministically and returns them as findings for the store.
No AI stage computes anything; AI may only narrate these findings later.

Metrics are rounded to 6 decimal places before storing: enough precision
for any honest comparison, and it removes last-bit float flutter across
BLAS builds so same-environment re-performance reproduces the findings
hash exactly. The rounding is part of the declared contract, not a
hidden truncation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

__all__ = ["ModelError", "train_baseline"]

RANDOM_SEED: Final[int] = 42
TEST_SIZE: Final[float] = 0.25
METRIC_DECIMALS: Final[int] = 6
MIN_ROWS_PER_CLASS: Final[int] = 10
LEAKAGE_THRESHOLD: Final[float] = 0.95  # step 18: fixed, disclosed

# G3 fixed parameters — Cohen (1988) at power=0.8, alpha=0.05 two-tailed
G3_POWER: Final[float] = 0.8
G3_ALPHA: Final[float] = 0.05
G3_Z_ALPHA_HALF: Final[float] = 1.959963984540054  # norm.ppf(0.975)
G3_Z_BETA: Final[float] = 0.8416212335729143  # norm.ppf(0.8)


class ModelError(Exception):
    """A model-stage problem, stated cleanly: what, where, what to do."""


def _require_sklearn() -> Any:
    try:
        import sklearn

        return sklearn
    except ImportError:
        raise ModelError(
            "The baseline model stage requires scikit-learn. Install it "
            "with: pip install 'delivery-engine[ml]' (or pip install "
            "scikit-learn). A must_pass stage fails loudly on a missing "
            "dependency; it never silently skips."
        ) from None


def train_baseline(
    source: str,
    target: str,
    numeric_features: list[str],
    categorical_features: list[str],
    metric_ci: bool = False,
    alpha: float = 0.05,
    alpha_source: str = "engine_default_disclosed",
    split: str = "random",
    n_splits: int = 5,
    ordering_column: str | None = None,
) -> dict[str, Any]:
    """Trains the deterministic baseline classifier; returns findings.

    Pipeline (all against scikit-learn official documentation):
    stratified train_test_split(test_size=0.25, random_state=42) ->
    ColumnTransformer(OneHotEncoder(handle_unknown='ignore') over
    categoricals, passthrough numerics) -> LogisticRegression(
    max_iter=1000, random_state=42). Metrics: accuracy, precision,
    recall, f1, roc_auc, plus class balance and split sizes.

    Same source + same classified columns -> same findings -> same hash.

    metric_ci (step 24, Change 1): opt-in, default False. When False,
    findings are byte-identical to before this parameter existed. When
    True, adds Wilson score confidence intervals (Brown, Cai & DasGupta
    2001) for recall and precision - the same interval the stats stage
    uses (delivery_engine.stats.wilson_interval; Single-Reader
    Principle, step 20), so a point estimate from a handful of positive
    cases is not read as more precise than it is. alpha/alpha_source are
    resolved by the executor: the playbook's pre-registered [stats]
    alpha when a stats stage exists, else a disclosed engine default.

    split (step 24, Change 2): "random" (default) is byte-identical to
    before this parameter existed - the stratified split above, unused
    by any other branch. "time_ordered" sorts ascending by
    ordering_column (a stable sort - ties keep their original row
    order, so ordering is deterministic, never silently arbitrary) and
    holds out the last TEST_SIZE fraction as test, no shuffle, no
    stratify: a fab (or any time-ordered process) deploys forward in
    time, and a random split measures something deployment never
    experiences. "walk_forward" runs
    sklearn.model_selection.TimeSeriesSplit(n_splits) over the same
    time-ordered rows, fitting and evaluating a fresh pipeline per fold;
    findings carry every fold's train/test size, positive count and
    metrics, plus a mean/min/max summary - the range sits structurally
    beside the mean so a consumer cannot read the average alone and
    miss a fold that caught nothing. ordering_column is supplied by the
    executor from the plan's classified timestamp_column - never
    guessed, never row order.
    """
    _require_sklearn()
    import numpy as np
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder

    path = Path(source)
    # Step 20: the single reader (delivery_engine.sources -> the kit's
    # DuckDB loader, the same one the profile gate used). CSV, Parquet,
    # .xlsx and SQLite all arrive here; the loader's refusals are loud
    # and specific, and are re-raised in this stage's voice.
    from delivery_engine.sources import SourceError, load_dataframe

    try:
        df = load_dataframe(str(path))
    except SourceError as exc:
        raise ModelError(str(exc)) from exc

    for col in [target, *numeric_features, *categorical_features]:
        if col not in df.columns:
            raise ModelError(
                f"Column '{col}' from the approved plan does not exist in "
                f"the source. The source changed after planning - "
                f"re-profile and re-plan."
            )
    if ordering_column is not None and ordering_column not in df.columns:
        raise ModelError(
            f"ordering_column '{ordering_column}' from the approved plan "
            f"does not exist in the source. The source changed after "
            f"planning - re-profile and re-plan."
        )
    features = [*numeric_features, *categorical_features]
    if not features:
        raise ModelError(
            "No feature columns available: the plan classified no numeric "
            "or categorical columns besides the target. A baseline needs "
            "at least one feature."
        )

    used = [target, *features]
    if ordering_column is not None:
        used = [*used, ordering_column]
    before = len(df)
    df = df.dropna(subset=used)
    n_dropped = before - len(df)
    if len(df) < 4 * MIN_ROWS_PER_CLASS:
        raise ModelError(
            f"After dropping {n_dropped} row(s) with nulls in the used "
            f"columns, only {len(df)} row(s) remain - too few to train. "
            f"Fix completeness first (that is what the DQ gates are for)."
        )

    y_raw = df[target]
    classes = sorted(y_raw.dropna().astype(str).unique().tolist())
    if len(classes) != 2:
        raise ModelError(
            f"Baseline classification requires exactly 2 classes in "
            f"'{target}'; found {len(classes)}: {classes[:5]}. A "
            f"single-class or multi-class target cannot train this "
            f"baseline."
        )
    y = (y_raw.astype(str) == classes[1]).astype(int)

    # ── Step 18 (G1): the target-leakage sentinel. Found in production:
    # a post-hoc label column (fraud_type) rode into the features and
    # produced AUC 1.0 - a perfect score that meant nothing. For every
    # feature, compute a deterministic association with the target:
    # Cramér's V for categoricals (Pearson chi-square by the textbook
    # formula), absolute point-biserial correlation for numerics. Any
    # association >= LEAKAGE_THRESHOLD (a fixed, disclosed constant) is
    # recorded as a possible_target_leakage warning in the hashed
    # findings and echoed by the narrative's Limitations section. The
    # warning NEVER gates - near-perfect association can be legitimate
    # (a duplicate encoding is not always leakage), so the judgment
    # stays human; the engine's job is to make the pattern impossible
    # to miss.
    leakage_warnings: list[dict[str, object]] = []
    y_bin = y.to_numpy(dtype=float)
    for col in categorical_features:
        table = pd.crosstab(df[col].astype(str), df[target].astype(str))
        obs = table.to_numpy(dtype=float)
        n_tot = obs.sum()
        if n_tot <= 0 or min(obs.shape) < 2:
            continue
        row_m = obs.sum(axis=1, keepdims=True)
        col_m = obs.sum(axis=0, keepdims=True)
        exp = row_m @ col_m / n_tot
        with np.errstate(divide="ignore", invalid="ignore"):
            cells = np.where(exp > 0, (obs - exp) ** 2 / exp, 0.0)
        chi2 = float(cells.sum())
        k = min(obs.shape) - 1
        v = float((chi2 / (n_tot * k)) ** 0.5) if k > 0 else 0.0
        if v >= LEAKAGE_THRESHOLD:
            leakage_warnings.append(
                {
                    "feature": col,
                    "measure": "cramers_v",
                    "association": round(v, 6),
                }
            )
    for col in numeric_features:
        x = df[col].astype(float).to_numpy()
        if np.std(x) == 0.0 or np.std(y_bin) == 0.0:
            continue
        r = abs(float(np.corrcoef(x, y_bin)[0, 1]))
        if r >= LEAKAGE_THRESHOLD:
            leakage_warnings.append(
                {
                    "feature": col,
                    "measure": "abs_point_biserial",
                    "association": round(r, 6),
                }
            )
    counts = y.value_counts()
    if int(counts.min()) < MIN_ROWS_PER_CLASS:
        raise ModelError(
            f"Minority class has {int(counts.min())} row(s); the baseline "
            f"requires at least {MIN_ROWS_PER_CLASS} per class for a "
            f"meaningful stratified split."
        )

    if split not in ("random", "time_ordered", "walk_forward"):
        raise ModelError(
            f"Unknown split '{split}'. Valid: random, time_ordered, "
            f"walk_forward."
        )

    def _r(v: float) -> float:
        return round(float(v), METRIC_DECIMALS)

    def _fit_score(
        x_tr: Any, y_tr: Any, x_te: Any, y_te: Any
    ) -> tuple[Any, Any, dict[str, float]]:
        pre = ColumnTransformer(
            transformers=[
                ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
            ],
            remainder="passthrough",  # numerics pass through untouched
        )
        clf = Pipeline(
            [
                ("prep", pre),
                ("model", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)),
            ]
        )
        clf.fit(x_tr, y_tr)
        y_pr = clf.predict(x_te)
        y_pb = clf.predict_proba(x_te)[:, 1]
        return y_pr, y_pb, {
            "accuracy": _r(accuracy_score(y_te, y_pr)),
            "precision": _r(precision_score(y_te, y_pr, zero_division=0)),
            "recall": _r(recall_score(y_te, y_pr, zero_division=0)),
            "f1": _r(f1_score(y_te, y_pr, zero_division=0)),
            "roc_auc": _r(roc_auc_score(y_te, y_pb)),
        }

    # ── Step 24 (Change 2): evaluation-split honesty. "random" below is
    # byte-identical to the pre-step-24 code path - untouched, still the
    # only branch that runs by default. "time_ordered" and
    # "walk_forward" are opt-in and require ordering_column (the plan's
    # classified timestamp_column, supplied by the executor - never
    # guessed, never row order).
    metrics: dict[str, float]
    folds: list[dict[str, Any]] | None = None
    fold_metrics_summary: dict[str, Any] | None = None
    y_test_for_ci: Any = None
    y_pred_for_ci: Any = None
    n_train_out: int | None = None
    n_test_out: int | None = None

    if split == "random":
        x = df[features]
        x_train, x_test, y_train, y_test = train_test_split(
            x,
            y,
            test_size=TEST_SIZE,
            random_state=RANDOM_SEED,
            stratify=y,
        )
        y_pred, _y_prob, metrics = _fit_score(x_train, y_train, x_test, y_test)
        split_desc = "stratified"
        n_train_out, n_test_out = len(x_train), len(x_test)
        g_test_n = len(x_test)
        y_test_for_ci, y_pred_for_ci = y_test, y_pred

    elif split == "time_ordered":
        if ordering_column is None:
            raise ModelError(
                "split = 'time_ordered' requires the plan to classify a "
                "timestamp_column; none was supplied. Re-plan against a "
                "source with a classified timestamp column, or declare "
                "split = 'random' (the default)."
            )
        # Stable sort: ties keep their original row order, so ordering
        # is deterministic - never silently arbitrary (step-24 hunt H4).
        ordered = df.sort_values(ordering_column, kind="stable")
        n_train_rows = round(len(ordered) * (1.0 - TEST_SIZE))
        train_rows, test_rows = ordered.iloc[:n_train_rows], ordered.iloc[n_train_rows:]
        x_train = train_rows[features]
        y_train = (train_rows[target].astype(str) == classes[1]).astype(int)
        x_test = test_rows[features]
        y_test = (test_rows[target].astype(str) == classes[1]).astype(int)
        if y_train.nunique() < 2 or y_test.nunique() < 2:
            raise ModelError(
                f"split = 'time_ordered' (sorted ascending by "
                f"'{ordering_column}', first {1.0 - TEST_SIZE:.0%} train / "
                f"remainder test) produced a train or test portion with "
                f"only one class present - no metrics can be computed. "
                f"Try split = 'random', or a larger / more balanced "
                f"dataset."
            )
        y_pred, _y_prob, metrics = _fit_score(x_train, y_train, x_test, y_test)
        split_desc = "time_ordered"
        n_train_out, n_test_out = len(x_train), len(x_test)
        g_test_n = len(x_test)
        y_test_for_ci, y_pred_for_ci = y_test, y_pred

    else:  # walk_forward
        if ordering_column is None:
            raise ModelError(
                "split = 'walk_forward' requires the plan to classify a "
                "timestamp_column; none was supplied. Re-plan against a "
                "source with a classified timestamp column, or declare "
                "split = 'random' (the default)."
            )
        from sklearn.model_selection import TimeSeriesSplit

        ordered = df.sort_values(ordering_column, kind="stable").reset_index(drop=True)
        x_all = ordered[features]
        y_all = (ordered[target].astype(str) == classes[1]).astype(int)

        fold_records: list[dict[str, Any]] = []
        collected: dict[str, list[float]] = {
            m: [] for m in ("accuracy", "precision", "recall", "f1", "roc_auc")
        }
        last_test: Any = None
        last_pred: Any = None
        for i, (tr_idx, te_idx) in enumerate(
            TimeSeriesSplit(n_splits=n_splits).split(x_all), start=1
        ):
            x_tr, x_te = x_all.iloc[tr_idx], x_all.iloc[te_idx]
            y_tr, y_te = y_all.iloc[tr_idx], y_all.iloc[te_idx]
            record: dict[str, Any] = {
                "fold": i,
                "train_size": len(x_tr),
                "test_size": len(x_te),
                "n_positives": int(y_te.sum()),
            }
            # Step 24 hunt H3: a fold whose train or test portion holds a
            # single class is a disclosed skip, never a divide-by-zero
            # and never a silent 0.0 standing in for an undefined metric.
            if y_tr.nunique() < 2:
                record["skipped"] = True
                record["reason"] = (
                    "this fold's training portion contains a single "
                    "class - cannot fit a binary classifier"
                )
                fold_records.append(record)
                continue
            if y_te.nunique() < 2:
                record["skipped"] = True
                record["reason"] = (
                    f"this fold's test portion contains a single class "
                    f"({int(y_te.sum())} positive case(s)) - recall, "
                    f"precision and roc_auc are undefined; no metrics "
                    f"are fabricated"
                )
                fold_records.append(record)
                continue
            y_pred_f, _y_prob_f, fold_metrics = _fit_score(x_tr, y_tr, x_te, y_te)
            record["metrics"] = fold_metrics
            fold_records.append(record)
            for k, v in fold_metrics.items():
                collected[k].append(v)
            last_test, last_pred = y_te, y_pred_f

        if not collected["accuracy"]:
            raise ModelError(
                f"split = 'walk_forward' with n_splits={n_splits} produced "
                f"no usable fold - every fold's train or test portion "
                f"contained a single class. Reduce n_splits, use a "
                f"larger dataset, or use split = 'random'."
            )

        # The range sits structurally beside the mean in the SAME dict
        # (step-24 hunt H5): a consumer reading fold_metrics_summary
        # cannot see the mean without also seeing min and max.
        fold_metrics_summary = {
            k: {
                "mean": _r(sum(vals) / len(vals)),
                "min": _r(min(vals)),
                "max": _r(max(vals)),
            }
            for k, vals in collected.items()
        }
        folds = fold_records
        split_desc = "time_series_walk_forward"
        g_test_n = sum(
            r["test_size"] for r in fold_records if not r.get("skipped")
        )
        y_test_for_ci, y_pred_for_ci = last_test, last_pred
        metrics = {}  # no single metrics dict for walk_forward; see folds

    # G2's detail prose names the split by its old fixed description for
    # "random" (byte-identical to pre-step-24 output); the two opt-in
    # modes get an accurate description instead of a stale one.
    g2_detail = (
        "The stratified split treats each row as an independent "
        "statistical unit. If rows share grouping structure (repeated "
        "measures, clustered sampling, time-series autocorrelation) "
        "the effective sample size is smaller than n_test and reported "
        "metrics will overstate generalisation. The engine cannot "
        "detect grouping from a flat source; the human reviewer must "
        "confirm independence."
    ) if split == "random" else (
        f"The {split_desc} split treats each row as an independent "
        f"statistical unit. If rows share grouping structure (repeated "
        f"measures, clustered sampling, time-series autocorrelation) "
        f"the effective sample size is smaller than "
        f"assumed_independent_units and reported metrics will overstate "
        f"generalisation. The engine cannot detect grouping from a flat "
        f"source; the human reviewer must confirm independence."
    )

    findings: dict[str, Any] = {
        "model": "LogisticRegression(max_iter=1000)",
        "library": "scikit-learn",
        "random_seed": RANDOM_SEED,
        "test_size": TEST_SIZE,
        "split": split_desc,
        "target": target,
        "positive_class": classes[1],
        "negative_class": classes[0],
        "numeric_features": sorted(numeric_features),
        "leakage_threshold": LEAKAGE_THRESHOLD,
        "leakage_warnings": sorted(leakage_warnings, key=lambda w: str(w["feature"])),
        "leakage_check": (
            "per-feature association with the target (Cramér's V for "
            "categoricals, absolute point-biserial for numerics); "
            "associations at or above the fixed threshold are flagged "
            "possible_target_leakage - a warning for human judgment, "
            "never a gate. Motivated by a production run where a "
            "post-hoc label column produced a perfect score."
        ),
        "categorical_features": sorted(categorical_features),
        "n_rows_dropped_nulls": int(n_dropped),
        "class_balance_positive": _r(float(y.mean())),
        "note": (
            "Deterministic baseline: fixed integer seeds on splitter and "
            "estimator per scikit-learn's controlling-randomness guidance; "
            "metrics rounded to 6 decimals as a declared contract. This is "
            "a reference point for human modeling work, not a delivered "
            "model."
        ),
        # ── G2: pseudoreplication disclosure (Forstmeier et al. 2017) ────────
        # The split assumes row independence. If rows share a grouping
        # structure (repeated measures, clustered sampling, autocorrelated
        # time series) the effective sample size is smaller than the
        # figure below and reported metrics overstate generalisation. The
        # engine cannot detect grouping from a flat source; human judgment
        # is required. Disclosure only — never a gate.
        "g2_pseudoreplication": {
            "warning": "pseudoreplication_risk",
            "reference": ("Forstmeier, Wagenmakers & Parker (2017) Proc. R. Soc. B 284:20152463"),
            "assumed_independent_units": g_test_n,
            "detail": g2_detail,
            "gate": False,
        },
        # ── G3: minimum detectable effect (Cohen 1988, power=0.8, alpha=0.05) ──
        # One-sample formula: h = (z_alpha/2 + z_beta) / sqrt(n_test). Effect
        # sizes smaller than mde_cohen_h cannot be reliably distinguished from
        # chance at the given test-set size. Disclosure only — never a gate.
        "g3_minimum_detectable_effect": {
            "disclosure": "minimum_detectable_effect",
            "reference": (
                "Cohen, J. (1988) Statistical Power Analysis for the Behavioral Sciences (2nd ed.)."
            ),
            "power": G3_POWER,
            "alpha": G3_ALPHA,
            "formula": "h = (z_alpha_half + z_beta) / sqrt(n_test)",
            "z_alpha_half": G3_Z_ALPHA_HALF,
            "z_beta": G3_Z_BETA,
            "n_test": g_test_n,
            "mde_cohen_h": _r((G3_Z_ALPHA_HALF + G3_Z_BETA) / (g_test_n ** 0.5)),
            "detail": (
                "With n_test independent observations the minimum "
                "Cohen's h detectable at power=0.8 and alpha=0.05 "
                "(two-tailed) is mde_cohen_h. Effect sizes smaller "
                "than this threshold cannot be reliably distinguished "
                "from chance at the given sample size. "
                "Disclosure only — never a gate."
            ),
            "gate": False,
        },
    }

    # split != "random" is opt-in; these keys are therefore absent (and
    # findings byte-identical to pre-step-24 output) unless a playbook
    # actually declares a non-default split.
    if split != "random":
        findings["split_mode"] = split
    if ordering_column is not None:
        findings["ordering_column"] = ordering_column
    if split == "walk_forward":
        findings["n_splits"] = n_splits
        findings["folds"] = folds
        findings["fold_metrics_summary"] = fold_metrics_summary
    else:
        findings["n_train"] = n_train_out
        findings["n_test"] = n_test_out
        findings["metrics"] = metrics

    # ── Step 24 (Change 1): metric confidence intervals - opt-in, adds
    # NOTHING to findings when metric_ci is False (byte-identical to
    # pre-step-24 output).
    if metric_ci:
        findings.update(
            _metric_ci_block(
                y_test_for_ci.to_numpy(), y_pred_for_ci, alpha, alpha_source
            )
        )

    return findings


def _metric_ci_block(
    y_test_arr: Any, y_pred: Any, alpha: float, alpha_source: str
) -> dict[str, Any]:
    """Wilson score confidence intervals for recall and precision (step
    24, Change 1) - the same failure G3 exists to prevent one layer up:
    a point estimate from a handful of positive cases (recall's
    TP/n_positives_in_test) can look precise while being highly
    uncertain. Reuses stats.wilson_interval - the Single-Reader
    Principle applied to a statistic (step 20) - so this is not a
    second implementation of the Wilson interval. A zero denominator
    (no positive cases, or the model predicted none) is a disclosed
    skip, never a crash and never a fabricated interval.

    Factored out of train_baseline so it is independently testable
    against planted array counts, including the zero-positive
    degenerate case a real stratified split structurally avoids.
    """
    from delivery_engine.stats import wilson_interval

    def _r(v: float) -> float:
        return round(float(v), METRIC_DECIMALS)

    n_pos_test = int((y_test_arr == 1).sum())
    n_pred_pos = int((y_pred == 1).sum())
    tp = int(((y_test_arr == 1) & (y_pred == 1)).sum())

    skipped: list[dict[str, str]] = []
    recall_ci: dict[str, float] | None
    precision_ci: dict[str, float] | None

    if n_pos_test == 0:
        recall_ci = None
        skipped.append({
            "what": "recall_ci95",
            "reason": (
                "zero positive cases in the test set (0/0) - recall is "
                "undefined; no confidence interval can be computed, and "
                "none is fabricated"
            ),
        })
    else:
        lo, hi = wilson_interval(tp, n_pos_test, alpha)
        recall_ci = {"ci_low": lo, "ci_high": hi}

    if n_pred_pos == 0:
        precision_ci = None
        skipped.append({
            "what": "precision_ci95",
            "reason": (
                "the model predicted zero positive cases in the test "
                "set (0/0) - precision is undefined; no confidence "
                "interval can be computed, and none is fabricated"
            ),
        })
    else:
        lo, hi = wilson_interval(tp, n_pred_pos, alpha)
        precision_ci = {"ci_low": lo, "ci_high": hi}

    return {
        "n_positives_in_test": n_pos_test,
        "recall_ci95": recall_ci,
        "precision_ci95": precision_ci,
        "metric_ci_alpha": _r(alpha),
        "metric_ci_alpha_source": alpha_source,
        "metric_ci_skipped": skipped,
        "metric_ci_caveat": (
            f"recall and precision above carry Wilson score 95% "
            f"confidence intervals (Brown, Cai & DasGupta 2001) at "
            f"alpha={_r(alpha)} ({alpha_source}); recall was estimated "
            f"from {n_pos_test} positive case(s) in the test set - a "
            f"point estimate from a small count can look precise while "
            f"remaining highly uncertain."
        ),
    }
