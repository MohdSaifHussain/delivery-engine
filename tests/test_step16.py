"""Step 16 tests - the pre-flight preview and the handoff manifest.

The constitutional positions under test:

Preview:
- render_preview is a pure function of (playbook, plan) and shows the
  human exactly what the executor will run - stages, gates, columns,
  the pre-registered alpha - computed from the same two documents the
  executor uses, never a third source.
- The engine core is non-interactive: no callback, no pause. With a
  callback, declining stops the run BEFORE any stage executes, with an
  audit entry; confirming records an audit entry and proceeds.
- The rendered preview is written into the package either way and is
  hashed by the manifest: what the human was shown is evidence.

Handoff:
- handoff_manifest.json is generated from the plan, the playbook, and
  the sealed findings - checks carry the digests they reference.
- Every signature starts null: the engine never signs for a human.
- The file is hashed in manifest.json: tampering fails verification.
- Deterministic: same run, same handoff content.
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
from delivery_engine.audit import file_sha256
from delivery_engine.preview import render_preview

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
SEGMENT = PLAYBOOKS / "segment_comparison.toml"

RULES = [{"column": "customer_id", "rule": "unique"}]
APPROVALS: dict[str, Any] = {"plan_approval": "Saif"}


def _segment_csv(path: Path, rows: int = 200) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "converted", "segment", "spend"])
        for i in range(rows):
            seg = "a" if i % 2 == 0 else "b"
            threshold = 8 if seg == "a" else 1
            conv = "yes" if i % 10 < threshold else "no"
            spend = (1000.0 + i) if conv == "yes" else (100.0 + i * 0.5)
            w.writerow([f"C-{i:05d}", conv, seg, f"{spend:.2f}"])
    return path


def _approved_plan(src: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "segment comparison with statistical significance for the "
        "growth team", str(src), envelope["findings"], PLAYBOOKS,
    )
    return approve_plan(plan, "Saif")


# ── the preview text ─────────────────────────────────────────────────────────


class TestRenderPreview:
    def test_shows_what_the_executor_will_run(self, tmp_path: Path) -> None:
        plan = _approved_plan(_segment_csv(tmp_path / "seg.csv"))
        pb = load_playbook(SEGMENT)
        text = render_preview(pb, plan)
        # every stage, in the playbook, by id
        for stage in pb.stages:
            assert stage.stage_id in text
        # the approved column classification
        for col, kind in plan.column_kinds:
            assert f"{col}: {kind}" in text
        # the pre-registered alpha for a stats playbook
        assert "pre-registered alpha = 0.05" in text
        assert "significance never gates" in text
        # gates split by mode
        assert "must_pass" in text and "advisory" in text
        # the plan digest so the preview is tied to the exact plan
        assert plan.plan_digest() in text

    def test_pure_function_same_inputs_same_text(
        self, tmp_path: Path
    ) -> None:
        plan = _approved_plan(_segment_csv(tmp_path / "seg.csv"))
        pb = load_playbook(SEGMENT)
        assert render_preview(pb, plan) == render_preview(pb, plan)


# ── the confirmation semantics ───────────────────────────────────────────────


class TestPreviewConfirmation:
    def test_no_callback_no_pause_file_still_written(
        self, tmp_path: Path
    ) -> None:
        plan = _approved_plan(_segment_csv(tmp_path / "seg.csv"))
        pb = load_playbook(SEGMENT)
        out = tmp_path / "pkg"
        run(plan, pb, RULES, out, approvals=APPROVALS)
        preview_file = out / "execution_preview.md"
        assert preview_file.exists()
        # and the manifest hashes it - the shown text is evidence
        manifest = json.loads((out / "manifest.json").read_text("utf-8"))
        assert "execution_preview.md" in manifest["files"]
        assert manifest["files"]["execution_preview.md"] == file_sha256(
            preview_file
        )

    def test_declining_stops_before_any_stage_runs(
        self, tmp_path: Path
    ) -> None:
        plan = _approved_plan(_segment_csv(tmp_path / "seg.csv"))
        pb = load_playbook(SEGMENT)
        out = tmp_path / "pkg"
        shown: list[str] = []

        def decline(text: str) -> bool:
            shown.append(text)
            return False

        with pytest.raises(ExecutionStopped, match="pre-flight"):
            run(plan, pb, RULES, out, approvals=APPROVALS,
                preview_confirm=decline)
        # the callback received the real preview
        assert shown and "PLAYBOOK EXECUTION PREVIEW" in shown[0]
        # nothing executed: no findings were sealed
        assert list((out / "findings").glob("*.json")) == []
        # the decline is audited, not swallowed
        audit = (out / "audit_log.jsonl").read_text(encoding="utf-8")
        assert "declined" in audit and "preflight" in audit

    def test_confirming_proceeds_and_is_audited(
        self, tmp_path: Path
    ) -> None:
        plan = _approved_plan(_segment_csv(tmp_path / "seg.csv"))
        pb = load_playbook(SEGMENT)
        out = tmp_path / "pkg"
        run(plan, pb, RULES, out, approvals=APPROVALS,
            preview_confirm=lambda text: True)
        audit = (out / "audit_log.jsonl").read_text(encoding="utf-8")
        assert "confirmed" in audit
        assert (out / "manifest.json").exists()


# ── the handoff manifest ─────────────────────────────────────────────────────


class TestHandoffManifest:
    def _run(self, tmp_path: Path) -> Path:
        plan = _approved_plan(_segment_csv(tmp_path / "seg.csv"))
        pb = load_playbook(SEGMENT)
        out = tmp_path / "pkg"
        run(plan, pb, RULES, out, approvals=APPROVALS)
        return out

    def test_written_with_null_signatures(self, tmp_path: Path) -> None:
        out = self._run(tmp_path)
        handoff = json.loads(
            (out / "handoff_manifest.json").read_text(encoding="utf-8")
        )
        teams = handoff["team_handoff"]
        assert set(teams) == {"data_engineering", "qa_quality_control",
                              "compliance", "manager"}
        for team in teams.values():
            assert team["signature"] is None  # the engine never signs
            assert team["checks"], "every team gets at least one check"

    def test_checks_reference_real_sealed_digests(
        self, tmp_path: Path
    ) -> None:
        out = self._run(tmp_path)
        handoff = json.loads(
            (out / "handoff_manifest.json").read_text(encoding="utf-8")
        )
        # gather the digests the pipeline actually sealed
        sealed = {
            json.loads(p.read_text(encoding="utf-8"))["sha256"]
            for p in (out / "findings").glob("*.json")
        }
        referenced = [
            c["evidence"]["sha256"]
            for team in handoff["team_handoff"].values()
            for c in team["checks"]
            if "sha256" in c.get("evidence", {})
        ]
        assert referenced, "checks must carry evidence digests"
        for digest in referenced:
            assert digest in sealed

    def test_row_count_check_matches_profile_findings(
        self, tmp_path: Path
    ) -> None:
        out = self._run(tmp_path)
        handoff = json.loads(
            (out / "handoff_manifest.json").read_text(encoding="utf-8")
        )
        profile = json.loads(
            (out / "findings" / "dq_profile.json").read_text("utf-8")
        )["findings"]
        totals = {c["total"] for c in profile["columns"]}
        assert len(totals) == 1  # one consistent row count in evidence
        de_checks = " ".join(
            c["check"]
            for c in handoff["team_handoff"]["data_engineering"]["checks"]
        )
        assert str(totals.pop()) in de_checks

    def test_stats_pipeline_gets_a_compliance_stats_check(
        self, tmp_path: Path
    ) -> None:
        out = self._run(tmp_path)
        handoff = json.loads(
            (out / "handoff_manifest.json").read_text(encoding="utf-8")
        )
        comp = " ".join(
            c["check"]
            for c in handoff["team_handoff"]["compliance"]["checks"]
        )
        assert "pre-registered alpha" in comp
        assert "effect sizes" in comp

    def test_plan_digest_binds_handoff_to_the_approved_plan(
        self, tmp_path: Path
    ) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        pb = load_playbook(SEGMENT)
        out = tmp_path / "pkg"
        run(plan, pb, RULES, out, approvals=APPROVALS)
        handoff = json.loads(
            (out / "handoff_manifest.json").read_text(encoding="utf-8")
        )
        assert handoff["pipeline"]["plan_sha256"] == plan.plan_digest()
        assert handoff["pipeline"]["approved_by"] == "Saif"

    def test_hashed_in_manifest_and_tamper_detectable(
        self, tmp_path: Path
    ) -> None:
        out = self._run(tmp_path)
        manifest = json.loads((out / "manifest.json").read_text("utf-8"))
        assert "handoff_manifest.json" in manifest["files"]
        recorded = manifest["files"]["handoff_manifest.json"]
        path = out / "handoff_manifest.json"
        assert file_sha256(path) == recorded
        # forge a signature after packaging: verification must catch it
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged["team_handoff"]["compliance"]["signature"] = "Mallory, 2026"
        path.write_text(json.dumps(forged, indent=2, sort_keys=True),
                        encoding="utf-8")
        assert file_sha256(path) != recorded

    def test_deterministic_across_runs(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        pb = load_playbook(SEGMENT)
        run(plan, pb, RULES, tmp_path / "p1", approvals=APPROVALS)
        run(plan, pb, RULES, tmp_path / "p2", approvals=APPROVALS)
        h1 = (tmp_path / "p1" / "handoff_manifest.json").read_text("utf-8")
        h2 = (tmp_path / "p2" / "handoff_manifest.json").read_text("utf-8")
        assert h1 == h2


# ── the interactive helper (step-16 hunt, H8) ────────────────────────────────


class TestPromptConfirmation:
    def test_enter_and_yes_proceed(self, monkeypatch: Any, capsys: Any) -> None:
        from delivery_engine.preview import prompt_confirmation

        for typed in ("", "y", "YES"):
            monkeypatch.setattr("builtins.input",
                                lambda _="", t=typed: t)
            assert prompt_confirmation("PREVIEW TEXT") is True
        out = capsys.readouterr().out
        assert "PREVIEW TEXT" in out  # the human saw the preview

    def test_n_declines(self, monkeypatch: Any) -> None:
        from delivery_engine.preview import prompt_confirmation

        monkeypatch.setattr("builtins.input", lambda _="": "n")
        assert prompt_confirmation("PREVIEW TEXT") is False

    def test_declined_dir_refuses_rerun_with_clear_message(
        self, tmp_path: Path
    ) -> None:
        """H4: a declined run leaves its preview + audit in out_dir; a
        re-run into the same dir is refused by the existing stale-files
        rule, and the decline message tells the human to use a fresh
        directory."""
        from delivery_engine import ExecutorError

        src = _segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        pb = load_playbook(SEGMENT)
        out = tmp_path / "pkg"
        with pytest.raises(ExecutionStopped, match="FRESH output"):
            run(plan, pb, RULES, out, approvals=APPROVALS,
                preview_confirm=lambda _: False)
        with pytest.raises(ExecutorError, match="not empty"):
            run(plan, pb, RULES, out, approvals=APPROVALS)
