"""Churn analysis with deterministic baseline model - end to end.

Run from the repository root:
    python examples/churn_analysis/run_example.py

Audience: business / product / data analysts.
Produces: EDA notebook, narrative report with baseline-model section,
README, 7-slide deck - every number injected from the hashed store.
The planted signal: churned = yes iff tenure < 12, so the baseline's
roc_auc lands near 1.0 - and you can verify that from the findings.
"""
import json
from pathlib import Path

from analystkit_mcp.tools import tool_profile
from delivery_engine import approve_plan, load_playbook, make_plan, run
from delivery_engine.compatibility import build_compatibility_report

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
SRC = str(HERE / "customers.csv")
OUT = HERE / "output"

findings = json.loads(tool_profile(SRC, None))["findings"]

report = build_compatibility_report(findings, ROOT / "playbooks", SRC)
OUT.mkdir(exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("compatibility_report.md written")

plan = approve_plan(
    make_plan("churn analysis for the retention team", SRC, findings,
              ROOT / "playbooks"),
    "Example Analyst",
)
pb = load_playbook(ROOT / "playbooks" / "churn_analysis.toml")

# churn_analysis takes user-provided rules (no drafting stage) and an
# explicit plan approval at the plan_approval human gate.
final = run(plan, pb, [{"column": "customer_id", "rule": "unique"}],
            OUT / "final", approvals={"plan_approval": "Example Analyst"})
print(f"Package complete: {final}")
baseline = json.loads((final / "findings" / "baseline.json").read_text())
print(f"Baseline roc_auc: {baseline['findings']['metrics']['roc_auc']}")
