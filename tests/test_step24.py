"""Step 24 tests — model-stage evidence honesty.

STEP24_DECISIONS.md is the spec. Three changes, each opt-in except the
bug fix (Change 3, which has no schema key and is a correctness fix for
every dataset with digit-bearing column names):

- Change 3 (this phase): identifier-aware injected-numbers scanning -
  verify_artifact_numbers must not misread a digit-bearing column name
  (e.g. sensor_060) as an unprovenanced numeric claim, while still
  catching a bare literal like "p95" and a fabricated bare percentage.
- Change 1 (planned): metric confidence intervals for the model stage
  (metric_ci, opt-in).
- Change 2 (planned): evaluation-split honesty (split / n_splits, opt-in).

Planted-answer discipline throughout (CLAUDE.md §7): fixtures contain
known issues, tests verify exactly those are found.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine import approve_plan, load_playbook, make_plan, run
from delivery_engine.executor import ExecutionStopped
from delivery_engine.playbook import PlaybookError
from delivery_engine.store import (
    FindingsStore,
    NumberInjector,
    StoreError,
    verify_artifact_numbers,
)

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
SEGMENT = PLAYBOOKS / "segment_comparison.toml"


def _csv(path: Path, header: list[str], rows: list[list[Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


# ── Change 3: identifier-aware injected-numbers scanning (unit level) ───────


class TestIdentifierAwareScanningUnit:
    """Direct tests of the masking rule in store.py, isolated from the
    executor/pipeline machinery."""

    def test_known_digit_bearing_identifier_does_not_raise(self) -> None:
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        text = "Column sensor_060 failed 17 validation rules."
        # sensor_060 is masked (known, non-digit-only); the bare "17" is
        # still unprovenanced and must still raise.
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers(text, injector)

    def test_known_digit_bearing_identifier_alone_does_not_raise(self) -> None:
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        text = "Column sensor_060 was profiled with no other claims."
        verify_artifact_numbers(text, injector)  # must not raise

    def test_p95_still_raises(self) -> None:
        """The reason the allowlist design was chosen over a regex
        loosening (STEP24_DECISIONS §5, test 10): a bare 'p95' that is
        NOT a known column name must still be caught, exactly as step
        17's amendment celebrates."""
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        text = "Latency reached p95 during the window."
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers(text, injector)

    def test_bare_fabricated_percentage_still_raises(self) -> None:
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        text = "Churn rate was 42.7% this quarter."
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers(text, injector)

    def test_column_named_95_cannot_launder_a_bare_95(self) -> None:
        """A column literally named '95' is an adversarial known
        identifier that is ALL digits. The non-digit requirement means
        it is never masked, so it cannot become a laundering channel
        for an arbitrary bare figure elsewhere in the text."""
        store = FindingsStore()
        injector = NumberInjector(store, known_identifiers=frozenset({"95"}))
        text = "The rate hit 95 last week."
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers(text, injector)

    def test_no_known_identifiers_is_unchanged_behaviour(self) -> None:
        """Default known_identifiers is empty - byte-identical scanning
        behaviour to before step 24 for any caller that does not opt in."""
        store = FindingsStore()
        injector = NumberInjector(store)
        assert injector.known_identifiers == frozenset()
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers("sensor_060 misbehaved.", injector)

    def test_partial_token_match_is_not_masked(self) -> None:
        """The identifier must match the WHOLE token, not a substring -
        'sensor_060x' is a different token and is not exempted."""
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers("Column sensor_060x failed.", injector)


# ── Change 3: end-to-end through the executor (the real crash site) ─────────


def _digit_named_column_csv(path: Path, rows: int = 200) -> Path:
    """customer_id, converted, segment, sensor_060 - the last column's
    name is exactly the shape (letters + underscore + digits) that
    crashed verify_artifact_numbers before this step: 'sensor_060'
    appears bare (no backticks) in the exception-listing line of
    build_narrative_report when a validate rule against it fails."""
    out = []
    for i in range(rows):
        seg = "a" if i % 2 == 0 else "b"
        threshold = 8 if seg == "a" else 1
        conv = "yes" if i % 10 < threshold else "no"
        sensor = "" if i % 20 == 0 else f"{100.0 + i}"  # planted nulls
        out.append([f"C-{i:05d}", conv, seg, sensor])
    return _csv(
        path, ["customer_id", "converted", "segment", "sensor_060"], out
    )


