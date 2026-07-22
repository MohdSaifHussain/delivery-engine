"""Segment comparison - statistical significance, end to end.

Run from the repository root:
    python examples/segment_comparison/run_example.py

Audience: growth / product analysts who need to know whether a
difference between segments is real or noise. The segment_comparison
archetype gates on data quality, then runs a deterministic inference
suite: Wilson confidence intervals per segment, Fisher/chi-square
independence test, Mann-Whitney U on numeric columns - all
Benjamini-Hochberg FDR corrected. Significance never gates; the
evidence is reported and the human decides.

The data: signup_conversion.csv - customer_id, converted (yes/no),
channel (organic vs paid), days_active. The core question: does
conversion rate differ by acquisition channel, and is that difference
statistically supported?
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
SRC = str(HERE / "signup_conversion.csv")
OUT = HERE / "output"

# segment_comparison requires id_column + binary_target.
# customer_id is the unique id; converted is the binary target.
RULES = [{"column": "customer_id", "rule": "unique"}]
# plan_approval human_gate: approved by name (not the hashed rules form).
APPROVALS = {"plan_approval": "Example Analyst"}

# 1. Deterministic profile
findings = json.loads(tool_profile(SRC, None))["findings"]

# 2. Compatibility report
report = build_compatibility_report(findings, ROOT / "playbooks", SRC)
OUT.mkdir(exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("compatibility_report.md written")

# 3. Plan + Human Gate 1
plan = approve_plan(
    make_plan(
        "segment comparison with statistical significance: "
        "does conversion rate differ by acquisition channel?",
        SRC, findings, ROOT / "playbooks",
    ),
    "Example Analyst",
)
assert plan.playbook_name == "segment_comparison", (
    f"expected segment_comparison, planner chose {plan.playbook_name}"
)

# 4. Single run to completion
pb = load_playbook(ROOT / "playbooks" / "segment_comparison.toml")
final = run(plan, pb, RULES, OUT / "final", approvals=APPROVALS)
print(f"Package complete: {final}")
