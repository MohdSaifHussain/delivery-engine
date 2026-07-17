# run_fraud.py
# Financial Fraud Detection Analysis for Synchrony-style dataset

import json
from pathlib import Path

from analystkit_mcp.tools import tool_profile
from delivery_engine import approve_plan, load_playbook, make_plan, run

# --- CONFIG ---
CSV_PATH = r"C:\Users\mohds\delivery-engine\data\synthetic_transactions.csv"
PLAYBOOK_NAME = "churn_analysis"
# ---------------------------------------------

HERE = Path(__file__).parent
SRC = CSV_PATH
OUT = HERE / "output" / "fraud_audit"

print(f"🔍 Profiling: {SRC}...")
findings = json.loads(tool_profile(SRC, None))["findings"]

print(f"📋 Checking compatibility...")
from delivery_engine.compatibility import build_compatibility_report

report = build_compatibility_report(findings, HERE / "playbooks", SRC)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("✅ Compatibility report written.")

print(f"🧠 Planning the run...")
plan = approve_plan(
    make_plan(
        "Analyze transaction data to detect fraud patterns and identify cost drivers",
        SRC,
        findings,
        HERE / "playbooks",
        chosen_playbook="churn_analysis",
    ),
    "Synchrony_Senior_Analyst_Fraud_Test",
)

pb = load_playbook(HERE / "playbooks" / f"{PLAYBOOK_NAME}.toml")

# --- Validation Rules (Clean, no duplicates) ---
RULES = [
    {"column": "transaction_id", "rule": "not_null"},
    {"column": "amount", "rule": "range", "min": 0},
    {"column": "is_fraud", "rule": "allowed", "values": [0, 1]},
    {"column": "is_online", "rule": "allowed", "values": ["False", "True"]},
    {"column": "is_recurring", "rule": "allowed", "values": ["False", "True"]},
    {"column": "is_international", "rule": "allowed", "values": ["False", "True"]},
    {"column": "currency", "rule": "allowed", "values": ["INR", "USD", "GBP"]},
    {
        "column": "merchant_category",
        "rule": "allowed",
        "values": [
            "hotel", "entertainment", "transport_rail", "grocery",
            "rideshare", "online_shopping", "fuel", "subscription",
            "pharmacy", "telecom", "retail_discount", "retail_clothing",
            "jewellery", "coffee", "restaurant"
        ],
    },
    {
        "column": "fraud_type",
        "rule": "allowed",
        "values": [
            "none", "bust_out", "account_takeover", "card_testing",
            "cnp_fraud", "geo_impossible"
        ],
    },
]

print(f"⚙️ Executing the pipeline...")
final = run(
    plan,
    pb,
    RULES,
    OUT / "final",
    approvals={"plan_approval": "Synchrony_Senior_Analyst_Fraud_Test"},
    max_exception_rate=4.0  # Override to see the full report
)

print(f"\n🎉 SUCCESS! Package generated at: {final}")
print(f"📄 Check the manifest: {final / 'manifest.json'}")
print(f"📊 Check the narrative report: {final / 'narrative_report.md'}")
print(f"📈 Baseline model findings: {final / 'findings' / 'baseline.json'}")