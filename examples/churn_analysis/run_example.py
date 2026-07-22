"""Telco churn analysis with deterministic baseline model - end to end.

Run from the repository root:
    python examples/churn_analysis/run_example.py

Audience: business / product / data analysts who need a reproducible,
hash-verified churn baseline before any custom modeling begins.

The data: Kaggle Telco Customer Churn dataset (7,043 rows, 21 columns).
Real-world messiness: TotalCharges has 11 blank rows (profiled as
VARCHAR; the engine reports this honestly). Churn rate is ~26.5%.

The model is a deterministic LogisticRegression baseline - fixed seeds,
metrics hashed, leakage sentinel checked. Every number in the package
traces to a SHA-256 verified finding. This is a reference point for
human modeling work, not a delivered model.
"""
import json
from pathlib import Path

from analystkit_mcp.tools import tool_profile
from delivery_engine import approve_plan, load_playbook, make_plan, run
from delivery_engine.compatibility import build_compatibility_report

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
SRC = str(HERE / "WA_Fn-UseC_-Telco-Customer-Churn.csv")
OUT = HERE / "output"

findings = json.loads(tool_profile(SRC, None))["findings"]

report = build_compatibility_report(findings, ROOT / "playbooks", SRC)
OUT.mkdir(exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("compatibility_report.md written")

plan = approve_plan(
    make_plan(
        "churn analysis for the retention team",
        SRC, findings, ROOT / "playbooks",
    ),
    "Example Analyst",
)

# PaySim lesson: verify the planner picked the right target.
# The executor uses the FIRST binary_target in column_kinds order
# (disclosed deterministic rule - see baseline.py line 572).
binary_targets = [col for col, kind in plan.column_kinds
                  if kind == "binary_target"]
first_target = binary_targets[0] if binary_targets else None
print(f"Planner binary targets: {binary_targets}")
print(f"Executor will model:    {first_target} (first in column order)")
assert first_target == "Churn", (
    f"Expected 'Churn' as first binary_target, got '{first_target}'. "
    f"Review the plan before proceeding."
)
assert plan.playbook_name == "churn_analysis", (
    f"Expected churn_analysis playbook, planner chose "
    f"'{plan.playbook_name}'."
)
print("Target and playbook confirmed. Running...")

pb = load_playbook(ROOT / "playbooks" / "churn_analysis.toml")
final = run(
    plan, pb,
    [{"column": "customerID", "rule": "unique"}],
    OUT / "final",
    approvals={"plan_approval": "Example Analyst"},
)
print(f"Package complete: {final}")

baseline = json.loads((final / "findings" / "baseline.json").read_text())
print(f"Baseline roc_auc: {baseline['findings']['metrics']['roc_auc']}")
print(f"Baseline recall:  {baseline['findings']['metrics']['recall']}")