def _approved_plan_for_digit_csv(src: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "segment comparison with statistical significance for the growth team",
        str(src),
        envelope["findings"],
        PLAYBOOKS,
    )
    return approve_plan(plan, "Saif")


class TestIdentifierAwareScanningEndToEnd:
    def test_digit_bearing_column_with_validate_failures_seals(
        self, tmp_path: Path
    ) -> None:
        src = _digit_named_column_csv(tmp_path / "sensors.csv")
        plan = _approved_plan_for_digit_csv(src)
        out = tmp_path / "pkg"
        rules = [{"column": "sensor_060", "rule": "not_null"}]
        approvals: dict[str, Any] = {"plan_approval": "Saif"}

        # Before step 24 this raised StoreError from inside the
        # narrative_report stage (the digits in "sensor_060" read as an
        # unprovenanced numeric claim) and the package never sealed.
        run(plan, load_playbook(SEGMENT), rules, out, approvals=approvals)

        assert (out / "manifest.json").exists()
        assert (out / "audit_log.jsonl").exists()
        narrative = (out / "narrative_report.md").read_text("utf-8")
        assert "sensor_060" in narrative

        validate = json.loads(
            (out / "findings" / "dq_validate.json").read_text("utf-8")
        )["findings"]
        assert validate["total_exceptions"] > 0  # the planted nulls were found


# ── Change 1: metric confidence intervals for the model stage ───────────────


def _model_ci_csv(path: Path, rows: int = 200) -> Path:
    """~20% positive rate, comfortably above MIN_ROWS_PER_CLASS after a
    stratified split - the natural case (nonzero test positives)."""
    out = []
    for i in range(rows):
        label = "yes" if i % 5 == 0 else "no"
        out.append([f"C-{i:05d}", label, float(i % 17), ("a", "b")[i % 2]])
    return _csv(path, ["customer_id", "converted", "num", "cat"], out)


class TestMetricCiUnit:
    """_metric_ci_block in isolation - planted array counts, including
    the zero-positive degenerate case a real stratified split
    structurally avoids (MIN_ROWS_PER_CLASS keeps every class >= 10)."""

    def test_known_positive_count_matches_wilson_interval_directly(self) -> None:
        from delivery_engine.model import _metric_ci_block
        from delivery_engine.stats import wilson_interval

        # 8 actual positives in the test set, 5 of them predicted correctly
        # (true positives); 2 false positives elsewhere.
        y_test = [1] * 8 + [0] * 22
        y_pred = [1] * 5 + [0] * 3 + [1] * 2 + [0] * 20
        import numpy as np

        block = _metric_ci_block(
            np.array(y_test), np.array(y_pred), 0.05, "engine_default_disclosed"
        )
        assert block["n_positives_in_test"] == 8
        tp = 5
        n_pred_pos = 7  # 5 true positives + 2 false positives
        expected_recall = wilson_interval(tp, 8, 0.05)
        expected_precision = wilson_interval(tp, n_pred_pos, 0.05)
        assert block["recall_ci95"] == {
            "ci_low": expected_recall[0], "ci_high": expected_recall[1],
        }
        assert block["precision_ci95"] == {
            "ci_low": expected_precision[0], "ci_high": expected_precision[1],
        }
        assert block["metric_ci_skipped"] == []

    def test_disclosed_alpha_and_source_recorded(self) -> None:
        import numpy as np

        from delivery_engine.model import _metric_ci_block

        block = _metric_ci_block(
            np.array([1, 1, 0, 0]), np.array([1, 0, 0, 0]),
            0.2, "pre_registered",
        )
        assert block["metric_ci_alpha"] == 0.2
        assert block["metric_ci_alpha_source"] == "pre_registered"
        assert "2 positive case" in block["metric_ci_caveat"]

    def test_zero_positives_in_test_is_disclosed_skip_not_crash(self) -> None:
        import numpy as np

        from delivery_engine.model import _metric_ci_block

        block = _metric_ci_block(
            np.array([0, 0, 0]), np.array([0, 0, 1]), 0.05,
            "engine_default_disclosed",
        )
        assert block["n_positives_in_test"] == 0
        assert block["recall_ci95"] is None
        reasons = {s["what"] for s in block["metric_ci_skipped"]}
        assert "recall_ci95" in reasons

    def test_zero_predicted_positives_is_disclosed_skip_not_crash(self) -> None:
        import numpy as np

        from delivery_engine.model import _metric_ci_block

        block = _metric_ci_block(
            np.array([1, 0, 0]), np.array([0, 0, 0]), 0.05,
            "engine_default_disclosed",
        )
        assert block["precision_ci95"] is None
        reasons = {s["what"] for s in block["metric_ci_skipped"]}
        assert "precision_ci95" in reasons


