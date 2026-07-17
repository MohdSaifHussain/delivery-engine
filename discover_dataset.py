# discover_dataset.py
# Universal Pre-Flight Checklist for ANY dataset.
# Run: python discover_dataset.py path/to/your/data.csv

import json
import sys
from pathlib import Path

import duckdb
from analystkit_mcp.tools import tool_profile
from delivery_engine.compatibility import build_compatibility_report
from delivery_engine.planner import classify_columns


def print_header(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def main(csv_path: str):
    path = Path(csv_path)
    if not path.exists():
        print(f"❌ File not found: {csv_path}")
        return

    print_header("DISCOVERY: " + path.name)
    print(f"📂 Source: {path}")

    # --- 1. Show first 5 rows (Visual Check) ---
    print_header("1. SAMPLE ROWS (First 5)")
    con = duckdb.connect()
    try:
        sample = con.execute(
            f"SELECT * FROM read_csv('{path}', header=True, auto_detect=True) LIMIT 5"
        ).fetchdf()
        print(sample.to_string())
    except Exception as e:
        print(f"⚠️ Could not read sample: {e}")

    # --- 2. Run the Profile (The engine does the heavy lifting) ---
    print_header("2. PROFILING SUMMARY")
    findings = json.loads(tool_profile(str(path), None))["findings"]
    columns = findings.get("columns", [])

    # --- 3. Show detailed column stats + unique values for categoricals ---
    print_header("3. COLUMN ANALYSIS & DETECTED VALUES")

    # Get actual unique values for low-cardinality columns using DuckDB
    unique_values_map = {}
    con = duckdb.connect()
    for col in columns:
        name = col["name"]
        distinct = col["distinct"]
        # If it has low distinct count (<= 15), fetch the actual values
        if 0 < distinct <= 15:
            try:
                # Fetch distinct values as a list
                result = con.execute(
                    f"SELECT DISTINCT \"{name}\" FROM read_csv('{path}', header=True, auto_detect=True) WHERE \"{name}\" IS NOT NULL"
                ).fetchall()
                values = [str(r[0]) for r in result if r[0] is not None]
                unique_values_map[name] = values
            except Exception:
                pass

    for col in columns:
        name = col["name"]
        dtype = col["dtype"]
        nulls = col["nulls"]
        total = col["total"]
        distinct = col["distinct"]

        null_pct = (nulls / total) * 100 if total > 0 else 0
        print(f"\n📊 {name}")
        print(f"   - Type: {dtype}")
        print(f"   - Nulls: {nulls:,} ({null_pct:.2f}%)")
        print(f"   - Distinct: {distinct:,}")

        # If we fetched unique values, print them!
        if name in unique_values_map:
            vals = unique_values_map[name]
            display_vals = vals[:10]
            if len(vals) > 10:
                display_vals.append(f"... ({len(vals)} total)")
            print(f"   - 💡 Detected Values: {', '.join(display_vals)}")

    # --- 4. Run the Compatibility Report (Which playbooks fit?) ---
    print_header("4. COMPATIBILITY REPORT (Qualifying Playbooks)")
    try:
        report = build_compatibility_report(
            findings, Path.cwd() / "playbooks", str(path)
        )
        # Parse the report to extract the "Verdict" section cleanly
        lines = report.splitlines()
        in_verdict = False
        for line in lines:
            if "QUALIFIES" in line:
                print("✅ " + line.strip())
            if "Verdict" in line:
                in_verdict = True
            if in_verdict and line.strip():
                print(line.strip())
    except Exception as e:
        print(f"⚠️ Could not run compatibility report: {e}")

    # --- 5. Recommendations ---
    print_header("5. RECOMMENDATION")
    # Check for binary_target columns to recommend churn_analysis
    kinds = classify_columns(findings)
    has_binary = any("binary_target" in [k.value for k in ks] for ks in kinds.values())
    has_id = any("id_column" in [k.value for k in ks] for ks in kinds.values())

    print("\nBased on the profile, the engine suggests:")
    if has_binary and has_id:
        print("   🔹 Recommended Playbook: **churn_analysis** (because binary_target + id_column detected)")
    elif has_id:
        print("   🔹 Recommended Playbook: **universal_audit** (has ID column, explore shape & outliers)")
    else:
        print("   🔹 Recommended Playbook: **data_quality_review** (general profiling)")

    # --- 6. Next Steps (Exact CMD commands) ---
    print_header("NEXT STEPS")
    print(f"✅ Discovery complete.")
    print(f"\n📝 Copy the 'Detected Values' above into your RULES list to avoid mismatches.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python discover_dataset.py path/to/your/file.csv")
    else:
        main(sys.argv[1])