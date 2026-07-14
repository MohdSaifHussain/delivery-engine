"""Step 14 tests - the Playbook Compatibility Report.

Planted answers: a churn-shaped dataset must show churn_analysis (and
the DQ/TM archetypes) as QUALIFIES with the exact planted row count in
the report; a tiny dataset must show DOES NOT QUALIFY with the min_rows
FAIL row naming the real number. The report must be a pure function
(byte-identical across calls) and must agree with the planner by
construction.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine.compatibility import (
    CompatibilityError,
    build_compatibility_report,
)

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"


def _churn_csv(path: Path, rows: int = 400) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "churned", "tenure_months",
                    "plan_type", "monthly_spend"])
        for i in range(rows):
            tenure = (i * 7) % 60 + 1
            w.writerow([f"C-{i:05d}", "yes" if tenure < 12 else "no",
                        tenure, ["basic", "plus", "pro"][i % 3],
                        f"{200.0 + (i % 50) * 3.5:.2f}"])
    return path


def _findings(src: Path) -> dict:  # type: ignore[type-arg]
    return json.loads(tool_profile(str(src), None))["findings"]


class TestCompatibilityReport:
    def test_qualifying_dataset_reported(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        report = build_compatibility_report(_findings(src), PLAYBOOKS,
                                            str(src))
        assert "# Playbook Compatibility Report" in report
        assert "**Rows:** 400" in report                    # planted
        assert "## churn_analysis" in report
        assert "churn_analysis v" in report
        # churn data qualifies for churn_analysis
        assert "— QUALIFIES" in report
        # every library playbook is evaluated
        for name in ("churn_analysis", "data_quality_review",
                     "transaction_monitoring_review", "ops_review"):
            assert f"## {name}" in report

    def test_failing_dataset_names_the_reason(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "tiny.csv", rows=5)
        report = build_compatibility_report(_findings(src), PLAYBOOKS,
                                            str(src))
        assert "DOES NOT QUALIFY" in report
        assert "source has 5 rows" in report                # planted
        assert "FAIL" in report

    def test_report_is_pure_function(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        f = _findings(src)
        a = build_compatibility_report(f, PLAYBOOKS, str(src))
        b = build_compatibility_report(f, PLAYBOOKS, str(src))
        assert a == b

    def test_report_agrees_with_planner(self, tmp_path: Path) -> None:
        """The report and the planner share the same check functions -
        a dataset the report marks QUALIFIES must plan successfully."""
        from delivery_engine import approve_plan, make_plan

        src = _churn_csv(tmp_path / "churn.csv")
        f = _findings(src)
        report = build_compatibility_report(f, PLAYBOOKS, str(src))
        assert "## churn_analysis" in report
        assert "— QUALIFIES" in report
        plan = make_plan("churn analysis for the retention team",
                         str(src), f, PLAYBOOKS)
        assert plan.playbook_name == "churn_analysis"
        approve_plan(plan, "Saif")   # no raise = agreement

    def test_column_kinds_section(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        report = build_compatibility_report(_findings(src), PLAYBOOKS,
                                            str(src))
        assert "## What the planner sees" in report
        assert "| churned | " in report
        assert "binary_target" in report

    def test_empty_library_refused(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        empty = tmp_path / "empty_lib"
        empty.mkdir()
        with pytest.raises(CompatibilityError, match="No playbooks found"):
            build_compatibility_report(_findings(src), empty, str(src))

    def test_formats_listed_per_playbook(self, tmp_path: Path) -> None:
        src = _churn_csv(tmp_path / "churn.csv")
        report = build_compatibility_report(_findings(src), PLAYBOOKS,
                                            str(src))
        assert "Deliverable formats: markdown" in report