class TestMetricCiTrainBaseline:
    def test_metric_ci_false_adds_nothing(self, tmp_path: Path) -> None:
        from delivery_engine.model import train_baseline

        src = _model_ci_csv(tmp_path / "ci.csv")
        f_off = train_baseline(str(src), "converted", ["num"], ["cat"])
        f_on = train_baseline(
            str(src), "converted", ["num"], ["cat"], metric_ci=False
        )
        assert set(f_off) == set(f_on)  # explicit default == implicit default
        for key in (
            "n_positives_in_test", "recall_ci95", "precision_ci95",
            "metric_ci_alpha", "metric_ci_alpha_source", "metric_ci_skipped",
            "metric_ci_caveat",
        ):
            assert key not in f_off

    def test_metric_ci_true_adds_the_declared_keys(self, tmp_path: Path) -> None:
        from delivery_engine.model import train_baseline

        src = _model_ci_csv(tmp_path / "ci.csv")
        f = train_baseline(
            str(src), "converted", ["num"], ["cat"],
            metric_ci=True, alpha=0.05, alpha_source="engine_default_disclosed",
        )
        assert f["n_positives_in_test"] > 0
        assert f["recall_ci95"] is not None
        assert f["metric_ci_alpha"] == 0.05
        assert f["metric_ci_alpha_source"] == "engine_default_disclosed"


# ── Change 1: alpha resolution end to end through the executor ──────────────

_MODEL_CI_PLAYBOOK_NO_STATS = """\
schema_version = 1

[playbook]
name = "test_model_ci_no_stats"
version = "1.0.0"
description = "model stage with metric_ci and no stats stage in this playbook"

[requirements]
min_rows = 50
required_kinds = ["binary_target", "id_column"]
source_types = ["csv"]

[[stages]]
id = "dq_profile"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"

[[stages]]
id = "dq_validate"
kind = "kit"
tool = "analystkit_validate"
gate = "must_pass"
needs = ["dq_profile"]

[[stages]]
id = "plan_approval"
kind = "human_gate"
needs = ["dq_profile", "dq_validate"]

[[stages]]
id = "baseline"
kind = "model"
gate = "must_pass"
metric_ci = true
needs = ["dq_profile", "dq_validate", "plan_approval"]

[[stages]]
id = "package"
kind = "package"
needs = ["baseline"]

[deliverables]
artifacts = ["delivery_package", "audit_log", "manifest"]
"""

_MODEL_CI_PLAYBOOK_WITH_STATS = """\
schema_version = 1

[playbook]
name = "test_model_ci_with_stats"
version = "1.0.0"
description = "model stage with metric_ci alongside a pre-registered stats stage"

[requirements]
min_rows = 50
required_kinds = ["binary_target", "id_column"]
source_types = ["csv"]

[stats]
alpha = 0.2

[[stages]]
id = "dq_profile"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"

[[stages]]
id = "dq_validate"
kind = "kit"
tool = "analystkit_validate"
gate = "must_pass"
needs = ["dq_profile"]

[[stages]]
id = "plan_approval"
kind = "human_gate"
needs = ["dq_profile", "dq_validate"]

[[stages]]
id = "stats"
kind = "stats"
stat_test = "proportion_ci"
gate = "must_pass"
needs = ["dq_profile", "dq_validate", "plan_approval"]

[[stages]]
id = "baseline"
kind = "model"
gate = "must_pass"
metric_ci = true
needs = ["dq_profile", "dq_validate", "plan_approval"]

[[stages]]
id = "package"
kind = "package"
needs = ["baseline", "stats"]

[deliverables]
artifacts = ["delivery_package", "audit_log", "manifest"]
"""

_MODEL_CI_RULES = [{"column": "customer_id", "rule": "unique"}]
_MODEL_CI_APPROVALS: dict[str, Any] = {"plan_approval": "Saif"}


