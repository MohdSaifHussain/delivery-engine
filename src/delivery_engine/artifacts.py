"""delivery_engine.artifacts - the bounded AI slots.

Every builder here follows the same law (charter 4.1): prose and
structure are template-driven; EVERY number passes through the
NumberInjector, which records what it emitted so the artifact can be
verified. Artifacts contain NO timestamps - timestamps live in the audit
log - so the same findings produce byte-identical artifacts on any day
(charter 4.8 re-performability, proven by test).

Notebook format: emitted directly against the official Jupyter nbformat
v4 JSON schema (nbformat.readthedocs.io): top level requires exactly
metadata, nbformat, nbformat_minor, cells; markdown cells carry
cell_type/metadata/source; code cells add execution_count and outputs;
cell ids are required from nbformat 4.5.

Optional LLM prose: when ANTHROPIC_API_KEY is present a narrative
paragraph can be generated FROM THE FINDINGS JSON ONLY (reusing
analystkit.ai - the proven pattern), returned labeled with the findings
hash. Absent a key, the deterministic template stands alone: the
artifact is complete either way (clean absence).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from delivery_engine.store import FindingsStore, NumberInjector

__all__ = ["build_eda_notebook", "build_narrative_report", "build_readme"]


def _md_cell(source: str) -> dict[str, Any]:
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, source[:64]).hex[:8],
        "cell_type": "markdown",
        "metadata": {},
        "source": source,
    }


def _code_cell(source: str) -> dict[str, Any]:
    return {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, "code:" + source[:64]).hex[:8],
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


def _profile_summary_lines(
    profile: dict[str, Any], inj: NumberInjector
) -> list[str]:
    lines: list[str] = []
    for col in profile["columns"]:
        lines.append(
            f"- **{col['name']}** ({col['dtype']}): "
            f"{inj.inject(col['total'], '{:,}')} rows, "
            f"{inj.inject(col['nulls'], '{:,}')} nulls, "
            f"{inj.inject(col['distinct'], '{:,}')} distinct, "
            f"validity {inj.inject_percent(col.get('valid_ratio'))}"
        )
    return lines


def build_eda_notebook(
    store: FindingsStore, inj: NumberInjector, source: str
) -> str:
    """The EDA notebook: findings rendered, next steps scaffolded.

    Returns the .ipynb JSON string. Structure per the official nbformat
    v4 schema. The reader gets: what the deterministic engine found
    (numbers injected and hash-referenced), and runnable scaffolding to
    continue the exploration themselves.
    """
    profile = store.get("dq_profile")
    validate = store.get("dq_validate")

    dama = profile["dama_scores"]
    score_lines = [
        f"| {dim} | {inj.inject_percent(val) if val is not None else 'not scored'} |"
        for dim, val in sorted(dama.items())
    ]

    rule_lines = [
        f"| `{r['rule_id']}` | {r['column']} | {r['rule']} | "
        f"{inj.inject(r['failures'], '{:,}')} |"
        for r in validate["results"]
    ]

    cells = [
        _md_cell(
            "# Exploratory Data Analysis\n\n"
            f"Source: `{source}`\n\n"
            "Every figure in this notebook was computed by the "
            "deterministic engine and injected from the hashed Findings "
            "Store. The AI wrote structure and prose only.\n\n"
            f"- dq_profile findings hash: `{store.digest('dq_profile')}`\n"
            f"- dq_validate findings hash: `{store.digest('dq_validate')}`"
        ),
        _md_cell(
            "## Data quality scorecard (DAMA six dimensions)\n\n"
            "| Dimension | Score |\n|---|---|\n" + "\n".join(score_lines)
            + "\n\nAccuracy is never scored from the dataset alone - "
            "that requires reconciliation against an authoritative source."
        ),
        _md_cell(
            "## Column profile\n\n" + "\n".join(_profile_summary_lines(profile, inj))
        ),
        _md_cell(
            "## Validation findings\n\n"
            "| Rule | Column | Check | Exceptions |\n|---|---|---|---|\n"
            + "\n".join(rule_lines)
            + "\n\nExceptions are reported, never dropped - every failure "
            "is evidence, not garbage."
        ),
        _md_cell(
            "## Continue the exploration\n\n"
            "The cells below are scaffolding for the human analyst - "
            "the judgment layer the engine deliberately does not automate."
        ),
        _code_cell(
            "import pandas as pd\n\n"
            f"df = pd.read_csv({json.dumps(source)})\n"
            "df.head()"
        ),
        _code_cell(
            "# Segment the binary target against each categorical column\n"
            "# and challenge the engine's findings with your own eyes.\n"
            "df.describe(include='all')"
        ),
    ]

    notebook = {
        "metadata": {
            "language_info": {"name": "python"},
            "delivery_engine": {
                "numbers_from": "findings_store",
                "findings_hashes": store.digests(),
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
        "cells": cells,
    }
    return json.dumps(notebook, indent=1, sort_keys=True)


def build_narrative_report(
    store: FindingsStore, inj: NumberInjector, source: str, goal: str
) -> str:
    """The findings report, markdown. Deterministic template + injected
    numbers. Optional LLM paragraph is appended LABELED when available."""
    profile = store.get("dq_profile")
    validate = store.get("dq_validate")
    total_rows = profile["columns"][0]["total"] if profile["columns"] else 0

    lines = [
        "# Findings Report",
        "",
        f"**Goal:** {goal}",
        f"**Source:** `{source}`",
        "",
        "Every number below was computed deterministically and injected "
        "from the hashed Findings Store.",
        "",
        "## What was tested",
        "",
        f"The source contains {inj.inject(total_rows, '{:,}')} rows across "
        f"{inj.inject(len(profile['columns']))} columns. "
        f"{inj.inject(validate['rules_evaluated'])} validation rules were "
        "evaluated against declared expectations.",
        "",
        "## What was found",
        "",
        f"Total exceptions: {inj.inject(validate['total_exceptions'], '{:,}')}.",
        "",
    ]
    for r in validate["results"]:
        if r["failures"]:
            lines.append(
                f"- **`{r['rule_id']}`** ({r['column']}, {r['rule']}): "
                f"{inj.inject(r['failures'], '{:,}')} exception(s). "
                f"Sample: {', '.join('`' + str(s) + '`' for s in r['sample'][:2])}"
            )
    lines += [
        "",
        "## Evidence trail",
        "",
        f"- dq_profile findings: `{store.digest('dq_profile')}`",
        f"- dq_validate findings: `{store.digest('dq_validate')}`",
        "",
        "Re-run the same commands on the same source: matching hashes "
        "prove the findings; a mismatch proves the data changed.",
    ]

    llm_paragraph = _optional_llm_narrative(validate)
    if llm_paragraph is not None:
        narrative, digest = llm_paragraph
        lines += [
            "",
            "---",
            "",
            "**AI-GENERATED NARRATIVE** - verify against the findings "
            f"above (input sha256: `{digest[:16]}...`). The AI saw only "
            "the findings JSON; it ran no queries and computed no numbers.",
            "",
            narrative,
        ]
    return "\n".join(lines) + "\n"


def _optional_llm_narrative(
    findings: dict[str, Any],
) -> tuple[str, str] | None:
    """Clean absence: no key or no SDK, no narrative, no degradation."""
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        from analystkit.ai import narrate_findings

        return narrate_findings(findings)
    except Exception:
        return None


def build_readme(
    store: FindingsStore, inj: NumberInjector, source: str, goal: str,
    artifacts: tuple[str, ...],
) -> str:
    """The package README: what this is, how to verify it."""
    validate = store.get("dq_validate")
    lines = [
        "# Delivery Package",
        "",
        f"**Goal:** {goal}",
        f"**Source:** `{source}`",
        "",
        "Produced by the Delivery Engine: agent proposes, deterministic "
        "tools dispose, human governs, every claim traceable.",
        "",
        "## Contents",
        "",
    ]
    for a in artifacts:
        lines.append(f"- `{a}`")
    lines += [
        "",
        "## Headline finding",
        "",
        f"{inj.inject(validate['rules_evaluated'])} rules evaluated, "
        f"{inj.inject(validate['total_exceptions'], '{:,}')} total "
        "exceptions - reported, never dropped.",
        "",
        "## How to verify this package",
        "",
        "Open `manifest.json`. Recompute the SHA-256 of any file and "
        "compare. Matching hashes = unaltered evidence. `audit_log.jsonl` "
        "records every stage, decision, rationale, and timestamp (IST). "
        "Findings JSONs under `findings/` carry their own digests - "
        "re-run the same tools on the same source to re-perform any stage.",
    ]
    return "\n".join(lines) + "\n"
