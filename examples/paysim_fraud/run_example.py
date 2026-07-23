"""PaySim fraud model - end to end.

Run from the repository root:
    python examples/paysim_fraud/run_example.py

The data: PaySim synthetic fraud simulation dataset (6,362,620 rows).
Source file: data/fraud_model.csv (493MB - not committed to repo).

CRITICAL: isFlaggedFraud excluded - fires on only 16/6.36M rows.
This runner asserts isFraud is the target before proceeding.

V1.1: baseline findings include G2 (Forstmeier et al 2017) and
G3 MDE (Cohen 1988) disclosures. Both non-gating.
"""
import json
from pathlib import Path

from analystkit_mcp.tools import tool_profile
from delivery_engine import approve_plan, load_playbook, make_plan, run
from delivery_engine.compatibility import build_compatibility_report

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
SRC = str(ROOT / "data" / "fraud_model.csv")
OUT = HERE / "output"

EXCLUDE_COLS = ["isFlaggedFraud"]

RULES = [
    {"column": "row_id", "rule": "unique"},
    {"column": "row_id", "rule": "not_null"},

    {"column": "type", "rule": "not_null"},
    {"column": "isFraud", "rule": "not_null"},
]
APPROVALS = {"plan_approval": "Example Analyst"}

findings = json.loads(tool_profile(SRC, EXCLUDE_COLS))["findings"]

report = build_compatibility_report(findings, ROOT / "playbooks", SRC)
OUT.mkdir(parents=True, exist_ok=True)
(HERE / "compatibility_report.md").write_text(report, encoding="utf-8")
print("compatibility_report.md written")

plan = approve_plan(
    make_plan(
        "churn analysis and binary classification baseline for fraud "
        "detection: predict isFraud using transaction features",
        SRC, findings, ROOT / "playbooks",
    ),
    "Example Analyst",
)

binary_targets = [col for col, kind in plan.column_kinds
                  if kind == "binary_target"]
first_target = binary_targets[0] if binary_targets else None
print(f"Planner binary targets: {binary_targets}")
print(f"Executor will model:    {first_target} (first in column order)")
assert first_target == "isFraud", (
    f"Expected 'isFraud' as first binary_target, got '{first_target}'."
)
print(f"Playbook chosen:        {plan.playbook_name}")
print("Target confirmed. Running...")

pb = load_playbook(ROOT / "playbooks" / "churn_analysis.toml")
final = run(plan, pb, RULES, OUT / "final", approvals=APPROVALS)
print(f"Package complete: {final}")

baseline = json.loads(
    (OUT / "final" / "findings" / "baseline.json").read_text()
)
f = baseline["findings"]
print(f"Baseline roc_auc: {f['metrics']['roc_auc']}")
print(f"Baseline recall:  {f['metrics']['recall']}")
print(f"G2 gate:          {f['g2_pseudoreplication']['gate']}")
print(f"G3 mde:           {f['g3_minimum_detectable_effect']['mde_cohen_h']}")