def _run_model_ci_playbook(tmp_path: Path, toml_text: str, name: str) -> Path:
    src = _model_ci_csv(tmp_path / "ci.csv")
    pb_dir = tmp_path / "pb_dir"
    pb_dir.mkdir()
    (pb_dir / f"{name}.toml").write_text(toml_text, encoding="utf-8")

    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "predict churn for the growth team", str(src),
        envelope["findings"], pb_dir,
    )
    plan = approve_plan(plan, "Saif")
    out = tmp_path / "pkg"
    run(
        plan, load_playbook(pb_dir / f"{name}.toml"), _MODEL_CI_RULES, out,
        approvals=_MODEL_CI_APPROVALS,
    )
    return out


class TestMetricCiAlphaResolutionEndToEnd:
    def test_no_stats_stage_uses_engine_default_disclosed(
        self, tmp_path: Path
    ) -> None:
        out = _run_model_ci_playbook(
            tmp_path, _MODEL_CI_PLAYBOOK_NO_STATS, "test_model_ci_no_stats"
        )
        f = json.loads(
            (out / "findings" / "baseline.json").read_text("utf-8")
        )["findings"]
        assert f["metric_ci_alpha_source"] == "engine_default_disclosed"
        assert f["metric_ci_alpha"] == 0.05

    def test_stats_stage_reuses_pre_registered_alpha(
        self, tmp_path: Path
    ) -> None:
        out = _run_model_ci_playbook(
            tmp_path, _MODEL_CI_PLAYBOOK_WITH_STATS, "test_model_ci_with_stats"
        )
        f = json.loads(
            (out / "findings" / "baseline.json").read_text("utf-8")
        )["findings"]
        assert f["metric_ci_alpha_source"] == "pre_registered"
        assert f["metric_ci_alpha"] == 0.2  # the playbook's [stats] alpha


# ── Change 2: evaluation-split honesty ───────────────────────────────────────


def _time_ordered_signal_csv(path: Path, rows: int = 300) -> Path:
    """Early period (first half): a small numeric feature (0-6)
    UNCORRELATED with the label (~20% positive, pseudo-random). Late
    period (second half): the same feature is a clean binary signal (0
    or 100) that fully determines the label. A model trained on the
    whole timeline learns the late-period signal; walk_forward's early
    folds - trained and evaluated only within the noise region - expose
    that the model is useless there. A random split blends both regions
    into one number and conceals it."""
    start = datetime(2024, 1, 1)
    out = []
    for i in range(rows):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        if i < rows // 2:
            feature = float(i % 7)
            label = "yes" if (i * 37) % 5 == 0 else "no"
        else:
            feature = 100.0 if i % 2 == 0 else 0.0
            label = "yes" if feature > 50 else "no"
        out.append([f"C-{i:05d}", day, label, feature])
    return _csv(
        path, ["customer_id", "signup_date", "converted", "feature"], out
    )


def _single_class_early_csv(path: Path, rows: int = 100) -> Path:
    """First 60% of the timeline is a single class ('no'); the tail
    alternates. With TimeSeriesSplit(n_splits=4) over 100 rows (fold
    boundaries at 20/40/60/80), the first three folds' TRAINING portions
    fall entirely inside the single-class prefix and are skipped; the
    fourth fold's training portion spans into the alternating tail and
    succeeds - both skip reasons (train-side and, for a shorter prefix,
    test-side) are exercised across the suite."""
    start = datetime(2024, 1, 1)
    out = []
    for i in range(rows):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        label = "no" if i < 60 else ("yes" if i % 2 == 0 else "no")
        out.append([f"C-{i:05d}", day, label, float(i)])
    return _csv(
        path, ["customer_id", "date_col", "converted", "feature"], out
    )


