"""Step 13 tests - deterministic multi-format deliverables.

The property under test: every NUMBER on every page of every format is
injected from the hashed Findings Store, and the verification stage
proves it — a hard gate on store-sourced numbers, a soft check on prose.
No AI authors any figure.

Planted answers: the churn fixture's known findings (row count, null
counts, rule count, baseline metrics) must all appear in the detail
formats; the verification must FAIL when a number is removed.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine import approve_plan, load_playbook, make_plan, run
from delivery_engine.documents import (
    DocumentError,
    build_documents,
    verify_document_numbers,
)
from delivery_engine.playbook import PlaybookError

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"


def _churn_csv(path: Path, rows: int = 400) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "churned", "tenure_months",
                    "plan_type", "monthly_spend"])
        for i in range(rows):
            tenure = (i * 7) % 60 + 1
            churned = "yes" if tenure < 12 else "no"
            w.writerow([f"C-{i:05d}", churned, tenure,
                        ["basic", "plus", "pro"][i % 3],
                        f"{200.0 + (i % 50) * 3.5:.2f}"])
    return path


def _snapshot(src: Path) -> dict[str, Any]:
    envelope = json.loads(tool_profile(str(src), None))
    findings = envelope["findings"]
    return {
        "dq_profile": findings,
        "dq_validate": {"rules_evaluated": 12, "total_exceptions": 0,
                        "results": []},
        "_digests": {"dq_profile": "a" * 64, "dq_validate": "b" * 64},
    }


# ── Builders produce valid, verifiable files ─────────────────────────────────


class TestBuilders:
    @pytest.mark.parametrize("fmt", ["docx", "xlsx", "pptx", "pdf"])
    def test_format_builds_and_verifies(
        self, fmt: str, tmp_path: Path
    ) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        snap = _snapshot(src)
        out = tmp_path / "out"
        out.mkdir()
        try:
            results = build_documents([fmt], snap, str(src), "churn review", out)
        except DocumentError as exc:
            if "LibreOffice" in str(exc):
                pytest.skip(f"{fmt} requires LibreOffice — not installed")
            raise
        produced = out / results[fmt]["file"]
        assert produced.exists()
        assert produced.stat().st_size > 2000
        verdict = verify_document_numbers(produced, fmt, snap)
        assert verdict["ok"], f"{fmt} missing: {verdict['missing_numbers']}"

    def test_row_count_present_in_all_formats(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        snap = _snapshot(src)
        out = tmp_path / "out"
        out.mkdir()
        successful: list[str] = []
        for fmt in ("docx", "xlsx", "pptx", "pdf"):
            try:
                build_documents([fmt], snap, str(src), "churn review", out)
                successful.append(fmt)
            except DocumentError as exc:
                if "LibreOffice" in str(exc):
                    continue
                raise
        from delivery_engine.documents import _extract_text

        for fmt in successful:
            text = _extract_text(out / f"delivery_package.{fmt}", fmt)
            joined = text.replace(",", "")
            assert "400" in joined, f"row count 400 absent in {fmt}"

    def test_markdown_is_skipped(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        snap = _snapshot(src)
        out = tmp_path / "out"
        out.mkdir()
        results = build_documents(["markdown", "xlsx"], snap, str(src),
                                  "review", out)
        assert "markdown" not in results
        assert "xlsx" in results

    def test_unknown_format_refused(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        snap = _snapshot(src)
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(DocumentError, match="Unknown output format"):
            build_documents(["holograph"], snap, str(src), "review", out)


# ── Verification is a real gate ──────────────────────────────────────────────


class TestVerification:
    def test_missing_number_fails_verification(self, tmp_path: Path) -> None:
        """The core guarantee: if a document omits a store-sourced number,
        verification catches it. Simulated by verifying a real doc against
        a snapshot containing a number the doc cannot possibly hold."""
        src = _churn_csv(tmp_path / "churn.csv")
        snap = _snapshot(src)
        out = tmp_path / "out"
        out.mkdir()
        build_documents(["xlsx"], snap, str(src), "review", out)
        # Inject a fake finding number that the document was never built with
        tampered = dict(snap)
        tampered["dq_validate"] = {"rules_evaluated": 999999,
                                   "total_exceptions": 0, "results": []}
        verdict = verify_document_numbers(
            out / "delivery_package.xlsx", "xlsx", tampered
        )
        assert not verdict["ok"]
        assert "999999" in verdict["missing_numbers"]

    def test_pptx_summary_scope(self, tmp_path: Path) -> None:
        """A deck is not expected to carry every per-column null count —
        the format-aware hard gate checks summary numbers for pptx."""
        src = _churn_csv(tmp_path / "churn.csv")
        snap = _snapshot(src)
        out = tmp_path / "out"
        out.mkdir()
        build_documents(["pptx"], snap, str(src), "review", out)
        verdict = verify_document_numbers(
            out / "delivery_package.pptx", "pptx", snap
        )
        assert verdict["ok"]


# ── Schema V13 ───────────────────────────────────────────────────────────────


class TestV13Schema:
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

    def _write(self, tmp_path: Path, deliverables: str) -> Path:
        p = tmp_path / "pb.toml"
        p.write_text(self.HEAD + deliverables, encoding="utf-8")
        return p

    def test_default_is_markdown(self, tmp_path: Path) -> None:
        pb = load_playbook(self._write(tmp_path, """
