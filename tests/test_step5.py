"""Step 5 tests - Human Gate 2 (content-bound), the second archetype,
deterministic rule drafting.

The critical property under test: WHAT WAS REVIEWED IS WHAT RUNS.
The approval quotes a hash; the hash binds to the exact draft; any
mismatch refuses. Charter 4.4 at its sharpest point.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine import (
    ExecutionStopped,
    approve_plan,
    load_playbook,
    make_plan,
    run,
)
from delivery_engine.rules_draft import draft_digest, draft_rules

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"


def _clean_csv(path: Path, rows: int = 150) -> Path:
    """Fully-complete data: ids unique, no nulls, a timestamp column -
    exactly the shapes the drafter can justify rules for."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["record_id", "amount", "created_at"])
        for i in range(rows):
            w.writerow([f"R-{i:05d}", 100 + i, f"2026-06-{(i % 28) + 1:02d} 09:00:00"])
    return path


def _dq_plan(src: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "data quality review of this extract", str(src),
        envelope["findings"], PLAYBOOKS,
    )
    return approve_plan(plan, "Saif")


# ── Drafting: deterministic, justified, reproducible ─────────────────────────


class TestDrafting:
    def _profile(self, tmp_path: Path) -> dict[str, Any]:
        src = _clean_csv(tmp_path / "d.csv")
        return dict(json.loads(tool_profile(str(src), None))["findings"])

    def test_drafts_expected_rules(self, tmp_path: Path) -> None:
        rules, rationales = draft_rules(self._profile(tmp_path))
        as_pairs = {(r["column"], r["rule"]) for r in rules}
        assert ("record_id", "not_null") in as_pairs
        assert ("record_id", "unique") in as_pairs
        assert ("created_at", "not_future") in as_pairs
        assert len(rules) == len(rationales)
        assert all(rationales)

    def test_draft_hash_reproducible(self, tmp_path: Path) -> None:
        p = self._profile(tmp_path)
        r1, _ = draft_rules(p)
        r2, _ = draft_rules(p)
        assert draft_digest(r1) == draft_digest(r2)

    def test_empty_profile_drafts_nothing(self) -> None:
        rules, rationales = draft_rules({"columns": []})
        assert rules == [] and rationales == []


# ── Human Gate 2: the two-phase, content-bound flow ──────────────────────────


class TestHumanGate2:
    def test_phase1_stops_and_writes_draft(self, tmp_path: Path) -> None:
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out")
        assert exc_info.value.stage_id == "rules"
        assert "Human Gate 2" in exc_info.value.reason
        draft = json.loads((tmp_path / "out" / "rules_draft.json").read_text())
        assert draft["rules"], "draft written with rules"
        assert draft["sha256"], "draft carries its hash"
        assert "how_to_approve" in draft

    def test_phase1_audit_records_awaiting(self, tmp_path: Path) -> None:
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutionStopped):
            run(plan, pb, [], tmp_path / "out")
        log = (tmp_path / "out" / "audit_log.jsonl").read_text()
        entries = [json.loads(line) for line in log.strip().splitlines()]
        waiting = next(e for e in entries if e["outcome"] == "awaiting_human_gate_2")
        assert waiting["stage"] == "rules"
        assert "sha256" in waiting

    def test_phase2_correct_hash_completes(self, tmp_path: Path) -> None:
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutionStopped):
            run(plan, pb, [], tmp_path / "phase1")
        digest = json.loads(
            (tmp_path / "phase1" / "rules_draft.json").read_text()
        )["sha256"]

        out = run(plan, pb, [], tmp_path / "phase2",
                  approvals={"rules": {"approver": "Saif", "sha256": digest}})
        assert (out / "manifest.json").exists()
        # validate consumed the drafted rules
        vf = json.loads((out / "findings" / "dq_validate.json").read_text())
        assert vf["findings"]["rules_evaluated"] >= 3

    def test_wrong_hash_refused(self, tmp_path: Path) -> None:
        """What was reviewed is not what would run - refuse."""
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out",
                approvals={"rules": {"approver": "Saif", "sha256": "0" * 64}})
        assert "does not match" in exc_info.value.reason

    def test_stage_only_approval_refused(self, tmp_path: Path) -> None:
        """A bare approver string is not content-bound - refused for
        feeds_deterministic stages."""
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out",
                approvals={"rules": "Saif"})  # type: ignore[dict-item]
        assert "content-bound" in exc_info.value.reason

    def test_approval_recorded_in_audit(self, tmp_path: Path) -> None:
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutionStopped):
            run(plan, pb, [], tmp_path / "p1")
        digest = json.loads(
            (tmp_path / "p1" / "rules_draft.json").read_text()
        )["sha256"]
        out = run(plan, pb, [], tmp_path / "p2",
                  approvals={"rules": {"approver": "Saif", "sha256": digest}})
        entries = [
            json.loads(line)
            for line in (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        approved = next(e for e in entries if e["outcome"] == "approved"
                        and e["stage"] == "rules")
        assert "Saif" in approved["rationale"]
        assert approved["sha256"] == digest


# ── The second archetype end-to-end ──────────────────────────────────────────


class TestSecondArchetype:
    def test_planner_selects_dq_review_by_goal(self, tmp_path: Path) -> None:
        """Both archetypes may qualify on a churn-shaped source; goal
        keywords must route to the right one deterministically."""
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        assert plan.playbook_name == "data_quality_review"

    def test_full_two_phase_package_reproducible(self, tmp_path: Path) -> None:
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutionStopped):
            run(plan, pb, [], tmp_path / "p1")
        digest = json.loads(
            (tmp_path / "p1" / "rules_draft.json").read_text()
        )["sha256"]
        approval = {"rules": {"approver": "Saif", "sha256": digest}}
        out_a = run(plan, pb, [], tmp_path / "a", approvals=approval)
        out_b = run(plan, pb, [], tmp_path / "b", approvals=approval)
        ma = json.loads((out_a / "manifest.json").read_text())
        mb = json.loads((out_b / "manifest.json").read_text())
        assert ma["findings"] == mb["findings"]
        assert ma["files"]["narrative_report.md"] == mb["files"]["narrative_report.md"]
        assert ma["files"]["rules_draft.json"] == mb["files"]["rules_draft.json"]


class TestHumanGate2Hardening:
    """Loophole hunt fixes: nameless approvals and dual rule sources."""

    def test_empty_approver_refused(self, tmp_path: Path) -> None:
        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutionStopped, match="content-bound"):
            run(plan, pb, [], tmp_path / "out",
                approvals={"rules": {"approver": "   ", "sha256": "0" * 64}})

    def test_dual_rule_sources_refused_preflight(self, tmp_path: Path) -> None:
        from delivery_engine import ExecutorError

        src = _clean_csv(tmp_path / "d.csv")
        plan = _dq_plan(src)
        pb = load_playbook(PLAYBOOKS / "data_quality_review.toml")
        with pytest.raises(ExecutorError, match="Two sources of rules"):
            run(plan, pb, [{"column": "record_id", "rule": "not_null"}],
                tmp_path / "out")