def _split_playbook_toml(
    name: str, split_value: str, n_splits: int | None = None
) -> str:
    n_splits_line = f"n_splits = {n_splits}\n" if n_splits is not None else ""
    return f"""\
schema_version = 1

[playbook]
name = "{name}"
version = "1.0.0"
description = "split honesty test playbook"

[requirements]
min_rows = 50
required_kinds = ["binary_target", "id_column"]
source_types = ["csv"]

[[stages]]
id = "dq_profile"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"

[[stages]]
id = "dq_validate"
kind = "kit"
tool = "analystkit_validate"
gate = "must_pass"
needs = ["dq_profile"]

[[stages]]
id = "plan_approval"
kind = "human_gate"
needs = ["dq_profile", "dq_validate"]

[[stages]]
id = "baseline"
kind = "model"
gate = "must_pass"
split = "{split_value}"
{n_splits_line}needs = ["dq_profile", "dq_validate", "plan_approval"]

[[stages]]
id = "package"
kind = "package"
needs = ["baseline"]

[deliverables]
artifacts = ["delivery_package", "audit_log", "manifest"]
"""


def _run_split_playbook(
    tmp_path: Path, toml_text: str, name: str, src: Path
) -> Path:
    pb_dir = tmp_path / f"pb_dir_{name}"
    pb_dir.mkdir()
    (pb_dir / f"{name}.toml").write_text(toml_text, encoding="utf-8")
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "predict churn for the growth team", str(src),
        envelope["findings"], pb_dir,
    )
    plan = approve_plan(plan, "Saif")
    out = tmp_path / f"pkg_{name}"
    run(
        plan, load_playbook(pb_dir / f"{name}.toml"), _MODEL_CI_RULES, out,
        approvals=_MODEL_CI_APPROVALS,
    )
    return out


class TestEvaluationSplitHonestyUnit:
    def test_time_ordered_adds_split_mode_and_ordering_column(
        self, tmp_path: Path
    ) -> None:
        from delivery_engine.model import train_baseline

        src = _time_ordered_signal_csv(tmp_path / "signal.csv")
        f = train_baseline(
            str(src), "converted", ["feature"], [],
            split="time_ordered", ordering_column="signup_date",
        )
        assert f["split_mode"] == "time_ordered"
        assert f["ordering_column"] == "signup_date"
        assert f["split"] == "time_ordered"
        assert "n_train" in f
        assert "n_test" in f
        assert "metrics" in f

    def test_random_default_has_no_new_keys(self, tmp_path: Path) -> None:
        from delivery_engine.model import train_baseline

        src = _time_ordered_signal_csv(tmp_path / "signal.csv")
        f = train_baseline(str(src), "converted", ["feature"], [])
        assert "split_mode" not in f
        assert "ordering_column" not in f
        assert "folds" not in f
        assert f["split"] == "stratified"

    def test_walk_forward_folds_deterministic_across_runs(
        self, tmp_path: Path
    ) -> None:
        from delivery_engine.model import train_baseline

        src = _time_ordered_signal_csv(tmp_path / "signal.csv")
        kwargs: dict[str, Any] = {
            "split": "walk_forward", "n_splits": 5,
            "ordering_column": "signup_date",
        }
        f1 = train_baseline(str(src), "converted", ["feature"], [], **kwargs)
        f2 = train_baseline(str(src), "converted", ["feature"], [], **kwargs)
        assert f1["folds"] == f2["folds"]
        assert f1["fold_metrics_summary"] == f2["fold_metrics_summary"]

    def test_fold_range_sits_structurally_beside_the_mean(
        self, tmp_path: Path
    ) -> None:
        """Step-24 hunt H5: a consumer reading fold_metrics_summary
        cannot see the mean without also seeing min and max - same dict,
        same level."""
        from delivery_engine.model import train_baseline

        src = _time_ordered_signal_csv(tmp_path / "signal.csv")
        f = train_baseline(
            str(src), "converted", ["feature"], [],
            split="walk_forward", n_splits=5, ordering_column="signup_date",
        )
        for metric_summary in f["fold_metrics_summary"].values():
            assert {"mean", "min", "max"} <= set(metric_summary)

    def test_single_class_folds_are_skipped_not_fabricated(
        self, tmp_path: Path
    ) -> None:
        """Step-24 hunt H3: a fold whose train or test portion holds a
        single class is a disclosed skip, never a divide-by-zero and
        never a silent 0.0 standing in for an undefined metric."""
        from delivery_engine.model import train_baseline

        src = _single_class_early_csv(tmp_path / "skew.csv")
        f = train_baseline(
            str(src), "converted", ["feature"], [],
            split="walk_forward", n_splits=4, ordering_column="date_col",
        )
        skipped = [r for r in f["folds"] if r.get("skipped")]
        successful = [r for r in f["folds"] if not r.get("skipped")]
        assert skipped
        assert successful
        for r in skipped:
            assert "reason" in r
            assert "metrics" not in r

    def test_all_folds_single_class_is_feasibility_failure(
        self, tmp_path: Path
    ) -> None:
        from delivery_engine.model import ModelError, train_baseline

        start = datetime(2024, 1, 1)
        rows = []
        for i in range(60):
            day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            label = "yes" if i < 12 else "no"  # positives ALL at the start
            rows.append([f"C-{i:05d}", day, label, float(i)])
        src = _csv(
            tmp_path / "allskip.csv",
            ["customer_id", "date_col", "converted", "feature"], rows,
        )
        with pytest.raises(ModelError, match="no usable fold"):
            train_baseline(
                str(src), "converted", ["feature"], [],
                split="walk_forward", n_splits=4, ordering_column="date_col",
            )