[deliverables]
artifacts = ["audit_log", "manifest"]
"""))
        assert pb.output_formats == ("markdown",)

    def test_explicit_formats_parsed(self, tmp_path: Path) -> None:
        pb = load_playbook(self._write(tmp_path, """
[deliverables]
artifacts = ["audit_log", "manifest"]
formats = ["markdown", "docx", "xlsx"]
"""))
        assert set(pb.output_formats) == {"markdown", "docx", "xlsx"}

    def test_unknown_format_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match=r"\(V13\)"):
            load_playbook(self._write(tmp_path, """
[deliverables]
artifacts = ["audit_log", "manifest"]
formats = ["docx", "papyrus"]
"""))

    def test_empty_formats_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match=r"\(V13\)"):
            load_playbook(self._write(tmp_path, """
[deliverables]
artifacts = ["audit_log", "manifest"]
formats = []
"""))

    def test_existing_playbooks_still_markdown(self) -> None:
        for name in ("churn_analysis", "data_quality_review",
                     "transaction_monitoring_review", "ops_review"):
            pb = load_playbook(PLAYBOOKS / f"{name}.toml")
            assert "markdown" in pb.output_formats


# ── End to end: a formats-enabled playbook run ───────────────────────────────


class TestEndToEnd:
    def test_data_quality_review_with_formats(self, tmp_path: Path) -> None:
        """A real run of a formats-enabled playbook: documents are built,
        verified, hashed into the manifest, and the audit records each."""
        # Build a formats-enabled variant of data_quality_review
        base = (PLAYBOOKS / "data_quality_review.toml").read_text()
        variant = base.replace(
            'artifacts = [', 'formats = ["markdown", "xlsx"]\nartifacts = ['
        )
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "dq_formats.toml").write_text(
            variant.replace('name = "data_quality_review"',
                            'name = "dq_formats"'),
            encoding="utf-8",
        )

        src = _churn_csv(tmp_path / "data.csv")
        envelope = json.loads(tool_profile(str(src), None))
        plan = make_plan("data quality review of this extract", str(src),
                         envelope["findings"], lib)
        plan = approve_plan(plan, "Saif")
        pb = load_playbook(lib / "dq_formats.toml")

        # data_quality_review has a rules_draft stage (Human Gate 2):
        # phase 1 stops at the gate, phase 2 approves the draft by hash.
        from delivery_engine import ExecutionStopped

        with pytest.raises(ExecutionStopped):
            run(plan, pb, [], tmp_path / "p1")
        digest = json.loads(
            (tmp_path / "p1" / "rules_draft.json").read_text()
        )["sha256"]
        out = run(
            plan, pb, [], tmp_path / "out",
            approvals={"rules": {"approver": "Saif", "sha256": digest}},
        )

        xlsx = out / "delivery_package.xlsx"
        assert xlsx.exists()

        manifest = json.loads((out / "manifest.json").read_text())
        assert "delivery_package.xlsx" in manifest["files"]

        entries = [
            json.loads(line) for line in
            (out / "audit_log.jsonl").read_text().strip().splitlines()
        ]
        doc_entry = next(
            e for e in entries
            if e["stage"] == "documents" and e["action"] == "document:xlsx"
        )
        assert doc_entry["outcome"] == "verified"
        assert "store-sourced number" in doc_entry["rationale"]
