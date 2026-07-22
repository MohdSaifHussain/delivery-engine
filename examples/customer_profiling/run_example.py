"""Customer profiling - descriptive audit, end to end.

Run from the repository root:
    python examples/customer_profiling/run_example.py

Audience: any analyst who needs to understand the shape of a customer
base before segmenting, modeling, or reporting on it. The
universal_audit archetype profiles every column, validates, waits for
plan approval at a human gate, then runs a deterministic descriptive
suite - distribution shape, outliers, entropy - over the approved
columns.

The data: a small customer table - customer_id, churned, tenure_months,
plan_type, monthly_spend. Two numeric columns (tenure, spend), one
categorical (plan_type), so the audit exercises the numeric and
categorical branches. No timestamp column, so the temporal branch does
not fire - the audit reports on what is present.
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
SRC = str(HERE / "customers.csv")
OUT = HERE / "output"

RULES = [{"column": "customer_id", "rule": "unique"}]
APPROVALS = {"plan_approval": "Example Analyst"}

findings = json.loads(tool_profile(SRC, None))["findings"]

report = build_compatibility_report(findings, ROOT / "playbooks", SRC)
OUT.mkdir(exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("compatibility_report.md written")

plan = approve_plan(
    make_plan(
        "descriptive profile of the customer base: distribution shape "
        "of spend and tenure, plan mix, outliers",
        SRC, findings, ROOT / "playbooks",
    ),
    "Example Analyst",
)
assert plan.playbook_name == "universal_audit", (
    f"expected universal_audit, planner chose {plan.playbook_name}"
)

pb = load_playbook(ROOT / "playbooks" / "universal_audit.toml")
final = run(plan, pb, RULES, OUT / "final", approvals=APPROVALS)
print(f"Package complete: {final}")
