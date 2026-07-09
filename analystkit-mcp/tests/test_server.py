"""analystkit-mcp tests — planted-answer principle through the REAL protocol.

Two layers:
1. Direct tool-function tests (fast, precise assertions on findings)
2. Protocol tests via the SDK's in-memory client session — the same
   code path a real MCP client exercises (list_tools, call_tool),
   so the wiring itself is under test, not just the logic.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from analystkit_mcp import tools
from analystkit_mcp.findings import envelope
from analystkit_mcp.server import mcp

# ── Planted fixtures (the same answer key philosophy as AnalystKit) ─────────


@pytest.fixture()
def messy_csv(tmp_path: Path) -> Path:
    """Planted: 2 null emails, 1 bad email, 1 negative amount, 1 future
    date, case variants, 1 exact dup row, 2 reused order ids."""
    p = tmp_path / "orders.csv"
    rows = [
        ["O-1", "C-1", "a@x.com", "2026-06-01 10:00:00", "100.0", "paid"],
        ["O-2", "C-1", "", "2026-06-02 10:00:00", "200.0", "paid"],
        ["O-3", "C-2", "", "2026-06-03 10:00:00", "-50.0", "PAID"],
        ["O-4", "C-2", "not-an-email", "2026-06-04 10:00:00", "300.0", "shipped"],
        ["O-5", "C-3", "b@x.com", "2099-01-01 10:00:00", "400.0", " paid"],
        ["O-1", "C-3", "c@x.com", "2026-06-05 10:00:00", "500.0", "delivered"],
        ["O-6", "C-9", "d@x.com", "2026-06-06 10:00:00", "600.0", "paid"],
        ["O-6", "C-9", "d@x.com", "2026-06-06 10:00:00", "600.0", "paid"],
    ]
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["order_id", "customer_id", "email", "order_date", "amount", "status"])
        w.writerows(rows)
    return p


@pytest.fixture()
def reference_csv(tmp_path: Path) -> Path:
    p = tmp_path / "customers.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "region"])
        w.writerows([["C-1", "N"], ["C-2", "S"], ["C-3", "E"], ["C-4", "W"]])
    return p


def _findings(result_json: str) -> dict[str, Any]:
    body = json.loads(result_json)
    assert set(body) == {"tool", "source", "run_at_ist", "findings", "sha256"}
    return dict(body["findings"])


# ── Envelope: the Findings Store contract ────────────────────────────────────


class TestEnvelope:
    def test_hash_covers_findings_only_not_timestamp(self) -> None:
        """Same findings must hash the same even at different run times —
        this is what makes evidence re-performable."""
        a = json.loads(envelope("t", "s", {"x": 1}))
        b = json.loads(envelope("t", "s", {"x": 1}))
        assert a["sha256"] == b["sha256"]

    def test_hash_changes_with_findings(self) -> None:
        a = json.loads(envelope("t", "s", {"x": 1}))
        b = json.loads(envelope("t", "s", {"x": 2}))
        assert a["sha256"] != b["sha256"]

    def test_digest_matches_toolkit_algorithm(self) -> None:
        """One digest algorithm across the ecosystem: the MCP layer's hash
        must verify against analystkit.ai.findings_digest."""
        from analystkit.ai import findings_digest

        payload = {"rules_evaluated": 2, "total_exceptions": 3}
        body = json.loads(envelope("t", "s", payload))
        assert body["sha256"] == findings_digest(payload)


# ── Direct tool tests (planted answers) ──────────────────────────────────────


class TestToolsDirect:
    def test_profile_finds_planted_nulls(self, messy_csv: Path) -> None:
        f = _findings(tools.tool_profile(str(messy_csv), None))
        email = next(c for c in f["columns"] if c["name"] == "email")
        assert email["nulls"] == 2

    def test_profile_accuracy_is_none_with_note(self, messy_csv: Path) -> None:
        f = _findings(tools.tool_profile(str(messy_csv), None))
        assert f["dama_scores"]["accuracy"] is None
        assert "fabrication" in f["accuracy_note"]

    def test_validate_finds_planted_negative(self, messy_csv: Path) -> None:
        f = _findings(tools.tool_validate(
            str(messy_csv), None,
            [{"column": "amount", "rule": "range", "min": 0}],
        ))
        assert f["total_exceptions"] == 1
        assert f["results"][0]["failures"] == 1

    def test_dedupe_finds_planted_exact_dup(self, messy_csv: Path) -> None:
        f = _findings(tools.tool_dedupe(str(messy_csv), None, None))
        assert f["duplicate_rows"] == 1

    def test_dedupe_finds_planted_key_dups(self, messy_csv: Path) -> None:
        f = _findings(tools.tool_dedupe(str(messy_csv), None, "order_id"))
        assert f["duplicate_groups"] == 2  # O-1 and O-6 reused

    def test_reconcile_finds_planted_orphans(
        self, messy_csv: Path, reference_csv: Path
    ) -> None:
        f = _findings(tools.tool_reconcile(
            str(messy_csv), str(reference_csv), "customer_id", "amount"
        ))
        assert f["left_orphans"] == 2   # two C-9 orders
        assert f["right_orphans"] == 1  # C-4 has no orders
        assert f["unreconciled"] == 1200.0  # 600 + 600

    def test_explain_returns_lesson(self) -> None:
        text = tools.tool_explain("accuracy")
        assert "accuracy" in text.lower()

    def test_explain_unknown_topic_clean_error(self) -> None:
        from analystkit import AnalystKitError

        with pytest.raises(AnalystKitError, match="Available topics"):
            tools.tool_explain("astrology")


# ── Protocol tests: the real MCP path ────────────────────────────────────────


class TestProtocol:
    async def test_all_six_tools_registered(self) -> None:
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as session:
            listed = await session.list_tools()
            names = {t.name for t in listed.tools}
            assert names == {
                "analystkit_profile",
                "analystkit_validate",
                "analystkit_dedupe",
                "analystkit_reconcile",
                "analystkit_explain",
                "analystkit_list_lessons",
            }

    async def test_profile_via_protocol(self, messy_csv: Path) -> None:
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as session:
            result = await session.call_tool(
                "analystkit_profile",
                {"params": {"source": str(messy_csv)}},
            )
            assert not result.isError
            text = result.content[0].text  # type: ignore[union-attr]
            f = _findings(text)
            email = next(c for c in f["columns"] if c["name"] == "email")
            assert email["nulls"] == 2

    async def test_validate_via_protocol_with_planted_answer(
        self, messy_csv: Path
    ) -> None:
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as session:
            result = await session.call_tool(
                "analystkit_validate",
                {"params": {
                    "source": str(messy_csv),
                    "rules_json": json.dumps(
                        [{"column": "order_id", "rule": "unique"}]
                    ),
                }},
            )
            text = result.content[0].text  # type: ignore[union-attr]
            f = _findings(text)
            assert f["results"][0]["failures"] == 2  # O-1 + O-6 reused

    async def test_bad_source_returns_clean_error_not_traceback(self) -> None:
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as session:
            result = await session.call_tool(
                "analystkit_profile",
                {"params": {"source": "/tmp/ghost_does_not_exist.csv"}},
            )
            text = result.content[0].text  # type: ignore[union-attr]
            assert text.startswith("Error:")
            assert "Traceback" not in text

    async def test_malformed_rules_json_clean_error(self, messy_csv: Path) -> None:
        async with create_connected_server_and_client_session(
            mcp._mcp_server
        ) as session:
            result = await session.call_tool(
                "analystkit_validate",
                {"params": {"source": str(messy_csv), "rules_json": "{not json"}},
            )
            text = result.content[0].text  # type: ignore[union-attr]
            assert text.startswith("Error:")
            assert "not valid JSON" in text
