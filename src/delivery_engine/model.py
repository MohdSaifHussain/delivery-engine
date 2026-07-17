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
LEAKAGE_THRESHOLD: Final[float] = 0.95   # step 18: fixed, disclosed


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
) -> dict[str, Any]:
    """Trains the deterministic baseline classifier; returns findings.

    Pipeline (all against scikit-learn official documentation):
    stratified train_test_split(test_size=0.25, random_state=42) ->
    ColumnTransformer(OneHotEncoder(handle_unknown='ignore') over
    categoricals, passthrough numerics) -> LogisticRegression(
    max_iter=1000, random_state=42). Metrics: accuracy, precision,
    recall, f1, roc_auc, plus class balance and split sizes.

    Same source + same classified columns -> same findings -> same hash.
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
    if not path.exists():
        raise ModelError(f"Source not found: {path}")
    if path.suffix.lower() != ".csv":
        raise ModelError(
            f"Baseline model v1 trains on CSV sources only; got "
            f"'{path.suffix}'. Other source types are a declared future "
            f"extension, not a silent failure."
        )
    df = pd.read_csv(path)

    for col in [target, *numeric_features, *categorical_features]:
        if col not in df.columns:
            raise ModelError(
                f"Column '{col}' from the approved plan does not exist in "
                f"the source. The source changed after planning - "
                f"re-profile and re-plan."
            )
    features = [*numeric_features, *categorical_features]
    if not features:
        raise ModelError(
            "No feature columns available: the plan classified no numeric "
            "or categorical columns besides the target. A baseline needs "
            "at least one feature."
        )

    used = [target, *features]
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
            leakage_warnings.append({
                "feature": col,
                "measure": "cramers_v",
                "association": round(v, 6),
            })
    for col in numeric_features:
        x = df[col].astype(float).to_numpy()
        if np.std(x) == 0.0 or np.std(y_bin) == 0.0:
            continue
        r = abs(float(np.corrcoef(x, y_bin)[0, 1]))
        if r >= LEAKAGE_THRESHOLD:
            leakage_warnings.append({
                "feature": col,
                "measure": "abs_point_biserial",
                "association": round(r, 6),
            })
    counts = y.value_counts()
    if int(counts.min()) < MIN_ROWS_PER_CLASS:
        raise ModelError(
            f"Minority class has {int(counts.min())} row(s); the baseline "
            f"requires at least {MIN_ROWS_PER_CLASS} per class for a "
            f"meaningful stratified split."
        )

    x = df[features]
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=y,
    )

    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"),
             categorical_features),
        ],
        remainder="passthrough",   # numerics pass through untouched
    )
    clf = Pipeline([
        ("prep", pre),
        ("model", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)),
    ])
    clf.fit(x_train, y_train)
    y_pred = clf.predict(x_test)
    y_prob = clf.predict_proba(x_test)[:, 1]

    def _r(v: float) -> float:
        return round(float(v), METRIC_DECIMALS)

    return {
        "model": "LogisticRegression(max_iter=1000)",
        "library": "scikit-learn",
        "random_seed": RANDOM_SEED,
        "test_size": TEST_SIZE,
        "split": "stratified",
        "target": target,
        "positive_class": classes[1],
        "negative_class": classes[0],
        "numeric_features": sorted(numeric_features),
        "leakage_threshold": LEAKAGE_THRESHOLD,
        "leakage_warnings": sorted(
            leakage_warnings, key=lambda w: str(w["feature"])
        ),
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
        "n_train": len(x_train),
        "n_test": len(x_test),
        "class_balance_positive": _r(float(y.mean())),
        "metrics": {
            "accuracy": _r(accuracy_score(y_test, y_pred)),
            "precision": _r(precision_score(y_test, y_pred, zero_division=0)),
            "recall": _r(recall_score(y_test, y_pred, zero_division=0)),
            "f1": _r(f1_score(y_test, y_pred, zero_division=0)),
            "roc_auc": _r(roc_auc_score(y_test, y_prob)),
        },
        "note": (
            "Deterministic baseline: fixed integer seeds on splitter and "
            "estimator per scikit-learn's controlling-randomness guidance; "
            "metrics rounded to 6 decimals as a declared contract. This is "
            "a reference point for human modeling work, not a delivered "
            "model."
        ),
    }
