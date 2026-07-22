"""scale_test.py - full 13,305,915-row transaction monitoring run.

Run from the repository root:
    python scale_test.py

This proves the engine at real bank-feed scale. Times every stage.
The file has quoted multi-value error fields that need a staging pass
first — same issue that real bank CSV exports have all the time.
"""
import json
import sys
import time
from pathlib import Path

SRC_RAW = Path(r"C:\Users\mohds\scale_test\transactions_data.csv")
SRC_STAGED = Path(r"C:\Users\mohds\scale_test\transactions_staged.csv")
OUT = Path(r"C:\Users\mohds\scale_test\output")
PLAYBOOKS = Path("playbooks")
T0 = time.time()


def elapsed() -> str:
    return f"{time.time() - T0:.1f}s"


print("=" * 60)
print("DELIVERY ENGINE — SCALE TEST")
print(f"Source: {SRC_RAW}")
print("=" * 60)

# ── STAGE 0: normalize the CSV (quoted multi-value error column) ──────────────
import duckdb

if not SRC_STAGED.exists():
    print(f"\n[{elapsed()}] Stage 0: normalising CSV (quoting all fields)...")
    t = time.time()
    con = duckdb.connect()
    con.execute(f"""
        COPY (
            SELECT * FROM read_csv('{SRC_RAW.as_posix()}',
                                   header=true, quote='"',
                                   strict_mode=false)
        )
        TO '{SRC_STAGED.as_posix()}'
        (HEADER, DELIMITER ',', FORCE_QUOTE *)
    """)
    n = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{SRC_STAGED.as_posix()}', header=true)"
    ).fetchone()[0]
    print(f"[{elapsed()}] Stage 0 done: {n:,} rows staged in {time.time()-t:.1f}s")
else:
    print(f"\n[{elapsed()}] Stage 0: staged file exists, skipping normalization")

# ── STAGE 1: AnalystKit profile ───────────────────────────────────────────────
from analystkit_mcp.tools import tool_profile

print(f"\n[{elapsed()}] Stage 1: profiling {SRC_STAGED.name}...")
t = time.time()
findings = json.loads(tool_profile(str(SRC_STAGED), None))["findings"]
cols = findings["columns"]
print(f"[{elapsed()}] Stage 1 done: {cols[0]['total']:,} rows x "
      f"{len(cols)} columns in {time.time()-t:.1f}s")
print()
print(f"  {'Column':16} {'Type':12} {'Nulls':>12} {'Null%':>6} {'Distinct':>12}")
print(f"  {'-'*16} {'-'*12} {'-'*12} {'-'*6} {'-'*12}")
for c in cols:
    pct = c["nulls"] / c["total"] * 100 if c["total"] else 0
    flag = " ◄ notable" if pct > 5 else ""
    print(f"  {c['name']:16} {str(c['dtype']):12} "
          f"{c['nulls']:>12,} {pct:>5.1f}% {c['distinct']:>12,}{flag}")

# ── STAGE 2: Plan + Human Gate 1 ─────────────────────────────────────────────
from delivery_engine import (
    ExecutionStopped, approve_plan, load_playbook, make_plan, run,
)
from delivery_engine.compatibility import build_compatibility_report

print(f"\n[{elapsed()}] Stage 2: compatibility report...")
report = build_compatibility_report(findings, PLAYBOOKS, str(SRC_STAGED))
OUT.mkdir(exist_ok=True)
(OUT / "compatibility_report.md").write_text(report, encoding="utf-8")
qualified = [l.split()[1] for l in report.splitlines()
             if "— QUALIFIES" in l]
print(f"[{elapsed()}] Qualifying playbooks: {qualified}")

print(f"\n[{elapsed()}] Stage 2: planning...")
plan = approve_plan(
    make_plan(
        "transaction monitoring completeness review of this feed",
        str(SRC_STAGED), findings, PLAYBOOKS,
    ),
    "Mohd Saif Hussain",
)
print(f"[{elapsed()}] Plan: {plan.playbook_name} | "
      f"column kinds: {len(plan.column_kinds)}")

# ── STAGE 3: Phase 1 (profile gate + rules draft → Human Gate 2) ─────────────
pb = load_playbook(PLAYBOOKS / "transaction_monitoring_review.toml")
p1 = OUT / "phase1"
if p1.exists():
    import shutil
    shutil.rmtree(p1)

print(f"\n[{elapsed()}] Stage 3: phase 1 "
      f"(re-profile 13M rows + draft validation rules)...")
t = time.time()
try:
    run(plan, pb, [], p1)
except ExecutionStopped:
    pass
print(f"[{elapsed()}] Phase 1 done in {time.time()-t:.1f}s")

draft = json.loads((p1 / "rules_draft.json").read_text())
print(f"  {len(draft['rules'])} rules drafted:")
for r in draft["rules"]:
    print(f"    [{r['rule']:12}] {r['column']}")

# ── STAGE 4: Phase 2 (approve rules, full pipeline) ──────────────────────────
final = OUT / "final"
if final.exists():
    import shutil
    shutil.rmtree(final)

print(f"\n[{elapsed()}] Stage 4: phase 2 "
      f"(validate + dedupe + OpsKit + reports + documents)...")
t = time.time()
result = run(
    plan, pb, [], final,
    approvals={"rules": {
        "approver": "Mohd Saif Hussain",
        "sha256": draft["sha256"],
    }},
)
print(f"[{elapsed()}] Phase 2 done in {time.time()-t:.1f}s")

# ── RESULTS ───────────────────────────────────────────────────────────────────
manifest = json.loads((result / "manifest.json").read_text())
val = json.loads(
    (result / "findings" / "dq_validate.json").read_text()
)["findings"]
ded = json.loads(
    (result / "findings" / "dq_dedupe.json").read_text()
)["findings"]
ops = json.loads(
    (result / "findings" / "ops_review.json").read_text()
)["findings"]

print()
print("=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Rows analysed:       {cols[0]['total']:>15,}")
print(f"Rules evaluated:     {val['rules_evaluated']:>15,}")
print(f"Total exceptions:    {val['total_exceptions']:>15,}")
print(f"Duplicate rows:      {ded.get('exact_duplicate_rows', 'n/a'):>15}")
print(f"OpsKit findings:     {len(ops.get('findings', [])):>15,}")
print(f"Package files:       {len(manifest['files']):>15,}")
print()
print(f"TOTAL WALL TIME:     {elapsed():>15}")
print()
print(f"Output: {result}")
print()
print("Key findings:")
for f in ops.get("findings", []):
    if f.get("severity") in ("CRITICAL", "NOTABLE"):
        print(f"  [{f['severity']:8}] {f.get('text', '')[:80]}")
print()
print("Evidence digests:")
for stage, digest in manifest["findings"].items():
    print(f"  {stage:20} {digest[:32]}...")
