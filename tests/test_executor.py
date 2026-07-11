"""Executor tests - charter section 10, each success criterion executable.

10.1 Re-performability: same input, same finding hashes, byte-identical
     artifacts (timestamps live in the audit log, never in artifacts).
10.2 Zero numbers outside the Findings Store (verified by the injector
     mechanism AND by independent scan).
10.3 A failed gate stops the pipeline (planted bad data).
10.4 Human gates cannot be bypassed (Gate 1: unapproved plan refused;
     mid-run gate: missing approval stops).
10.5 All artifacts + manifest + audit log present; manifest verifies.
10.6 The audit log alone reconstructs what happened and why.
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine import (
    ExecutionStopped,
    ExecutorError,
    approve_plan,
    load_playbook,
    make_plan,
    run,
)
from delivery_engine.audit import file_sha256
from delivery_engine.store import (
    FindingsStore,
    NumberInjector,
    StoreError,
    verify_artifact_numbers,
)

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"

# Note: yes/no values are avoided in the fixture - DuckDB's CSV sniffer
# reads them as BOOLEAN (documented engine behavior), so stored values
# become true/false and an allowed-rule on ["yes","no"] correctly reports
# every row. The rule is honest about type coercion; the fixture uses
# values that stay VARCHAR.
RULES: list[dict[str, Any]] = [
    {"column": "customer_id", "rule": "not_null"},
    {"column": "tenure_months", "rule": "range", "min": 0},
    {"column": "churned", "rule": "allowed", "values": ["active", "churned"]},
]


def _churn_csv(path: Path, rows: int = 400, bad_fraction: float = 0.0) -> Path:
    """Planted data: bad_fraction of rows get a negative tenure -
    exactly the violation the range rule catches."""
    random.seed(42)
    bad_count = int(rows * bad_fraction)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "churned", "tenure_months", "plan_type"])
        for i in range(rows):
            tenure = -5 if i < bad_count else random.randint(1, 60)
            w.writerow([
                f"C-{i:05d}", random.choice(["active", "churned"]),
                tenure, random.choice(["basic", "pro"]),
            ])
    return path


def _approved_plan(source: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(source), None))
    plan = make_plan(
        "churn analysis", str(source), envelope["findings"], PLAYBOOKS
    )
    return approve_plan(plan, "Saif")


def _full_run(tmp_path: Path, bad_fraction: float = 0.0) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    src = _churn_csv(tmp_path / "data.csv", bad_fraction=bad_fraction)
    plan = _approved_plan(src)
    pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
    out = tmp_path / "package"
    return run(plan, pb, RULES, out, approvals={"plan_approval": "Saif"})


# ── 10.5: the package is complete and the manifest verifies ─────────────────


class TestPackage:
    def test_all_deliverables_present(self, tmp_path: Path) -> None:
        out = _full_run(tmp_path)
        for name in [
            "eda_notebook.ipynb", "narrative_report.md", "README.md",
            "plan.json", "audit_log.jsonl", "manifest.json",
            "findings/dq_profile.json", "findings/dq_validate.json",
            "findings/dq_dedupe.json",
        ]:
            assert (out / name).exists(), f"missing {name}"

    def test_manifest_hashes_verify(self, tmp_path: Path) -> None:
        """The charter's definition of evidence: recompute and match."""
        out = _full_run(tmp_path)
        manifest = json.loads((out / "manifest.json").read_text())
        assert manifest["files"], "manifest lists no files"
        for rel, expected in manifest["files"].items():
            assert file_sha256(out / rel) == expected, f"hash mismatch: {rel}"

    def test_notebook_is_valid_nbformat_v4(self, tmp_path: Path) -> None:
        """Top-level shape per the official nbformat v4 JSON schema."""
        out = _full_run(tmp_path)
        nb = json.loads((out / "eda_notebook.ipynb").read_text())
        assert set(nb) == {"metadata", "nbformat", "nbformat_minor", "cells"}
        assert nb["nbformat"] == 4
        for cell in nb["cells"]:
            assert cell["cell_type"] in {"markdown", "code"}
            assert "id" in cell and "source" in cell and "metadata" in cell
            if cell["cell_type"] == "code":
                assert "execution_count" in cell and "outputs" in cell


# ── 10.1: re-performability ──────────────────────────────────────────────────


class TestReperformability:
    def test_two_runs_same_findings_and_artifacts(self, tmp_path: Path) -> None:
        """Charter 4.8: SAME input -> same hashes. One source file, one
        plan, executed twice into different output directories."""
        src = _churn_csv(tmp_path / "data.csv")
        plan = _approved_plan(src)
        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        out1 = run(plan, pb, RULES, tmp_path / "run_a",
                   approvals={"plan_approval": "Saif"})
        out2 = run(plan, pb, RULES, tmp_path / "run_b",
                   approvals={"plan_approval": "Saif"})
        m1 = json.loads((out1 / "manifest.json").read_text())
        m2 = json.loads((out2 / "manifest.json").read_text())
        assert m1["findings"] == m2["findings"], "finding hashes differ"
        for name in ["eda_notebook.ipynb", "narrative_report.md", "README.md"]:
            assert m1["files"][name] == m2["files"][name], (
                f"{name} is not byte-reproducible - a timestamp or other "
                f"nondeterminism leaked into an artifact"
            )


