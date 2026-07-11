"""delivery_engine.rules_draft - deterministic rule drafting for Human Gate 2.

The rules_draft slot is the single highest-risk point in the architecture
(charter 4.4): content authored inside the engine feeds the deterministic
validation layer. Three controls apply, by construction:

1. DETERMINISTIC DRAFTING - v0.2 drafts only what profile findings can
   justify: not_null for fully-complete columns, unique for id-ratio
   columns, not_future for timestamp columns. Every rule carries its
   written rationale. No LLM in the drafting path - a draft must hash
   the same on every run so the content-bound approval can work.
   (allowed/range drafting needs value-level findings the profile
   envelope does not carry - documented as deferred, not faked.)

2. CONTENT-BOUND APPROVAL - the draft is written to rules_draft.json
   with its SHA-256. Human Gate 2 approval must quote that hash: the
   human approves THIS draft, not "the rules stage". A hash mismatch
   means a different draft and is refused.

3. VALIDATED BEFORE USE - drafted rules pass the same shape checks a
   user's rules would. The gate does not launder invalid rules into
   the deterministic layer.
"""
from __future__ import annotations

from typing import Any, Final

from analystkit.ai import findings_digest

__all__ = ["DraftedRule", "draft_digest", "draft_rules"]

ID_DISTINCT_RATIO: Final[float] = 0.999
TIME_DTYPE_HINTS: Final[tuple[str, ...]] = ("TIMESTAMP", "DATE")


DraftedRule = dict[str, Any]


def draft_rules(
    profile_findings: dict[str, Any],
) -> tuple[list[DraftedRule], list[str]]:
    """Drafts validation rules a profile can justify, with rationales.

    Returns (rules, rationales) - parallel lists, one rationale per rule.
    Pure function of the findings: same profile, same draft, same hash.
    """
    columns = profile_findings.get("columns")
    if not isinstance(columns, list) or not columns:
        return [], []

    rules: list[DraftedRule] = []
    rationales: list[str] = []

    for col in columns:
        name = str(col["name"])
        dtype = str(col["dtype"]).upper()
        total = int(col["total"])
        nulls = int(col["nulls"])
        distinct = int(col["distinct"])

        if total > 0 and nulls == 0:
            rules.append({"column": name, "rule": "not_null"})
            rationales.append(
                f"'{name}' has zero nulls across {total:,} rows - the "
                f"profile suggests completeness is an expectation, so "
                f"future nulls should be exceptions."
            )
        if total > 0 and distinct / total >= ID_DISTINCT_RATIO:
            rules.append({"column": name, "rule": "unique"})
            rationales.append(
                f"'{name}' is distinct on {distinct:,} of {total:,} rows "
                f"(ratio >= {ID_DISTINCT_RATIO}) - it behaves as an "
                f"identifier, so duplicates should be exceptions."
            )
        if any(h in dtype for h in TIME_DTYPE_HINTS):
            rules.append({"column": name, "rule": "not_future"})
            rationales.append(
                f"'{name}' is a {dtype} column - future-dated records "
                f"are a validity finding in most operational data."
            )

    return rules, rationales


def draft_digest(rules: list[DraftedRule]) -> str:
    """The SHA-256 of the draft - the object of Human Gate 2 approval.

    Same algorithm as everything else in the ecosystem
    (analystkit.ai.findings_digest): canonical JSON, sort_keys.
    """
    return findings_digest({"rules": rules})