class TestSplitPlaybookValidation:
    def test_unknown_split_rejected(self, tmp_path: Path) -> None:
        pb = tmp_path / "bad.toml"
        pb.write_text(
            _split_playbook_toml("bad_split", "bogus"), encoding="utf-8"
        )
        with pytest.raises(PlaybookError, match="split"):
            load_playbook(pb)

    def test_n_splits_illegal_without_walk_forward(self, tmp_path: Path) -> None:
        pb = tmp_path / "bad2.toml"
        pb.write_text(
            _split_playbook_toml("bad_n_splits", "random", n_splits=3),
            encoding="utf-8",
        )
        with pytest.raises(PlaybookError, match="n_splits"):
            load_playbook(pb)

    def test_n_splits_too_small_rejected(self, tmp_path: Path) -> None:
        pb = tmp_path / "bad3.toml"
        pb.write_text(
            _split_playbook_toml("bad_n_splits2", "walk_forward", n_splits=1),
            encoding="utf-8",
        )
        with pytest.raises(PlaybookError, match="n_splits"):
            load_playbook(pb)


class TestEvaluationSplitHonestyEndToEnd:
    def test_time_ordered_without_timestamp_column_is_clean_refusal(
        self, tmp_path: Path
    ) -> None:
        src = _model_ci_csv(tmp_path / "no_dates.csv")  # no date-like column
        toml_text = _split_playbook_toml("split_no_ts", "time_ordered")
        pb_dir = tmp_path / "pb_dir_split_no_ts"
        pb_dir.mkdir()
        (pb_dir / "split_no_ts.toml").write_text(toml_text, encoding="utf-8")
        envelope = json.loads(tool_profile(str(src), None))
        plan = make_plan(
            "predict churn for the growth team", str(src),
            envelope["findings"], pb_dir,
        )
        plan = approve_plan(plan, "Saif")
        out = tmp_path / "pkg_split_no_ts"
        with pytest.raises(ExecutionStopped, match="timestamp_column"):
            run(
                plan, load_playbook(pb_dir / "split_no_ts.toml"),
                _MODEL_CI_RULES, out, approvals=_MODEL_CI_APPROVALS,
            )

    def test_walk_forward_min_fold_exposes_what_random_split_conceals(
        self, tmp_path: Path
    ) -> None:
        src = _time_ordered_signal_csv(tmp_path / "signal_e2e.csv")

        out_random = _run_split_playbook(
            tmp_path, _split_playbook_toml("split_random_cmp", "random"),
            "split_random_cmp", src,
        )
        f_random = json.loads(
            (out_random / "findings" / "baseline.json").read_text("utf-8")
        )["findings"]
        random_recall = f_random["metrics"]["recall"]

        out_wf = _run_split_playbook(
            tmp_path,
            _split_playbook_toml("split_wf_cmp", "walk_forward", n_splits=5),
            "split_wf_cmp", src,
        )
        f_wf = json.loads(
            (out_wf / "findings" / "baseline.json").read_text("utf-8")
        )["findings"]

        assert f_wf["split_mode"] == "walk_forward"
        assert f_wf["ordering_column"] == "signup_date"
        min_fold_recall = f_wf["fold_metrics_summary"]["recall"]["min"]

        # The concealment: a single random-split number cannot show the
        # fold-to-fold volatility. walk_forward's weakest fold is well
        # below what the random split reported as one blended number.
        assert min_fold_recall < random_recall
