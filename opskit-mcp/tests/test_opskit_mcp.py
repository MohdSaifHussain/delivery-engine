"""Tests for opskit-mcp — planted-answer principle throughout.

The surge fixture plants a true conditional story (service='payments',
within it severity='P2'); tests verify the MCP surface returns exactly
that path as structured data, that envelopes reproduce hashes, that the
protocol stream stays clean, and that every user mistake earns a readable
OpsKitError, never a traceback.
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from opskit_mcp import VENDORED_OPSKIT_SHA256
from opskit_mcp._vendor.opskit4 import OpsKitError
from opskit_mcp.envelope import ENVELOPE_SCHEMA, sha256_of, wrap
from opskit_mcp.server import (
    opskit_drill,
    opskit_explain_playbook,
    opskit_list_playbooks,
    opskit_run_playbook,
)
from opskit_mcp.service import (
    drill_payload,
    explain_playbook_payload,
    list_playbooks_payload,
    run_playbook_payload,
)

VENDOR_FILE = (
    Path(__file__).resolve().parents[1]
    / "src" / "opskit_mcp" / "_vendor" / "opskit4.py"
)


@pytest.fixture()
def surge_csv(tmp_path: Path) -> Path:
    """Calm 5/day then surge 12/day; surge driven by service='payments',
    WITHIN payments by severity='P2'. Plus an amount column: payments rows
    carry 900.0 in the surge week (for sum-metric drilling), else 100.0."""
    p = tmp_path / "inc.csv"
    end = datetime(2026, 7, 6, 12, 0)
    rows: list[list[str]] = []
    n = 1
    for off in range(56, -1, -1):
        day = end - timedelta(days=off)
        per_day = 12 if off <= 7 else 5
        for i in range(per_day):
            if off <= 7 and i % 2 == 0:
                svc, sev = "payments", ("P2" if i % 3 != 0 else "P3")
                amt = 900.0
            else:
                svc, sev, amt = "cards", "P3", 100.0
            rows.append([f"I-{n:04d}", day.strftime("%Y-%m-%d 10:00:00"),
                         sev, svc, "owner" if i else "", f"{amt:.2f}"])
            n += 1
    rows.append(list(rows[0]))
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["incident_id", "opened_at", "severity", "service",
                    "owner", "amount"])
        w.writerows(rows)
    return p


@pytest.fixture()
def clean_csv(tmp_path: Path) -> Path:
    p = tmp_path / "clean.csv"
    p.write_text("id,category\n1,a\n2,b\n3,a\n", encoding="utf-8")
    return p


class TestVendorSeal:
    def test_vendored_file_hash_matches_recorded_constant(self) -> None:
        actual = hashlib.sha256(VENDOR_FILE.read_bytes()).hexdigest()
        assert actual == VENDORED_OPSKIT_SHA256, (
            "vendored opskit4.py differs from the recorded seal — either "
            "the file was tampered with or the seal was not updated with "
            "a deliberate re-vendor"
        )


class TestEnvelope:
    def test_hash_is_order_independent(self) -> None:
        a = {"x": 1, "y": [1, 2], "z": {"b": 2, "a": 1}}
        b = {"z": {"a": 1, "b": 2}, "y": [1, 2], "x": 1}
        assert sha256_of(a) == sha256_of(b)

    def test_wrap_carries_schema_and_hash(self) -> None:
        env = wrap("t", {"k": "v"})
        assert env["schema"] == ENVELOPE_SCHEMA
        assert env["payload_sha256"] == sha256_of({"k": "v"})
        assert env["vendored_opskit_sha256"] == VENDORED_OPSKIT_SHA256
        assert env["generated_at"].endswith("+05:30")   # IST, tz-aware

    def test_run_payload_hash_reproduces(self, surge_csv: Path) -> None:
        first = run_playbook_payload("weekly-review", str(surge_csv))
        second = run_playbook_payload("weekly-review", str(surge_csv))
        assert sha256_of(first) == sha256_of(second)


class TestDrillTool:
    def test_finds_planted_conditional_path(self, surge_csv: Path) -> None:
        payload = drill_payload(str(surge_csv))
        assert payload["refused"] is False
        path = payload["path"]
        assert path, "drill returned nothing"
        assert path[0]["level"] == 1
        assert path[0]["column"] == "service"
        assert path[0]["value"] == "payments"
        assert 0 < abs(path[0]["contribution"]) <= 1.5
        if len(path) > 1:
            assert path[1]["column"] == "severity"
            assert path[1]["value"] == "P2"

    def test_sum_metric_carries_through(self, surge_csv: Path) -> None:
        payload = drill_payload(str(surge_csv), metric="sum:amount")
        assert payload["metric"] == "sum(amount)"
        path = payload["path"]
        assert path and path[0]["column"] == "service"
        assert path[0]["value"] == "payments"
        # regression guard inherited from OpsKit: level-2 values must be
        # sums computed INSIDE payments, not row counts dressed as money
        if len(path) > 1:
            assert path[1]["current"] > 500

    def test_avg_metric_returns_structured_refusal(
        self, surge_csv: Path
    ) -> None:
        payload = drill_payload(str(surge_csv), metric="avg:amount")
        assert payload["refused"] is True
        assert "Simpson" in payload["reason"]
        assert payload["path"] == []

    def test_invalid_metric_kind_raises(self, surge_csv: Path) -> None:
        with pytest.raises(OpsKitError, match="Unknown metric kind"):
            drill_payload(str(surge_csv), metric="sparkle:amount")

    def test_metric_on_non_numeric_column_raises(
        self, surge_csv: Path
    ) -> None:
        with pytest.raises(OpsKitError, match="not numeric"):
            drill_payload(str(surge_csv), metric="sum:service")


class TestRunPlaybook:
    def test_findings_are_schema_versioned(self, surge_csv: Path) -> None:
        payload = run_playbook_payload("data-quality", str(surge_csv))
        assert payload["findings"]
        for rec in payload["findings"]:
            assert rec["schema"] == "opskit.finding/v1"
            assert rec["severity"] in ("INFO", "NOTABLE", "CRITICAL")

    def test_gate_stops_on_critical(self, surge_csv: Path) -> None:
        payload = run_playbook_payload("weekly-review", str(surge_csv))
        assert payload["critical_findings"] >= 1
        assert payload["gate"] == "stop"

    def test_gate_passes_when_clean(self, clean_csv: Path) -> None:
        payload = run_playbook_payload("data-quality", str(clean_csv))
        assert payload["critical_findings"] == 0
        assert payload["gate"] == "pass"

    def test_assumptions_captured_as_data(self, surge_csv: Path) -> None:
        payload = run_playbook_payload("weekly-review", str(surge_csv))
        joined = " ".join(payload["assumptions"])
        assert "time column" in joined
        assert "opened_at" in joined

    def test_source_identified_by_hash_not_path(
        self, surge_csv: Path
    ) -> None:
        payload = run_playbook_payload("data-quality", str(surge_csv))
        assert payload["source_name"] == surge_csv.name
        assert payload["source_sha256"] == hashlib.sha256(
            surge_csv.read_bytes()
        ).hexdigest()
        assert str(surge_csv.parent) not in str(payload)


class TestErrors:
    def test_unknown_playbook_raises(self, surge_csv: Path) -> None:
        with pytest.raises(OpsKitError, match="No playbook 'ghost'"):
            run_playbook_payload("ghost", str(surge_csv))

    def test_missing_source_raises(self) -> None:
        with pytest.raises(OpsKitError, match="Source not found"):
            run_playbook_payload("data-quality", "/no/such/file.csv")

    def test_explicit_missing_config_refuses_silent_fallback(
        self, surge_csv: Path
    ) -> None:
        with pytest.raises(OpsKitError, match="Config file not found"):
            run_playbook_payload(
                "data-quality", str(surge_csv),
                config_path="/no/such/opskit.toml",
            )

    def test_unknown_threshold_key_raises(
        self, surge_csv: Path, tmp_path: Path
    ) -> None:
        bad = tmp_path / "opskit.toml"
        bad.write_text("[thresholds]\nsparkle = 3\n", encoding="utf-8")
        with pytest.raises(OpsKitError, match="unknown keys"):
            run_playbook_payload(
                "data-quality", str(surge_csv), config_path=str(bad)
            )

    def test_unknown_custom_step_raises(
        self, surge_csv: Path, tmp_path: Path
    ) -> None:
        bad = tmp_path / "opskit.toml"
        bad.write_text(
            '[playbooks.broken]\ntitle = "b"\ndescription = "d"\n'
            'steps = ["shape", "teleport"]\n',
            encoding="utf-8",
        )
        with pytest.raises(OpsKitError, match="unknown steps"):
            list_playbooks_payload(config_path=str(bad))


class TestLoopholeRegressions:
    """Each fix from the Step 6 loophole hunt lands with a test proving
    the old failure."""

    def test_bogus_metric_rejected_even_without_volume_step(
        self, surge_csv: Path
    ) -> None:
        """LOOPHOLE: data-quality has no volume step, so a supplied metric
        was never validated — the audit record claimed an unvalidated
        metric produced the findings. Now validated eagerly."""
        with pytest.raises(OpsKitError, match="Unknown metric kind"):
            run_playbook_payload(
                "data-quality", str(surge_csv), metric="sparkle:amount"
            )

    def test_nonexistent_metric_column_rejected_eagerly(
        self, surge_csv: Path
    ) -> None:
        with pytest.raises(OpsKitError, match="does not exist"):
            run_playbook_payload(
                "data-quality", str(surge_csv), metric="sum:ghost"
            )

    def test_source_hash_is_sealed_before_execution(
        self, surge_csv: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LOOPHOLE: the source hash was computed after the run, so a
        mid-run swap would be recorded as if it were the input. The seal
        must be taken before build_context ever opens the file."""
        import opskit_mcp.service as svc

        original_hash = hashlib.sha256(surge_csv.read_bytes()).hexdigest()
        real_build = svc.build_context

        def swap_then_build(*args: Any, **kwargs: Any) -> Any:
            ctx = real_build(*args, **kwargs)
            # same schema, different content — a schema-changing swap
            # crashes DuckDB's lazy view outright (a defense in itself);
            # this test isolates the hash-ordering question
            surge_csv.write_text(
                "incident_id,opened_at,severity,service,owner,amount\n"
                "I-9999,2026-07-06 10:00:00,P3,cards,owner,1.00\n",
                encoding="utf-8",
            )
            return ctx

        monkeypatch.setattr(svc, "build_context", swap_then_build)
        payload = run_playbook_payload("data-quality", str(surge_csv))
        assert payload["source_sha256"] == original_hash, (
            "recorded hash must be the pre-execution seal, not the "
            "swapped file"
        )


