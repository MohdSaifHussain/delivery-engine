"""Universal descriptive audit - end to end.

Run from the repository root:
    python examples/universal_audit/run_example.py

Audience: any analyst who needs to understand the SHAPE of a dataset
before deciding what to do with it. The universal_audit archetype runs
on any table with an id column: it profiles every column, validates,
waits for plan approval (Human Gate), then runs the full deterministic
descriptive suite - distribution shape, outliers, entropy, temporal
structure - and packages re-performable evidence.

The data: a small orders feed (record_id, amount, region, event_date)
- one numeric, one categorical, one temporal column, so the audit
exercises all three branches of the descriptive suite.
"""
import json
from pathlib import Path

from analystkit_mcp.tools import tool_profile
from delivery_engine import (
    approve_plan, load_playbook, make_plan, run,
)
from delivery_engine.compatibility import build_compatibility_report

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
SRC = str(HERE / "orders.csv")
OUT = HERE / "output"

# The universal_audit playbook requires an id column; record_id is unique.
RULES = [{"column": "record_id", "rule": "unique"}]
# A human_gate stage is approved by name (executor lines 265-281):
# approvals maps the gate's stage_id -> approver. Not the hashed
# rules-draft form; universal_audit has no rules_draft stage.
APPROVALS = {"plan_approval": "Example Analyst"}

# 1. Deterministic profile (the first gate's own tool)
findings = json.loads(tool_profile(SRC, None))["findings"]

# 2. Compatibility report - the front door: what can run on this data?
report = build_compatibility_report(findings, ROOT / "playbooks", SRC)
OUT.mkdir(exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("compatibility_report.md written")

# 3. Plan + Human Gate 1 (goal wording selects universal_audit by fit)
plan = approve_plan(
    make_plan(
        "universal descriptive audit: distribution shape outliers "
        "entropy temporal structure",
        SRC, findings, ROOT / "playbooks",
    ),
    "Example Analyst",
)
assert plan.playbook_name == "universal_audit", (
    f"expected universal_audit, planner chose {plan.playbook_name}"
)

# 4. Single run to completion: the plan_approval human gate is satisfied
#    by APPROVALS; the math suite then runs over the approved columns.
pb = load_playbook(ROOT / "playbooks" / "universal_audit.toml")
final = run(plan, pb, RULES, OUT / "final", approvals=APPROVALS)
print(f"Package complete: {final}")
