"""Step 7 tests - the OpsKit stage wired into the engine.

Planted answers: a surge CSV whose weekly-review findings contain
operational criticals (insights, must not stop the pipeline) and a
zero-row source (unfitness, must stop). The opskit path runs the REAL
opskit_mcp wrapper end to end. The analystkit_profile stage is faked
with a synthetic envelope (the test_planner precedent for the Anthropic
SDK): the object under test here is the OpsKit wiring; full-suite
certification with the real analystkit_mcp runs on the private repo.
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

from delivery_engine import (
    ExecutionStopped,
    PlaybookError,
    approve_plan,
    load_playbook,
    make_plan,
    run,
)

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"

VALID_HEAD = """
schema_version = 1

[playbook]
name = "test"
version = "1.0.0"
description = "test playbook"
"""

VALID_GATE_STAGE = """
[[stages]]
id = "gate"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"
"""

VALID_TAIL = """
[deliverables]
artifacts = ["audit_log", "manifest"]
"""


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "pb.toml"
    p.write_text(body, encoding="utf-8")
    return p


def _surge_csv(path: Path) -> Path:
    """Calm then surge, driven by payments/P2 - weekly-review will emit
    operational CRITICALs. Those are insights, not unfitness."""
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
    """Synthetic analystkit_profile findings matching the surge CSV's
    shape: id + timestamp + categoricals + numeric. The same findings
    feed the plan and the faked profile stage, so the executor's TOCTOU
    classification check holds by construction."""
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
    """Installs a fake analystkit_mcp whose tool_profile returns a planted
    envelope. Mutable via the returned dict ('findings' key)."""
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
    assert plan.playbook_name == "ops_review"
    return approve_plan(plan, "Saif")


# ── V11: the constitution extends to opskit stages ───────────────────────────


class TestV11OpsPlaybookKey:
    def test_missing_ops_playbook_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE + """
[[stages]]
id = "ops"
kind = "kit"
tool = "opskit_run_playbook"
gate = "must_pass"
needs = ["gate"]
""" + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V11\)"):
            load_playbook(_write(tmp_path, body))

    def test_ops_playbook_on_wrong_tool_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + """
[[stages]]
id = "gate"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"
ops_playbook = "weekly-review"
""" + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V11\)"):
            load_playbook(_write(tmp_path, body))

    def test_invalid_ops_playbook_key_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE + """
