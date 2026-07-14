"""Transaction monitoring feed review - end to end.

Run from the repository root:
    python examples/transaction_monitoring/run_example.py

Audience: compliance / AML / transaction-monitoring analysts.
Produces: full multi-format delivery package (markdown, docx, pptx,
xlsx, pdf*) plus the Playbook Compatibility Report.
*pdf requires LibreOffice; the engine says so clearly if absent.
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
SRC = str(HERE / "transactions_sample.csv")
OUT = HERE / "output"

# 1. Deterministic profile (the first gate's own tool)
findings = json.loads(tool_profile(SRC, None))["findings"]

# 2. Compatibility report - the front door: what can run on this data?
report = build_compatibility_report(findings, ROOT / "playbooks", SRC)
OUT.mkdir(exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("compatibility_report.md written")

# 3. Plan + Human Gate 1
plan = approve_plan(
    make_plan("transaction monitoring completeness review of this feed",
              SRC, findings, ROOT / "playbooks"),
    "Example Analyst",
)
pb = load_playbook(ROOT / "playbooks" / "transaction_monitoring_review.toml")

# 4. Phase 1 stops at Human Gate 2 (engine-drafted rules await approval)
try:
    run(plan, pb, [], OUT / "phase1")
except ExecutionStopped as stop:
    print(f"Human Gate 2: {stop.reason[:80]}...")

draft = json.loads((OUT / "phase1" / "rules_draft.json").read_text())
print(f"Reviewing {len(draft['rules'])} engine-drafted rules...")

# 5. Phase 2: approve the EXACT draft by hash, run to completion
final = run(plan, pb, [], OUT / "final",
            approvals={"rules": {"approver": "Example Analyst",
                                 "sha256": draft["sha256"]}})
print(f"Package complete: {final}")