# ── 10.2: the injected-numbers rule ──────────────────────────────────────────


class TestInjectedNumbers:
    def test_verifier_catches_a_rogue_number(self) -> None:
        store = FindingsStore()
        store.put("s", {"x": 1})
        inj = NumberInjector(store)
        inj.inject(42)
        with pytest.raises(StoreError, match="Injected-numbers rule violated"):
            verify_artifact_numbers("value is 42 but rogue is 9999", inj)

    def test_verifier_passes_injected_only(self) -> None:
        store = FindingsStore()
        store.put("s", {"x": 1})
        inj = NumberInjector(store)
        text = f"rows: {inj.inject(1107, '{:,}')} and rate {inj.inject_percent(0.153)}"
        verify_artifact_numbers(text, inj)  # must not raise

    def test_none_renders_as_na_never_zero(self) -> None:
        inj = NumberInjector(FindingsStore())
        assert inj.inject(None) == "n/a"
        assert inj.inject_percent(None) == "n/a"

    def test_artifacts_scan_clean_independently(self, tmp_path: Path) -> None:
        """Belt and braces: re-scan the written report with a fresh regex,
        asserting every numeric token appears in the findings JSONs or
        the hash strings - no number from nowhere."""
        out = _full_run(tmp_path)
        report = (out / "narrative_report.md").read_text()
        findings_text = "".join(
            p.read_text() for p in (out / "findings").glob("*.json")
        )
        import re

        # Independent claims-surface: backticked spans are references
        # (paths, ids, hashes), not claims - deliberately re-implemented
        # here rather than importing the engine's extract_claims, so this
        # check stays independent of the code it audits.
        claims = re.sub(r"`[^`]*`", " ", report)

        for token in re.findall(r"\d+\.\d+|\d{1,3}(?:,\d{3})+|\d+", claims):
            plain = token.replace(",", "")
            assert (
                plain in findings_text.replace(",", "")
                or token in findings_text
            ), f"number {token} in report has no source in findings"


# ── 10.3: gates stop the pipeline ────────────────────────────────────────────


class TestGates:
    def test_planted_bad_data_stops_at_validate(self, tmp_path: Path) -> None:
        """25% of rows violate the range rule - far over the 10% gate."""
        with pytest.raises(ExecutionStopped) as exc_info:
            _full_run(tmp_path, bad_fraction=0.25)
        assert exc_info.value.stage_id == "dq_validate"
        assert "exception rate" in exc_info.value.reason

    def test_stop_still_writes_audit_log(self, tmp_path: Path) -> None:
        """A stopped run must still leave its evidence."""
        with pytest.raises(ExecutionStopped):
            _full_run(tmp_path, bad_fraction=0.25)
        log = (tmp_path / "package" / "audit_log.jsonl").read_text()
        entries = [json.loads(line) for line in log.strip().splitlines()]
        fail = next(e for e in entries if e["outcome"] == "fail")
        assert fail["stage"] == "dq_validate"

    def test_no_artifacts_after_stopped_gate(self, tmp_path: Path) -> None:
        """Nothing downstream of a failed gate may exist."""
        with pytest.raises(ExecutionStopped):
            _full_run(tmp_path, bad_fraction=0.25)
        out = tmp_path / "package"
        assert not (out / "eda_notebook.ipynb").exists()
        assert not (out / "narrative_report.md").exists()

    def test_exception_rate_within_threshold_passes(self, tmp_path: Path) -> None:
        """5% bad rows - exceptions are evidence, the gate passes."""
        out = _full_run(tmp_path, bad_fraction=0.05)
        assert (out / "manifest.json").exists()


# ── 10.4: human gates cannot be bypassed ─────────────────────────────────────


