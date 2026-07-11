"""Step 9 tests - the transaction_monitoring_review archetype.

The first playbook to compose the full system: both kits, Human Gate 2,
dual narratives. Zero engine changes - if any test here required an
engine change, the playbooks-not-code principle would have failed.

Planted answers: a transaction feed whose volume surges in the last week
(the OpsKit story) with clean ids and timestamps (the drafted-rules
story). Runs the REAL analystkit_mcp and opskit_mcp end to end.

Routing lesson recorded from this step's build: the planner's tie-break
is lexical, so archetype descriptions are part of the routing contract -
this archetype's description deliberately avoids the tokens 'data
quality' so the two archetypes stay separable by goal wording. The
routing tests below pin that contract.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
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

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
TM = PLAYBOOKS / "transaction_monitoring_review.toml"


def _txn_csv(path: Path) -> Path:
    """A transaction feed: unique txn ids, timestamps, amounts, channel.
    Calm 5/day then surge 12/day in the final week, surge driven by
    channel='wire' - the planted volume story."""
    end = datetime(2026, 7, 6, 12, 0)
    rows: list[list[str]] = []
    n = 1
    for off in range(56, -1, -1):
        day = end - timedelta(days=off)
        per_day = 12 if off <= 7 else 5
        for i in range(per_day):
            channel = "wire" if (off <= 7 and i % 2 == 0) else "card"
            rows.append([
                f"TXN-{n:06d}", day.strftime("%Y-%m-%d %H:%M:%S"),
                f"{250.0 + (i * 13):.2f}", channel,
            ])
            n += 1
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["txn_id", "posted_at", "amount", "channel"])
        w.writerows(rows)
    return path


def _approved_tm_plan(src: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "transaction monitoring completeness review of this feed",
        str(src), envelope["findings"], PLAYBOOKS,
    )
    assert plan.playbook_name == "transaction_monitoring_review"
    return approve_plan(plan, "Saif")


def _two_phase_run(src: Path, tmp_path: Path) -> Path:
    """Phase 1 stops at Human Gate 2; phase 2 approves the exact draft
    by hash and completes."""
    plan = _approved_tm_plan(src)
    pb = load_playbook(TM)
    with pytest.raises(ExecutionStopped):
        run(plan, pb, [], tmp_path / "phase1")
    digest = json.loads(
        (tmp_path / "phase1" / "rules_draft.json").read_text()
    )["sha256"]
    return run(
        plan, pb, [], tmp_path / "final",
        approvals={"rules": {"approver": "Saif", "sha256": digest}},
    )


# ── Constitution and composition ─────────────────────────────────────────────


class TestArchetype:
    def test_loads_and_composes_everything(self) -> None:
        pb = load_playbook(TM)
        assert pb.name == "transaction_monitoring_review"
        tools = {s.tool for s in pb.stages if s.tool}
        assert "analystkit_profile" in tools
        assert "analystkit_validate" in tools
        assert "opskit_run_playbook" in tools
        slots = {s.slot.value for s in pb.stages if s.slot}
        assert {"rules_draft", "narrative_report", "ops_report",
                "readme"} <= slots
        rules = next(s for s in pb.stages if s.stage_id == "rules")
        assert rules.feeds_deterministic and rules.human_approval

    def test_requirements(self) -> None:
        pb = load_playbook(TM)
        assert pb.requirements.min_rows == 100
        assert set(pb.requirements.required_kinds) == {
            "id_column", "timestamp_column",
        }


# ── Routing: the lexical contract, pinned ────────────────────────────────────


class TestRouting:
    def test_tm_goal_routes_to_tm(self, tmp_path: Path) -> None:
        src = _txn_csv(tmp_path / "txns.csv")
        envelope = json.loads(tool_profile(str(src), None))
        plan = make_plan(
            "transaction monitoring completeness review of this feed",
            str(src), envelope["findings"], PLAYBOOKS,
        )
        assert plan.playbook_name == "transaction_monitoring_review"

    def test_dq_goal_still_routes_to_dq(self, tmp_path: Path) -> None:
        """The regression this step nearly shipped: the TM description
        originally contained 'data quality', tying with the DQ archetype
        on its own goal. Descriptions are routing surfaces - pinned."""
        src = _txn_csv(tmp_path / "txns.csv")
        envelope = json.loads(tool_profile(str(src), None))
        plan = make_plan(
            "data quality review of this extract",
            str(src), envelope["findings"], PLAYBOOKS,
        )
        assert plan.playbook_name == "data_quality_review"


# ── End to end: the full composition, real kits ──────────────────────────────


class TestEndToEnd:
    def test_two_phase_completes_with_dual_narratives(
        self, tmp_path: Path
    ) -> None:
        src = _txn_csv(tmp_path / "txns.csv")
        out = _two_phase_run(src, tmp_path)

        # both narratives exist
        report = (out / "narrative_report.md").read_text(encoding="utf-8")
        ops = (out / "ops_report.md").read_text(encoding="utf-8")
        assert "# Findings Report" in report
        assert "# Operational Review Report" in ops

        # the planted volume story appears verbatim in the ops narrative
        stored = json.loads(
            (out / "findings" / "ops_review.json").read_text()
        )
        crit_texts = [f["text"] for f in stored["findings"]["findings"]
                      if f["severity"] == "CRITICAL"]
        assert crit_texts, "the planted surge must yield criticals"
        assert any(t in ops for t in crit_texts)

        # the drafted-rules story: validate consumed the approved draft
        vf = json.loads((out / "findings" / "dq_validate.json").read_text())
        assert vf["findings"]["rules_evaluated"] >= 3

        # package complete
        manifest = json.loads((out / "manifest.json").read_text())
        for f in ("narrative_report.md", "ops_report.md", "README.md",
                  "rules_draft.json", "audit_log.jsonl"):
            assert f in manifest["files"] or f == "audit_log.jsonl"
        assert {"dq_profile", "dq_validate", "dq_dedupe", "ops_review"} <= set(
            manifest["findings"]
        )

    def test_audit_tells_the_whole_story(self, tmp_path: Path) -> None:
        src = _txn_csv(tmp_path / "txns.csv")
        out = _two_phase_run(src, tmp_path)
        entries = [
            json.loads(line) for line in
            (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        stages = {e["stage"] for e in entries}
        assert {"dq_profile", "rules", "dq_validate", "ops_review",
                "report", "ops_report", "readme"} <= stages
        approved = next(e for e in entries
                        if e["stage"] == "rules" and e["outcome"] == "approved")
        assert "Saif" in approved["rationale"]
        ops_pass = next(e for e in entries
                        if e["stage"] == "ops_review" and e["outcome"] == "pass")
        assert "seal verified" in ops_pass["rationale"]

    def test_package_reproducible(self, tmp_path: Path) -> None:
        """Charter 4.8 on the richest package yet: same source, same
        approval, matching finding digests and artifact hashes."""
        src = _txn_csv(tmp_path / "txns.csv")
        plan = _approved_tm_plan(src)
        pb = load_playbook(TM)
        with pytest.raises(ExecutionStopped):
            run(plan, pb, [], tmp_path / "p1")
        digest = json.loads(
            (tmp_path / "p1" / "rules_draft.json").read_text()
        )["sha256"]
        approval: dict[str, Any] = {
            "rules": {"approver": "Saif", "sha256": digest}
        }
        out_a = run(plan, pb, [], tmp_path / "a", approvals=approval)
        out_b = run(plan, pb, [], tmp_path / "b", approvals=approval)
        ma = json.loads((out_a / "manifest.json").read_text())
        mb = json.loads((out_b / "manifest.json").read_text())
        assert ma["findings"] == mb["findings"]
        for f in ("narrative_report.md", "ops_report.md", "README.md",
                  "rules_draft.json"):
            assert ma["files"][f] == mb["files"][f]

    def test_wrong_hash_still_refused_in_composition(
        self, tmp_path: Path
    ) -> None:
        """Human Gate 2 keeps its teeth inside the richest archetype."""
        src = _txn_csv(tmp_path / "txns.csv")
        plan = _approved_tm_plan(src)
        pb = load_playbook(TM)
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out",
                approvals={"rules": {"approver": "Saif", "sha256": "0" * 64}})
        assert "does not match" in exc_info.value.reason