class TestConfig:
    def test_supplied_config_is_hashed_and_applied(
        self, surge_csv: Path, tmp_path: Path
    ) -> None:
        toml = tmp_path / "opskit.toml"
        toml.write_text(
            "[thresholds]\ndrill_threshold = 0.5\n", encoding="utf-8"
        )
        payload = drill_payload(str(surge_csv), config_path=str(toml))
        cfg = payload["config"]
        assert cfg["source"] == "opskit.toml"
        assert cfg["file_sha256"] == hashlib.sha256(
            toml.read_bytes()
        ).hexdigest()
        assert cfg["resolved"]["drill_threshold"] == 0.5

    def test_defaults_recorded_when_no_config(self, clean_csv: Path) -> None:
        payload = run_playbook_payload("data-quality", str(clean_csv))
        assert payload["config"]["source"] == "defaults"
        assert payload["config"]["file_sha256"] is None
        assert payload["config"]["resolved"]["drill_threshold"] == 0.20

    def test_custom_toml_playbook_runs_end_to_end(
        self, surge_csv: Path, tmp_path: Path
    ) -> None:
        toml = tmp_path / "opskit.toml"
        toml.write_text(
            '[playbooks.claims-review]\ntitle = "Claims"\n'
            'description = "domain pack"\n'
            'steps = ["shape", "missing", "time_coverage", "volume_change"]\n',
            encoding="utf-8",
        )
        payload = run_playbook_payload(
            "claims-review", str(surge_csv), config_path=str(toml)
        )
        assert payload["playbook"] == "claims-review"
        assert {f["step"] for f in payload["findings"]} <= {
            "shape", "missing", "time_coverage", "volume_change",
            "recommendations",   # OpsKit's runner appends this to every run
        }
        listed = list_playbooks_payload(config_path=str(toml))
        origins = {p["key"]: p["origin"] for p in listed["playbooks"]}
        assert origins["claims-review"] == "custom"