class TestHumanGates:
    def test_unapproved_plan_refused(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "d.csv")
        envelope = json.loads(tool_profile(str(src), None))
        plan = make_plan("churn analysis", str(src), envelope["findings"], PLAYBOOKS)
        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        with pytest.raises(ExecutorError, match="Human Gate 1"):
            run(plan, pb, RULES, tmp_path / "out")

    def test_missing_midrun_approval_stops(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "d.csv")
        plan = _approved_plan(src)
        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, RULES, tmp_path / "out", approvals={})
        assert exc_info.value.stage_id == "plan_approval"

    def test_playbook_drift_refused(self, tmp_path: Path) -> None:
        """The playbook changed after approval - re-plan, re-approve."""
        src = _churn_csv(tmp_path / "d.csv")
        plan = _approved_plan(src)
        drifted_dir = tmp_path / "lib"
        drifted_dir.mkdir()
        ref = (PLAYBOOKS / "churn_analysis.toml").read_text()
        (drifted_dir / "churn_analysis.toml").write_text(
            ref.replace('id = "dq_dedupe"', 'id = "dq_dedupe_v2"')
        )
        drifted = load_playbook(drifted_dir / "churn_analysis.toml")
        with pytest.raises(ExecutorError, match="re-plan and re-approve"):
            run(plan, drifted, RULES, tmp_path / "out",
                approvals={"plan_approval": "Saif"})

    def test_validate_without_rules_refused_preflight(
        self, tmp_path: Path
    ) -> None:
        src = _churn_csv(tmp_path / "d.csv")
        plan = _approved_plan(src)
        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        with pytest.raises(ExecutorError, match="no rules"):
            run(plan, pb, [], tmp_path / "out",
                approvals={"plan_approval": "Saif"})


# ── 10.6: the audit log alone reconstructs the run ───────────────────────────


class TestAuditLog:
    def test_every_stage_has_an_entry(self, tmp_path: Path) -> None:
        out = _full_run(tmp_path)
        entries = [
            json.loads(line)
            for line in (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        stages_logged = {e["stage"] for e in entries}
        for sid in ["plan", "dq_profile", "dq_validate", "dq_dedupe",
                    "plan_approval", "eda", "report", "readme", "package"]:
            assert sid in stages_logged, f"stage '{sid}' missing from audit log"

    def test_entries_carry_rationale_and_hashes(self, tmp_path: Path) -> None:
        out = _full_run(tmp_path)
        entries = [
            json.loads(line)
            for line in (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        assert all(e["rationale"] for e in entries)
        kit_entries = [e for e in entries if e["action"].startswith("kit:")]
        assert all("sha256" in e for e in kit_entries)

    def test_plan_digest_in_log_matches_manifest(self, tmp_path: Path) -> None:
        out = _full_run(tmp_path)
        entries = [
            json.loads(line)
            for line in (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        gate1 = next(e for e in entries if e["action"] == "human_gate_1")
        manifest = json.loads((out / "manifest.json").read_text())
        assert gate1["sha256"] == manifest["plan_sha256"]


# ── Findings store discipline ─────────────────────────────────────────────────


class TestStore:
    def test_evidence_never_overwritten(self) -> None:
        store = FindingsStore()
        store.put("s", {"x": 1})
        with pytest.raises(StoreError, match="never overwritten"):
            store.put("s", {"x": 2})

    def test_missing_stage_clean_error(self) -> None:
        store = FindingsStore()
        with pytest.raises(StoreError, match="No findings"):
            store.get("ghost")


class TestExecutorHardening:
    """Loophole hunt fixes: forged approvals, TOCTOU source swaps, dirty
    output directories, and stray approvals - all fail closed."""

    def test_incomplete_approval_metadata_refused(self, tmp_path: Path) -> None:
        from dataclasses import replace

        src = _churn_csv(tmp_path / "d.csv")
        plan = _approved_plan(src)
        forged = replace(plan, approved_by=None)
        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        with pytest.raises(ExecutorError, match="who and when"):
            run(forged, pb, RULES, tmp_path / "out",
                approvals={"plan_approval": "Saif"})

    def test_source_swap_after_approval_stops_at_profile(
        self, tmp_path: Path
    ) -> None:
        """TOCTOU: same path, different data - the fresh profile no longer
        matches the plan's classified kinds, and the gate stops."""
        src = _churn_csv(tmp_path / "d.csv")
        plan = _approved_plan(src)
        # swap: same file, entirely different content and schema
        src.write_text("alpha,beta\nx,y\nx,y\n", encoding="utf-8")
        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, RULES, tmp_path / "out",
                approvals={"plan_approval": "Saif"})
        assert exc_info.value.stage_id == "dq_profile"
        assert "drifted" in exc_info.value.reason

    def test_dirty_out_dir_refused(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "d.csv")
        plan = _approved_plan(src)
        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        out = tmp_path / "out"
        out.mkdir()
        (out / "stale_artifact.md").write_text("left over", encoding="utf-8")
        with pytest.raises(ExecutorError, match="not empty"):
            run(plan, pb, RULES, out, approvals={"plan_approval": "Saif"})

    def test_stray_approval_refused(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "d.csv")
        plan = _approved_plan(src)
        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        with pytest.raises(ExecutorError, match="nonexistent gate"):
            run(plan, pb, RULES, tmp_path / "out",
                approvals={"plan_approval": "Saif", "ghost_gate": "X"})
