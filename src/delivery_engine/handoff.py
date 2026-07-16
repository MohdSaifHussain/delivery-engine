"""delivery_engine.handoff - the multi-team handoff manifest (step 16).

A delivery package moves through hands: analyst -> data engineering ->
QA -> compliance -> manager. Each team re-checks specific things, and
today those checks live in heads and chat threads. This module writes
them down: `handoff_manifest.json`, a structured receipt generated at
package time, with each team's checks PRE-POPULATED from the hashed
findings and a `signature` field left null for the human to fill.

Constitutional posture:

- Every number in a check is read from the Findings Store - the same
  hashed findings the artifacts inject from. The handoff manifest
  introduces no new computation and no second source of truth.
- Checks are generated from what the pipeline ACTUALLY ran (which
  stages exist in the store), not from a static template pretending
  every pipeline is the same.
- Signatures start null and stay null: the engine never signs for a
  human. A signed handoff is a human act; the engine only prepares the
  paper.
- The file is written BEFORE manifest.json, so the package manifest
  hashes it like every other file: a tampered handoff fails
  verification.
- No timestamps inside the file (the step-9 rule: timestamps live
  outside hashed content; the audit log records when).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from delivery_engine.planner import Plan
from delivery_engine.playbook import Playbook
from delivery_engine.store import FindingsStore

__all__ = ["build_handoff", "write_handoff"]


def _dq_checks(store: FindingsStore, plan: Plan) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    digests = store.digests()
    if "dq_profile" in digests:
        prof = store.get("dq_profile")
        cols = prof.get("columns", [])
        totals = {c.get("total") for c in cols if "total" in c}
        if len(totals) == 1:
            row_count = totals.pop()
            checks.append({
                "check": (
                    f"Verify the loaded row count matches {row_count} "
                    f"(source: {plan.source})."
                ),
                "evidence": {"stage": "dq_profile",
                             "sha256": digests["dq_profile"]},
            })
        # If per-column totals disagree or are absent, no row-count
        # check is written: the engine never fabricates a check around
        # a number it does not have (step-16 hunt, H1).
        id_cols = [c for c, k in plan.column_kinds if k == "id_column"]
        if id_cols:
            checks.append({
                "check": (
                    f"Confirm uniqueness/null status of id column(s) "
                    f"{id_cols} before loading to staging."
                ),
                "evidence": {"stage": "dq_profile",
                             "sha256": digests["dq_profile"]},
            })
    return checks


def _qa_checks(store: FindingsStore) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    digests = store.digests()
    if "dq_validate" in digests:
        val = store.get("dq_validate")
        checks.append({
            "check": (
                "Re-perform the validation rules against the source and "
                "confirm the recorded exception counts match the findings "
                "exactly (rules and results are in the hashed findings)."
            ),
            "evidence": {"stage": "dq_validate",
                         "sha256": digests["dq_validate"],
                         "summary_keys": sorted(val.keys())[:12]},
        })
    if "dq_dedupe" in digests:
        checks.append({
            "check": "Confirm duplicate analysis was reviewed before load.",
            "evidence": {"stage": "dq_dedupe",
                         "sha256": digests["dq_dedupe"]},
        })
    return checks


def _compliance_checks(store: FindingsStore,
                       playbook: Playbook) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    digests = store.digests()
    if "stats" in digests:
        s = store.get("stats")
        n_sig = sum(1 for t in s.get("tests", [])
                    if t.get("significant_at_alpha"))
        checks.append({
            "check": (
                f"Review the {len(s.get('tests', []))} statistical "
                f"test(s) ({n_sig} significant at the pre-registered "
                f"alpha {s.get('alpha')}); confirm alpha was approved at "
                f"Human Gate 1 and effect sizes were considered, not "
                f"p-values alone."
            ),
            "evidence": {"stage": "stats", "sha256": digests["stats"]},
        })
    if "ops_review" in digests:
        checks.append({
            "check": (
                "Review flagged operational findings (drivers, "
                "concentrations) against policy thresholds."
            ),
            "evidence": {"stage": "ops_review",
                         "sha256": digests["ops_review"]},
        })
    checks.append({
        "check": (
            "Verify manifest.json against the package files - matching "
            "hashes certify unaltered evidence; then verify the audit "
            "log tells the full story of every gate."
        ),
        "evidence": {"files": ["manifest.json", "audit_log.jsonl"]},
    })
    return checks


def _manager_checks(playbook: Playbook) -> list[dict[str, Any]]:
    return [{
        "check": (
            "Read narrative_report.md; every figure in it is injected "
            "from hashed findings. Approve the narrative and add "
            "business context before forwarding - the engine supplies "
            "evidence, the judgment is yours."
        ),
        "evidence": {"files": sorted(playbook.artifacts)},
    }]


def build_handoff(
    plan: Plan,
    playbook: Playbook,
    store: FindingsStore,
) -> dict[str, Any]:
    """Assembles the handoff manifest content. Deterministic: reads the
    plan, the playbook, and the sealed findings - computes nothing."""
    return {
        "pipeline": {
            "playbook": f"{playbook.name} v{playbook.version}",
            "goal": plan.goal,
            "source": plan.source,
            "plan_sha256": plan.plan_digest(),
            "approved_by": plan.approved_by,
        },
        "team_handoff": {
            "data_engineering": {
                "checks": _dq_checks(store, plan),
                "signature": None,
            },
            "qa_quality_control": {
                "checks": _qa_checks(store),
                "signature": None,
            },
            "compliance": {
                "checks": _compliance_checks(store, playbook),
                "signature": None,
            },
            "manager": {
                "checks": _manager_checks(playbook),
                "signature": None,
            },
        },
        "note": (
            "Each team verifies its checks against the referenced hashed "
            "findings, then fills its signature (e.g. 'name, date'). "
            "Signatures start null: the engine never signs for a human. "
            "This file is hashed in manifest.json - alter it and package "
            "verification fails."
        ),
    }


def write_handoff(
    out_dir: Path,
    plan: Plan,
    playbook: Playbook,
    store: FindingsStore,
) -> Path:
    """Writes handoff_manifest.json into the package (call BEFORE
    write_manifest so the package manifest hashes it)."""
    path = out_dir / "handoff_manifest.json"
    path.write_text(
        json.dumps(build_handoff(plan, playbook, store),
                   indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
