"""Step 8 tests - the ops_report slot and the verbatim-provenance control.

The critical property under test: numbers reach the report ONLY from the
hashed Findings Store. OpsKit finding texts carry numbers in prose, so
the injector gained inject_from_findings: it proves the exact text lives
inside the stage's stored findings before registering its tokens. Text
that is not verbatim store content is refused; a number a builder writes
itself still fails verification. Charter 4.1 extended, not weakened.
"""
from __future__ import annotations

import csv
import json
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from delivery_engine import approve_plan, load_playbook, make_plan, run
from delivery_engine.store import (
    FindingsStore,
    NumberInjector,
    StoreError,
    verify_artifact_numbers,
)

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"


def _surge_csv(path: Path) -> Path:
    end = datetime(2026, 7, 6, 12, 0)
    rows: list[list[str]] = []
    n = 1
    for off in range(56, -1, -1):
        day = end - timedelta(days=off)
        per_day = 12 if off <= 7 else 5
        for i in range(per_day):
            if off <= 7 and i % 2 == 0:
                svc, sev = "payments", ("P2" if i % 3 != 0 else "P3")
            else:
                svc, sev = "cards", "P3"
            rows.append([f"I-{n:04d}", day.strftime("%Y-%m-%d 10:00:00"),
                         sev, svc, f"{100.0 + i:.2f}"])
            n += 1
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["incident_id", "opened_at", "severity", "service", "amount"])
        w.writerows(rows)
    return path


def _col(name: str, dtype: str, total: int, nulls: int, distinct: int) -> dict[str, Any]:
    return {
        "name": name, "dtype": dtype, "total": total, "nulls": nulls,
        "completeness": 1.0, "distinct": distinct, "case_variants": 0,
        "valid_ratio": 1.0,
    }


def _surge_profile(total: int = 469) -> dict[str, Any]:
    return {
        "columns": [
            _col("incident_id", "VARCHAR", total, 0, total),
            _col("opened_at", "TIMESTAMP", total, 0, 57),
            _col("severity", "VARCHAR", total, 0, 2),
            _col("service", "VARCHAR", total, 0, 2),
            _col("amount", "DOUBLE", total, 0, 12),
        ],
        "dama_scores": {"completeness": 1.0},
    }


@pytest.fixture()
def fake_analystkit_mcp(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"findings": _surge_profile()}

    def tool_profile(source: str, table: str | None) -> str:
        return json.dumps({"findings": state["findings"], "sha256": "planted"})

    tools = types.ModuleType("analystkit_mcp.tools")
    tools.tool_profile = tool_profile  # type: ignore[attr-defined]
    pkg = types.ModuleType("analystkit_mcp")
    pkg.tools = tools  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "analystkit_mcp", pkg)
    monkeypatch.setitem(sys.modules, "analystkit_mcp.tools", tools)
    return state


def _approved_ops_plan(src: Path, findings: dict[str, Any]):  # type: ignore[no-untyped-def]
    plan = make_plan(
        "operational review of incident volume trends", str(src),
        findings, PLAYBOOKS,
    )
    return approve_plan(plan, "Saif")


# ── The verbatim-provenance control, unit level ──────────────────────────────


class TestInjectFromFindings:
    def _store(self) -> FindingsStore:
        store = FindingsStore()
        store.put("ops", {
            "findings": [
                {"step": "volume_change", "severity": "CRITICAL",
                 "text": "Volume rose 140% (35 -> 84) in the last window."},
            ],
            "assumptions": ["Assuming time column: opened_at"],
        })
        return store

    def test_verbatim_store_text_is_injected(self) -> None:
        store = self._store()
        inj = NumberInjector(store)
        text = inj.inject_from_findings(
            "ops", "Volume rose 140% (35 -> 84) in the last window."
        )
        assert "140" in inj.emitted
        assert "35" in inj.emitted and "84" in inj.emitted
        # the artifact containing exactly this text now verifies
        verify_artifact_numbers(text, inj)

    def test_non_store_text_refused(self) -> None:
        """The old failure this control prevents: prose the AI wrote
        itself, smuggling its own numbers."""
        store = self._store()
        inj = NumberInjector(store)
        with pytest.raises(StoreError, match="verbatim"):
            inj.inject_from_findings("ops", "Volume rose 999% last week.")

    def test_near_miss_text_refused(self) -> None:
        """One character different from store content is not store
        content."""
        store = self._store()
        inj = NumberInjector(store)
        with pytest.raises(StoreError, match="verbatim"):
            inj.inject_from_findings(
                "ops", "Volume rose 141% (35 -> 84) in the last window."
            )

    def test_foreign_number_still_fails_verification(self) -> None:
        """inject_from_findings extends the allowlist with store tokens
        ONLY - a number the builder writes itself is still a violation."""
        store = self._store()
        inj = NumberInjector(store)
        quoted = inj.inject_from_findings(
            "ops", "Volume rose 140% (35 -> 84) in the last window."
        )
        artifact = quoted + "\nSeparately, revenue grew 777 units."
        with pytest.raises(StoreError, match="777"):
            verify_artifact_numbers(artifact, inj)

    def test_unknown_stage_refused(self) -> None:
        store = self._store()
        inj = NumberInjector(store)
        with pytest.raises(StoreError, match="No findings"):
            inj.inject_from_findings("ghost", "anything")


