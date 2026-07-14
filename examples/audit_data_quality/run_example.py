"""Audit-universe data quality review - end to end.

Run from the repository root:
    python examples/audit_data_quality/run_example.py

Audience: internal audit / audit COO analysts (3rd Line of Defence).
The dataset is an audit-issues register (business line, severity,
status, owner). The engine profiles it, drafts validation rules, waits
for content-bound approval (Human Gate 2 - the reviewer sign-off), then
validates and packages re-performable evidence: an automated workpaper.
The planted DQ issue: owner_team is null on ~8% of rows - watch the
profile find it and the report state it with the exact count.
"""
import json
from pathlib import Path

from analystkit_mcp.tools import tool_profile
from delivery_engine import (
    ExecutionStopped, approve_plan, load_playbook, make_plan, run,
)
from delivery_engine.compatibility import build_compatibility_report

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
SRC = str(HERE / "audit_issues.csv")
OUT = HERE / "output"

findings = json.loads(tool_profile(SRC, None))["findings"]

report = build_compatibility_report(findings, ROOT / "playbooks", SRC)
OUT.mkdir(exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("compatibility_report.md written")

plan = approve_plan(
    make_plan("data quality review of this extract", SRC, findings,
              ROOT / "playbooks"),
    "Example Analyst",
)
pb = load_playbook(ROOT / "playbooks" / "data_quality_review.toml")

try:
    run(plan, pb, [], OUT / "phase1")
except ExecutionStopped as stop:
    print(f"Human Gate 2: {stop.reason[:80]}...")

draft = json.loads((OUT / "phase1" / "rules_draft.json").read_text())
final = run(plan, pb, [], OUT / "final",
            approvals={"rules": {"approver": "Example Analyst",
                                 "sha256": draft["sha256"]}})
print(f"Package complete: {final}")
