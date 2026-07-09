"""analystkit_mcp.tools — tool implementations. Pure logic, zero MCP wiring.

The separation follows the official SDK's recommended layout (server.py
wiring + tool modules) and the AnalystKit charter principle: dispatch
layers contain no logic, so every function here is independently
importable and testable without the protocol in the way.

All tools are READ-ONLY. This server exposes analysis, never mutation:
- no workpaper tool in v0.1 (it writes files — deferred by design)
- no dedupe --out (same reason)
- database sources inherit AnalystKit's READ_ONLY-by-construction attach

Every tool returns the canonical findings envelope (findings.envelope):
canonical JSON + SHA-256 of the findings payload.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from analystkit import (
    AnalystKitError,
    Dimension,
    dimension_scores,
    find_duplicates,
    profile_columns,
    reconcile_sources,
    run_rules,
)
from analystkit.cli import open_source
from analystkit.teach import LESSONS

from analystkit_mcp.findings import envelope

__all__ = [
    "tool_dedupe",
    "tool_explain",
    "tool_list_lessons",
    "tool_profile",
    "tool_reconcile",
    "tool_validate",
]


def tool_profile(source: str, table: str | None) -> str:
    """DAMA six-dimension profile. Accuracy is never scored — by design."""
    con = open_source(source, table)
    profiles = profile_columns(con)
    scores = dimension_scores(con, profiles)
    payload: dict[str, Any] = {
        "columns": [
            {
                "name": p.name,
                "dtype": p.dtype,
                "total": p.total,
                "nulls": p.nulls,
                "completeness": p.completeness,
                "distinct": p.distinct,
                "case_variants": p.case_variants,
                "valid_ratio": p.valid_ratio,
            }
            for p in profiles
        ],
        "dama_scores": {
            dim.value.lower(): scores[dim] for dim in Dimension
        },
        "accuracy_note": (
            "Accuracy is never scored from the dataset alone — that would "
            "be fabrication. Use analystkit_reconcile against an "
            "authoritative source."
        ),
    }
    return envelope("analystkit_profile", source, payload)


def tool_validate(source: str, table: str | None, rules: list[dict[str, Any]]) -> str:
    """Runs declarative validation rules. Exceptions are reported, never dropped."""
    con = open_source(source, table)
    results = run_rules(con, rules)
    payload: dict[str, Any] = {
        "rules_evaluated": len(results),
        "total_exceptions": sum(r.failures for r in results),
        "results": [
            {
                "rule_id": r.rule_id,
                "column": r.column,
                "rule": r.rule,
                "detail": r.detail,
                "failures": r.failures,
                "sample": list(r.sample),
            }
            for r in results
        ],
    }
    return envelope("analystkit_validate", source, payload)


def tool_dedupe(source: str, table: str | None, key: str | None) -> str:
    """Duplicate detection: exact-row (key=None) or key-based."""
    con = open_source(source, table)
    dup_rows, groups = find_duplicates(con, key=key)
    payload: dict[str, Any] = {
        "mode": "key" if key else "exact_row",
        "key": key,
        "duplicate_rows": dup_rows,
        "duplicate_groups": len(groups),
        "sample_groups": [
            {
                "value": " | ".join(str(v) for v in g[:-1]),
                "copies": int(g[-1]),
            }
            for g in groups[:10]
        ],
    }
    return envelope("analystkit_dedupe", source, payload)


def tool_reconcile(left: str, right: str, key: str, total_col: str | None) -> str:
    """The tie-out: row counts, key matching, control totals.

    Orphans are findings, never garbage — the completeness principle.
    """
    r = reconcile_sources(Path(left), Path(right), key, total_col)
    payload: dict[str, Any] = {
        "key": key,
        "left_rows": r.left_rows,
        "right_rows": r.right_rows,
        "matched_keys": r.matched_keys,
        "left_orphans": r.left_orphans,
        "right_orphans": r.right_orphans,
        "left_total": r.left_total,
        "matched_total": r.matched_total,
        "unreconciled": (
            round(r.left_total - r.matched_total, 2)
            if r.left_total is not None and r.matched_total is not None
            else None
        ),
        "orphan_note": (
            "Orphan keys are records outside the reconciled population. "
            "They must be investigated and reported, never silently excluded."
        ),
    }
    return envelope("analystkit_reconcile", f"{left} vs {right}", payload)


def tool_explain(topic: str) -> str:
    """Built-in lesson on a DAMA dimension or concept. Plain text, no envelope
    — lessons are teaching content, not findings."""
    key = topic.strip().lower()
    if key not in LESSONS:
        available = ", ".join(sorted(LESSONS))
        raise AnalystKitError(
            f"No lesson for '{topic}'. Available topics: {available}"
        )
    return LESSONS[key]


def tool_list_lessons() -> str:
    """Lists available lesson topics."""
    return "Available lessons: " + ", ".join(sorted(LESSONS))
