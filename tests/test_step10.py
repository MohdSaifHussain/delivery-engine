"""Step 10 tests - the deterministic baseline model stage.

Planted-answer testing applied to ML: the fixture's churn column is a
deterministic function of tenure (churned = yes iff tenure < 12), so the
baseline MUST separate the classes almost perfectly - a specific,
verifiable planted answer, not a vague "model trains" smoke test.

The charter position under test: the AI generates NO training code. The
baseline is fixed-seed deterministic engine code over columns the
planner classified and the human approved. Metric values never gate;
training feasibility does.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine import (
    ExecutionStopped,
    PlaybookError,
    approve_plan,
    load_playbook,
    make_plan,
    run,
)
from delivery_engine.model import ModelError, train_baseline

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
CHURN = PLAYBOOKS / "churn_analysis.toml"

RULES = [{"column": "customer_id", "rule": "unique"}]
APPROVALS: dict[str, Any] = {"plan_approval": "Saif"}


def _churn_csv(path: Path, rows: int = 400) -> Path:
    """The planted signal: churned = 'yes' iff tenure_months < 12.
    A deterministic rule the baseline must discover (roc_auc ~ 1.0)."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "churned", "tenure_months",
                    "plan_type", "monthly_spend"])
        for i in range(rows):
            tenure = (i * 7) % 60 + 1            # 1..60, deterministic
            churned = "yes" if tenure < 12 else "no"
            plan_type = ["basic", "plus", "pro"][i % 3]
            spend = 200.0 + (i % 50) * 3.5
            w.writerow([f"C-{i:05d}", churned, tenure, plan_type,
                        f"{spend:.2f}"])
    return path


def _approved_churn_plan(src: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "churn analysis for the retention team", str(src),
        envelope["findings"], PLAYBOOKS,
    )
    assert plan.playbook_name == "churn_analysis"
    return approve_plan(plan, "Saif")


# ── The trainer, unit level: planted signal and clean failures ───────────────


