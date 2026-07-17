# run_insurance.py
# Real-world test for Indian Health Insurance Claims dataset

import json
from pathlib import Path

from analystkit_mcp.tools import tool_profile
from delivery_engine import approve_plan, load_playbook, make_plan, run

# --- CONFIG (Pointing to your exact file) ---
CSV_PATH = r"C:\Users\mohds\delivery-engine\data\indian_health_insurance_claims_dataset.csv"
PLAYBOOK_NAME = "healthcare_claims_audit"  # Auto-detects and runs stats on ALL numeric columns
# ---------------------------------------------

HERE = Path(__file__).parent
SRC = CSV_PATH
OUT = HERE / "output" / "insurance_audit"

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
        "Analyze health insurance claims to identify cost drivers and fraud patterns", 
        SRC, 
        findings,
        HERE / "playbooks",
        chosen_playbook="healthcare_claims_audit"  # <--- FORCE the planner to use THIS playbook
    ),
    "Senior_Analyst_Manager_Test",
)

pb = load_playbook(HERE / "playbooks" / f"{PLAYBOOK_NAME}.toml")

# --- Validation Rules (Using the exact column names we just discovered) ---
# --- Validation Rules (Healthcare-specific) ---
RULES = [
    {"column": "policy_id", "rule": "not_null"},
    {"column": "age", "rule": "range", "min": 0, "max": 120},
    {"column": "bmi", "rule": "range", "min": 10, "max": 60},
    # total_claim_amount REMOVED because it has commas (VARCHAR)
    # The math stage will handle its analysis automatically
    {"column": "icu_days", "rule": "range", "min": 0},
    {"column": "length_of_stay", "rule": "range", "min": 0},
    {"column": "gender", "rule": "allowed", "values": ["M", "F", "male", "female", "Male", "Female", "Other"]},
]

print(f"⚙️ Executing the pipeline...")
final = run(
    plan, 
    pb, 
    RULES,
    OUT / "final", 
    approvals={"plan_approval": "Senior_Analyst_Manager_Test"}
)

print(f"\n🎉 SUCCESS! Package generated at: {final}")
print(f"📄 Check the manifest: {final / 'manifest.json'}")
print(f"📊 Check the narrative report: {final / 'narrative_report.md'}")
print(f"📈 Math findings: {final / 'findings' / 'math.json'}")