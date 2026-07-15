# run_supplychain.py
# Delivery Engine runner for Supply Chain dataset

import json
from pathlib import Path

from analystkit_mcp.tools import tool_profile
from delivery_engine import approve_plan, load_playbook, make_plan, run

# --- CONFIG ---
CSV_PATH = r"C:\Users\mohds\delivery-engine\data\DataCoSupplyChainDataset_utf8.csv"
PLAYBOOK_NAME = "supplychain_audit"
# ---------------

HERE = Path(__file__).parent
SRC = CSV_PATH
OUT = HERE / "output" / "supplychain_audit"

print(f"🔍 Profiling: {SRC}...")
findings = json.loads(tool_profile(SRC, None))["findings"]

print(f"📋 Checking compatibility with {PLAYBOOK_NAME}...")
from delivery_engine.compatibility import build_compatibility_report
report = build_compatibility_report(findings, HERE / "playbooks", SRC)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
print("✅ Compatibility report written.")

print(f"🧠 Planning the run...")
plan = approve_plan(
    make_plan(
        "Run a rigorous data quality audit of supply chain orders", 
        SRC, 
        findings,
        HERE / "playbooks"
    ),
    "RegTech_Auditor_Mohd",
)

pb = load_playbook(HERE / "playbooks" / f"{PLAYBOOK_NAME}.toml")

# --- Validation Rules (Using correct column names) ---
RULES = [
    {"column": "Order Id", "rule": "not_null"},
    {"column": "Sales", "rule": "range", "min": -5000, "max": 5000},
    {"column": "Order Profit Per Order", "rule": "range", "min": -10000, "max": 50000},
    # FIXED: Added the real values from the report
    {"column": "Order Status", "rule": "allowed", "values": ["COMPLETE", "PENDING", "PENDING_PAYMENT", "CLOSED", "ON HOLD", "CANCELLED", "CANCELED", "SUSPECTED FRAUD", "PROCESSING"]},
    # FIXED: Added the real shipping statuses
    {"column": "Delivery Status", "rule": "allowed", "values": ["Advance shipping", "Late delivery", "Shipping on time", "Shipping canceled"]},
]

print(f"⚙️ Executing the pipeline...")
final = run(
    plan, 
    pb, 
    RULES,
    OUT / "final", 
    approvals={"plan_approval": "RegTech_Auditor_Mohd"}
)

print(f"\n🎉 SUCCESS! Package generated at: {final}")
print(f"📄 Check the manifest: {final / 'manifest.json'}")
print(f"📊 Check the narrative report: {final / 'narrative_report.md'}")