class TestStdoutIsolation:
    """Per the MCP spec, a stdio server must never write non-protocol
    bytes to stdout. OpsKit prints assumptions; the wrapper must swallow
    every byte of it."""

    def test_service_calls_write_nothing_to_stdout(
        self, surge_csv: Path
    ) -> None:
        sentinel = io.StringIO()
        with redirect_stdout(sentinel):
            run_playbook_payload("weekly-review", str(surge_csv))
            drill_payload(str(surge_csv))
            drill_payload(str(surge_csv), metric="avg:amount")
            list_playbooks_payload()
            explain_playbook_payload("weekly-review")
        assert sentinel.getvalue() == ""

    def test_tool_functions_write_nothing_to_stdout(
        self, surge_csv: Path
    ) -> None:
        sentinel = io.StringIO()
        real = sys.stdout
        try:
            sys.stdout = sentinel
            opskit_run_playbook("weekly-review", str(surge_csv))
            opskit_drill(str(surge_csv))
            opskit_list_playbooks()
            opskit_explain_playbook("weekly-review")
        finally:
            sys.stdout = real
        assert sentinel.getvalue() == ""


class TestServerSurface:
    def test_tools_return_hashed_envelopes(self, surge_csv: Path) -> None:
        env: dict[str, Any] = opskit_run_playbook(
            "data-quality", str(surge_csv)
        )
        assert env["schema"] == ENVELOPE_SCHEMA
        assert env["tool"] == "opskit_run_playbook"
        assert env["payload_sha256"] == sha256_of(env["payload"])

    def test_drill_tool_envelope(self, surge_csv: Path) -> None:
        env: dict[str, Any] = opskit_drill(str(surge_csv))
        assert env["tool"] == "opskit_drill"
        assert env["payload"]["path"][0]["value"] == "payments"