class TestTrainBaseline:
    def test_planted_signal_is_found(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        findings = train_baseline(
            str(src), "churned", ["tenure_months", "monthly_spend"],
            ["plan_type"],
        )
        assert findings["metrics"]["roc_auc"] > 0.95, (
            "the planted deterministic signal (churned iff tenure < 12) "
            "must be nearly perfectly separable"
        )
        assert findings["random_seed"] == 42
        assert findings["split"] == "stratified"
        assert findings["n_train"] + findings["n_test"] == 400

    def test_metrics_reproduce_exactly(self, tmp_path: Path) -> None:
        """Fixed integer seeds per scikit-learn's controlling-randomness
        guidance: same source, same columns, identical findings."""
        src = _churn_csv(tmp_path / "churn.csv")
        a = train_baseline(str(src), "churned",
                           ["tenure_months", "monthly_spend"], ["plan_type"])
        b = train_baseline(str(src), "churned",
                           ["tenure_months", "monthly_spend"], ["plan_type"])
        assert a == b

    def test_single_class_target_refused(self, tmp_path: Path) -> None:
        src = tmp_path / "one.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "churned", "x"])
            for i in range(50):
                w.writerow([i, "no", i])
        with pytest.raises(ModelError, match="exactly 2 classes"):
            train_baseline(str(src), "churned", ["x"], [])

    def test_tiny_minority_class_refused(self, tmp_path: Path) -> None:
        src = tmp_path / "tiny.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "churned", "x"])
            for i in range(100):
                w.writerow([i, "yes" if i < 3 else "no", i])
        with pytest.raises(ModelError, match="Minority class"):
            train_baseline(str(src), "churned", ["x"], [])

    def test_plan_source_drift_refused(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        with pytest.raises(ModelError, match="does not exist in"):
            train_baseline(str(src), "churned", ["ghost_column"], [])

    def test_no_features_refused(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        with pytest.raises(ModelError, match="at least one feature"):
            train_baseline(str(src), "churned", [], [])

    def test_missing_sklearn_is_clean_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A must_pass stage fails loudly on a missing dependency."""
        monkeypatch.setitem(sys.modules, "sklearn", None)
        from delivery_engine.model import _require_sklearn

        with pytest.raises(ModelError, match="delivery-engine\\[ml\\]"):
            _require_sklearn()


# ── V12: the constitution extends to model stages ────────────────────────────


class TestV12:
    HEAD = """
schema_version = 1

[playbook]
name = "t"
version = "1.0.0"
description = "d"

[[stages]]
id = "gate"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"
"""
    TAIL = """
[deliverables]
artifacts = ["audit_log", "manifest"]
"""

    def _load(self, tmp_path: Path, body: str):  # type: ignore[no-untyped-def]
        p = tmp_path / "pb.toml"
        p.write_text(body, encoding="utf-8")
        return load_playbook(p)

    def test_model_without_needs_rejected(self, tmp_path: Path) -> None:
        body = self.HEAD + """
[[stages]]
id = "baseline"
kind = "model"
gate = "must_pass"
""" + self.TAIL
        with pytest.raises(PlaybookError, match=r"\(V12\)"):
            self._load(tmp_path, body)

    def test_model_without_gate_rejected(self, tmp_path: Path) -> None:
        body = self.HEAD + """
[[stages]]
id = "baseline"
kind = "model"
needs = ["gate"]
""" + self.TAIL
        with pytest.raises(PlaybookError, match="gate"):
            self._load(tmp_path, body)

    def test_model_unknown_key_rejected(self, tmp_path: Path) -> None:
        body = self.HEAD + """
[[stages]]
id = "baseline"
kind = "model"
gate = "must_pass"
needs = ["gate"]
hyperparameters = "lots"
""" + self.TAIL
        with pytest.raises(PlaybookError, match=r"\(V6"):
            self._load(tmp_path, body)

    def test_churn_archetype_v11_loads_with_baseline(self) -> None:
        pb = load_playbook(CHURN)
        assert pb.version == "1.1.0"
        baseline = next(s for s in pb.stages if s.stage_id == "baseline")
        assert baseline.kind.value == "model"
        assert set(baseline.needs) >= {"dq_profile", "dq_validate"}


# ── End to end: the model stage inside the churn archetype ───────────────────


class TestLoopholeRegressions:
    """Step 10 loophole hunt: each fix lands with a test proving the old
    failure."""

    def test_null_rows_dropped_and_recorded(self, tmp_path: Path) -> None:
        """LOOPHOLE: a null in any feature row crashed with a raw sklearn
        error. Now rows are dropped, the count is recorded in the hashed
        findings, and training proceeds honestly."""
        src = tmp_path / "nulls.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "churned", "x"])
            for i in range(200):
                x = "" if i % 10 == 0 else str(i % 60)
                w.writerow([i, "yes" if (i % 60) < 12 else "no", x])
        findings = train_baseline(str(src), "churned", ["x"], [])
        assert findings["n_rows_dropped_nulls"] == 20
        assert findings["n_train"] + findings["n_test"] == 180

    def test_all_null_features_refused_cleanly(self, tmp_path: Path) -> None:
        src = tmp_path / "allnull.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "churned", "x"])
            for i in range(100):
                w.writerow([i, "yes" if i % 2 else "no", ""])
        with pytest.raises(ModelError, match="too few to train"):
            train_baseline(str(src), "churned", ["x"], [])

    def test_multiple_binary_targets_disclosed(self, tmp_path: Path) -> None:
        """LOOPHOLE: with two binary columns the stage silently trained
        on whichever came first, telling no one. Refusal was rejected as
        over-engineering (a yes/no flag is ordinary data); the fix is
        DISCLOSED deterministic selection: first binary in the plan order
        the human approved, all candidates recorded in hashed findings."""
        src = tmp_path / "twoflags.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["customer_id", "churned", "is_active",
                        "tenure_months", "plan_type", "monthly_spend"])
            for i in range(400):
                t = (i * 7) % 60 + 1
                w.writerow([f"C-{i:05d}", "yes" if t < 12 else "no",
                            "y" if i % 2 else "n", t,
                            ["basic", "plus", "pro"][i % 3],
                            f"{200 + (i % 50) * 3.5:.2f}"])
        envelope = json.loads(tool_profile(str(src), None))
        plan = make_plan(
            "churn analysis for the retention team", str(src),
            envelope["findings"], PLAYBOOKS,
        )
        plan = approve_plan(plan, "Saif")
        pb = load_playbook(CHURN)
        out = run(plan, pb, RULES, tmp_path / "out", approvals=APPROVALS)
        stored = json.loads((out / "findings" / "baseline.json").read_text())
        f = stored["findings"]
        assert f["target"] == "churned"          # first in plan order
        assert set(f["target_candidates"]) == {"churned", "is_active"}
        assert "Human Gate 1" in f["target_selection"]
        entries = [
            json.loads(line) for line in
            (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        b = next(e for e in entries if e["stage"] == "baseline")
        assert "is_active" in b["rationale"]     # candidates disclosed

    def test_id_columns_excluded_from_features(self, tmp_path: Path) -> None:
        """LOOPHOLE: a numeric id classifies as both id_column and
        numeric_column and entered the feature set - identifier leakage.
        Now id-classified columns never train."""
        src = tmp_path / "numid.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["customer_num", "churned", "tenure_months",
                        "plan_type"])
            for i in range(400):
                t = (i * 7) % 60 + 1
                w.writerow([100000 + i, "yes" if t < 12 else "no", t,
                            ["basic", "plus", "pro"][i % 3]])
        envelope = json.loads(tool_profile(str(src), None))
        plan = make_plan(
            "churn analysis for the retention team", str(src),
            envelope["findings"], PLAYBOOKS,
        )
        plan = approve_plan(plan, "Saif")
        pb = load_playbook(CHURN)
        out = run(plan, pb, [{"column": "customer_num", "rule": "unique"}],
                  tmp_path / "out", approvals=APPROVALS)
        stored = json.loads((out / "findings" / "baseline.json").read_text())
        trained_on = (stored["findings"]["numeric_features"]
                      + stored["findings"]["categorical_features"])
        assert "customer_num" not in trained_on


class TestEndToEnd:
    def test_baseline_findings_and_report_section(
        self, tmp_path: Path
    ) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        plan = _approved_churn_plan(src)
        pb = load_playbook(CHURN)
        out = run(plan, pb, RULES, tmp_path / "out", approvals=APPROVALS)

        stored = json.loads((out / "findings" / "baseline.json").read_text())
        assert stored["findings"]["metrics"]["roc_auc"] > 0.95
        assert stored["findings"]["target"] == "churned"

        report = (out / "narrative_report.md").read_text(encoding="utf-8")
        assert "## Baseline model" in report
        assert str(stored["findings"]["metrics"]["roc_auc"]) in report
        assert "not a delivered model" in report

        manifest = json.loads((out / "manifest.json").read_text())
        assert "baseline" in manifest["findings"]

        entries = [
            json.loads(line) for line in
            (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        b = next(e for e in entries if e["stage"] == "baseline")
        assert b["outcome"] == "pass"
        assert "metric values never gate" in b["rationale"]

    def test_package_reproducible_with_baseline(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        plan = _approved_churn_plan(src)
        pb = load_playbook(CHURN)
        out_a = run(plan, pb, RULES, tmp_path / "a", approvals=APPROVALS)
        out_b = run(plan, pb, RULES, tmp_path / "b", approvals=APPROVALS)
        ma = json.loads((out_a / "manifest.json").read_text())
        mb = json.loads((out_b / "manifest.json").read_text())
        assert ma["findings"]["baseline"] == mb["findings"]["baseline"]
        assert ma["files"]["narrative_report.md"] == mb["files"]["narrative_report.md"]

    def test_untrainable_target_stops_pipeline(self, tmp_path: Path) -> None:
        """must_pass semantics: feasibility gates. A source whose target
        went single-class after planning stops the run cleanly."""
        src = _churn_csv(tmp_path / "churn.csv")
        plan = _approved_churn_plan(src)
        # drift the source after approval: everyone churns now
        rows = src.read_text(encoding="utf-8").splitlines()
        head, body = rows[0], rows[1:]
        drifted = [head] + [
            ",".join([r.split(",")[0], "yes", *r.split(",")[2:]])
            for r in body
        ]
        src.write_text("\n".join(drifted) + "\n", encoding="utf-8")
        pb = load_playbook(CHURN)
        with pytest.raises(ExecutionStopped):
            run(plan, pb, RULES, tmp_path / "out", approvals=APPROVALS)