# ── The ops_report stage end to end ──────────────────────────────────────────


class TestOpsReportEndToEnd:
    def test_report_written_and_verified(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any]
    ) -> None:
        src = _surge_csv(tmp_path / "inc.csv")
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        out = run(plan, pb, [], tmp_path / "out")

        report = (out / "ops_report.md").read_text(encoding="utf-8")
        assert "# Operational Review Report" in report
        assert "weekly-review" in report
        # the planted surge's critical finding text must appear verbatim
        stored = json.loads((out / "findings" / "ops_review.json").read_text())
        crit_texts = [f["text"] for f in stored["findings"]["findings"]
                      if f["severity"] == "CRITICAL"]
        assert crit_texts
        assert any(t in report for t in crit_texts)
        # audit records the artifact with its hash
        entries = [
            json.loads(line) for line in
            (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        rep = next(e for e in entries if e["stage"] == "report")
        assert rep["outcome"] == "artifact_written"
        assert "sha256" in rep

    def test_report_byte_reproducible(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any]
    ) -> None:
        """Charter 4.8: artifacts carry no timestamps; same findings,
        byte-identical report."""
        import os

        src = _surge_csv(tmp_path / "inc.csv")
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        out_a = run(plan, pb, [], tmp_path / "a")
        out_b = run(plan, pb, [], tmp_path / "b")
        ma = json.loads((out_a / "manifest.json").read_text())
        mb = json.loads((out_b / "manifest.json").read_text())
        assert ma["files"]["ops_report.md"] == mb["files"]["ops_report.md"]
        ops_key = os.path.join("findings", "ops_review.json")
        assert ma["files"][ops_key] == mb["files"][ops_key]

    def test_report_stage_appears_in_manifest_and_deliverables(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any]
    ) -> None:
        src = _surge_csv(tmp_path / "inc.csv")
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        assert "ops_report" in pb.artifacts
        out = run(plan, pb, [], tmp_path / "out")
        manifest = json.loads((out / "manifest.json").read_text())
        assert "ops_report.md" in manifest["files"]


# ── Constitution: the new slot obeys the old rules ───────────────────────────


class TestLoopholeRegressions:
    """Step 8 loophole hunt: each fix lands with a test proving the old
    failure."""

    def test_unknown_severity_fails_closed(self) -> None:
        """LOOPHOLE: a finding with an unexpected severity landed in the
        counts but silently vanished from the narrative. Fail closed."""
        from delivery_engine.artifacts import build_ops_report

        store = FindingsStore()
        store.put("ops", {
            "findings": [
                {"step": "shape", "severity": "APOCALYPTIC",
                 "text": "something new"},
            ],
            "assumptions": [],
        })
        inj = NumberInjector(store)
        with pytest.raises(StoreError, match="APOCALYPTIC"):
            build_ops_report(store, inj, "s.csv", "goal", "ops")

    def test_wrong_needs_target_is_clean_error(self) -> None:
        """LOOPHOLE: needs pointing at a non-OpsKit stage (a profile)
        crashed with a raw KeyError. Now a clean StoreError."""
        from delivery_engine.artifacts import build_ops_report

        store = FindingsStore()
        store.put("dq_profile", _surge_profile())
        inj = NumberInjector(store)
        with pytest.raises(StoreError, match="OpsKit-shaped"):
            build_ops_report(store, inj, "s.csv", "goal", "dq_profile")


class TestConstitutionStillHolds:
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

    def test_ops_report_requires_findings_store(self, tmp_path: Path) -> None:
        from delivery_engine import PlaybookError

        body = self.HEAD + """
[[stages]]
id = "report"
kind = "ai"
slot = "ops_report"
numbers_from = "model_generated"
needs = ["gate"]
""" + self.TAIL
        p = tmp_path / "pb.toml"
        p.write_text(body, encoding="utf-8")
        with pytest.raises(PlaybookError, match="injected-numbers"):
            load_playbook(p)

    def test_ops_report_without_needs_is_clean_executor_error(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any]
    ) -> None:
        """Declared inputs, never guessed: an ops_report stage that names
        no findings stage is refused with a clean error."""
        from delivery_engine import ExecutorError

        body = self.HEAD.replace('name = "t"', 'name = "ops_noneeds"') + """
[[stages]]
id = "report"
kind = "ai"
slot = "ops_report"
numbers_from = "findings_store"

[[stages]]
id = "package"
kind = "package"
needs = ["report"]
""" + self.TAIL
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "ops_noneeds.toml").write_text(body, encoding="utf-8")
        src = _surge_csv(tmp_path / "inc.csv")
        plan = make_plan("x", str(src), fake_analystkit_mcp["findings"], lib)
        plan = approve_plan(plan, "Saif")
        pb = load_playbook(lib / "ops_noneeds.toml")
        with pytest.raises(ExecutorError, match="declared inputs"):
            run(plan, pb, [], tmp_path / "out")