[[stages]]
id = "ops"
kind = "kit"
tool = "opskit_run_playbook"
ops_playbook = "Weekly Review!"
gate = "must_pass"
needs = ["gate"]
""" + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V11\)"):
            load_playbook(_write(tmp_path, body))

    def test_ops_review_archetype_loads(self) -> None:
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        ops = next(s for s in pb.stages if s.stage_id == "ops_review")
        assert ops.tool == "opskit_run_playbook"
        assert ops.ops_playbook == "weekly-review"
        assert "timestamp_column" in pb.requirements.required_kinds


# ── Planner routing: the goal reaches the new archetype ──────────────────────


class TestRouting:
    def test_goal_routes_to_ops_review(self, tmp_path: Path) -> None:
        src = _surge_csv(tmp_path / "inc.csv")
        plan = make_plan(
            "operational review of incident volume trends", str(src),
            _surge_profile(), PLAYBOOKS,
        )
        assert plan.playbook_name == "ops_review"


# ── The ops stage end to end (real opskit_mcp) ───────────────────────────────


class TestLoopholeRegressions:
    """Step 7 loophole hunt: each fix lands with a test proving the old
    failure."""

    def test_unknown_envelope_schema_refused(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """LOOPHOLE: the engine consumed any envelope without checking
        its schema id - a future v2 envelope would be interpreted by
        guesswork. Fail closed on unknown schemas."""
        import opskit_mcp.server as srv

        real = srv.opskit_run_playbook

        def future_schema(playbook: str, source: str, **kwargs: Any) -> dict[str, Any]:
            env = real(playbook, source, **kwargs)
            env["schema"] = "opskit.envelope/v2"
            return env

        monkeypatch.setattr(srv, "opskit_run_playbook", future_schema)
        src = _surge_csv(tmp_path / "inc.csv")
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out")
        assert "not supported" in exc_info.value.reason

    def test_sealed_but_malformed_payload_refused(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """LOOPHOLE: the seal proves integrity, not shape. A correctly
        re-sealed payload whose findings are not finding objects crashed
        after the seal check with a raw traceback. Now a clean stop."""
        import opskit_mcp.server as srv
        from opskit_mcp.envelope import sha256_of

        real = srv.opskit_run_playbook

        def malformed(playbook: str, source: str, **kwargs: Any) -> dict[str, Any]:
            env = real(playbook, source, **kwargs)
            env["payload"]["findings"] = "not a list"
            env["payload_sha256"] = sha256_of(env["payload"])  # re-sealed!
            return env

        monkeypatch.setattr(srv, "opskit_run_playbook", malformed)
        src = _surge_csv(tmp_path / "inc.csv")
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out")
        assert "malformed" in exc_info.value.reason


class TestOpsStageEndToEnd:
    def test_insight_criticals_pass_and_package_seals(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any]
    ) -> None:
        """The planted surge yields operational CRITICALs. Declared
        semantics: insights are evidence, not unfitness - the pipeline
        completes and the package seals."""
        src = _surge_csv(tmp_path / "inc.csv")
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        out = run(plan, pb, [], tmp_path / "out")

        assert (out / "manifest.json").exists()
        stored = json.loads((out / "findings" / "ops_review.json").read_text())
        crit = [f for f in stored["findings"]["findings"]
                if f["severity"] == "CRITICAL"]
        assert crit, "the planted surge must yield operational criticals"
        assert all(f["step"] != "shape" for f in crit)

        entries = [
            json.loads(line) for line in
            (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        ops_entry = next(e for e in entries if e["stage"] == "ops_review")
        assert ops_entry["outcome"] == "pass"
        assert "recorded as evidence" in ops_entry["rationale"]
        assert "seal verified" in ops_entry["rationale"]

        manifest = json.loads((out / "manifest.json").read_text())
        assert "ops_review" in manifest["findings"]

    def test_zero_row_source_is_unfit_and_stops(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any]
    ) -> None:
        """OpsKit's shape critical (zero rows) is data unfitness - the
        must_pass gate stops the pipeline."""
        src = tmp_path / "empty.csv"
        src.write_text(
            "incident_id,opened_at,severity,service,amount\n",
            encoding="utf-8",
        )
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out")
        assert exc_info.value.stage_id == "ops_review"
        assert "unfit" in exc_info.value.reason

    def test_seal_mismatch_refused(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A payload altered between the wrapper and the engine must not
        enter the Findings Store - the engine verifies the kit's seal."""
        import opskit_mcp.server as srv

        real = srv.opskit_run_playbook

        def tampered(playbook: str, source: str, **kwargs: Any) -> dict[str, Any]:
            env = real(playbook, source, **kwargs)
            env["payload"]["critical_findings"] = 0   # alter after sealing
            return env

        monkeypatch.setattr(srv, "opskit_run_playbook", tampered)
        src = _surge_csv(tmp_path / "inc.csv")
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out")
        assert "seal" in exc_info.value.reason

    def test_unknown_opskit_playbook_stops_cleanly(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any]
    ) -> None:
        body = VALID_HEAD.replace('name = "test"', 'name = "ops_ghost"') + """
[[stages]]
id = "dq_profile"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"

[[stages]]
id = "ops_review"
kind = "kit"
tool = "opskit_run_playbook"
ops_playbook = "ghost-book"
gate = "must_pass"
needs = ["dq_profile"]

[[stages]]
id = "package"
kind = "package"
needs = ["ops_review"]
""" + VALID_TAIL
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "ops_ghost.toml").write_text(body, encoding="utf-8")
        src = _surge_csv(tmp_path / "inc.csv")
        plan = make_plan(
            "ghost", str(src), fake_analystkit_mcp["findings"], lib
        )
        plan = approve_plan(plan, "Saif")
        pb = load_playbook(lib / "ops_ghost.toml")
        with pytest.raises(ExecutionStopped) as exc_info:
            run(plan, pb, [], tmp_path / "out")
        assert exc_info.value.stage_id == "ops_review"
        assert "kit tool failed" in exc_info.value.reason
        assert "ghost-book" in exc_info.value.reason

    def test_package_reproducible(
        self, tmp_path: Path, fake_analystkit_mcp: dict[str, Any]
    ) -> None:
        """Same source, same plan - the ops findings digests must match
        across runs (charter 4.8)."""
        src = _surge_csv(tmp_path / "inc.csv")
        plan = _approved_ops_plan(src, fake_analystkit_mcp["findings"])
        pb = load_playbook(PLAYBOOKS / "ops_review.toml")
        out_a = run(plan, pb, [], tmp_path / "a")
        out_b = run(plan, pb, [], tmp_path / "b")
        ma = json.loads((out_a / "manifest.json").read_text())
        mb = json.loads((out_b / "manifest.json").read_text())
        assert ma["findings"] == mb["findings"]
        import os
        ops_key = os.path.join("findings", "ops_review.json")
        assert ops_key in ma["files"], (
            f"expected '{ops_key}' in manifest; got keys: {list(ma['files'])}"
        )
        assert ma["files"][ops_key] == mb["files"][ops_key]
