"""delivery_engine.planner — archetype selection: 80% deterministic, 20% LLM.

Charter 4.6 made executable:

1. DETERMINISTIC CLASSIFICATION - column kinds are decided by rules over
   the AnalystKit profile findings envelope (the exact JSON returned by
   analystkit_mcp). No model involved.
2. DETERMINISTIC REQUIREMENTS CHECK - each playbook's [requirements] are
   evaluated against the classified profile. A failed check disqualifies
   the playbook, and NOTHING can override that - not the LLM, not the
   goal text.
3. DETERMINISTIC GOAL MATCHING - keyword overlap between the goal text
   and each qualified playbook's name/description. A single top scorer
   is selected deterministically.
4. LLM ONLY FOR GENUINE AMBIGUITY - when several qualified playbooks tie,
   the LLM chooses among the candidate names ONLY (a choice outside the
   list is rejected), and the decision plus rationale is logged. With no
   API key the feature is cleanly absent: PlannerAmbiguityError is raised
   listing the candidates for the human to choose.
5. HUMAN GATE 1 - the Plan is born unapproved. approve_plan() returns an
   approved copy with approver and IST timestamp recorded. The executor
   (build step 4) refuses unapproved plans.

Classification thresholds are declared defaults, documented and testable -
reasonable defaults, not universal truths (the AnalystKit timeliness
precedent).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo

from delivery_engine.playbook import Playbook, PlaybookError, load_playbook

__all__ = [
    "ColumnKind",
    "DecisionSource",
    "Plan",
    "PlannerAmbiguityError",
    "PlannerError",
    "approve_plan",
    "check_requirements",
    "classify_columns",
    "make_plan",
    "render_plan",
]

IST: Final[ZoneInfo] = ZoneInfo("Asia/Kolkata")

# ── Declared classification defaults (documented, not hidden) ────────────────

ID_DISTINCT_RATIO: Final[float] = 0.999   # distinct/rows >= this => id-like
CATEGORICAL_MAX_DISTINCT: Final[int] = 20  # VARCHAR with <= this => categorical
NUMERIC_DTYPE_HINTS: Final[tuple[str, ...]] = (
    "INT", "DECIMAL", "FLOAT", "DOUBLE", "HUGEINT", "NUMERIC", "REAL",
)
TIME_DTYPE_HINTS: Final[tuple[str, ...]] = ("TIMESTAMP", "DATE")


class PlannerError(Exception):
    """A planner problem, stated cleanly."""


class PlannerAmbiguityError(PlannerError):
    """Multiple qualified playbooks tie and no resolver is available.

    Carries the candidate names so a human can choose.
    """

    def __init__(self, candidates: tuple[str, ...]) -> None:
        self.candidates = candidates
        super().__init__(
            "Multiple playbooks qualify equally: "
            + ", ".join(candidates)
            + ". Choose one explicitly, or set ANTHROPIC_API_KEY to let "
            "the LLM resolver pick (its choice is logged and limited to "
            "this list)."
        )


class ColumnKind(StrEnum):
    ID_COLUMN = "id_column"
    BINARY_TARGET = "binary_target"
    TIMESTAMP_COLUMN = "timestamp_column"
    NUMERIC_COLUMN = "numeric_column"
    CATEGORICAL_COLUMN = "categorical_column"


class DecisionSource(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class Plan:
    """The planner's output. Born unapproved; the executor refuses it
    until Human Gate 1 (approve_plan) has been passed."""

    playbook_name: str
    playbook_version: str
    playbook_path: str
    goal: str
    source: str
    stage_ids: tuple[str, ...]
    column_kinds: tuple[tuple[str, str], ...]  # (column, kind) pairs
    requirement_results: tuple[tuple[str, bool, str], ...]  # (check, ok, note)
    decision_source: DecisionSource
    decision_rationale: str
    candidates_considered: tuple[str, ...]
    created_at_ist: str
    approved: bool = False
    approved_by: str | None = None
    approved_at_ist: str | None = None

    def plan_digest(self) -> str:
        """SHA-256 over the decision content (not approval state or
        timestamps): the same inputs and decision always hash the same."""
        from analystkit.ai import findings_digest

        payload: dict[str, Any] = {
            "playbook_name": self.playbook_name,
            "playbook_version": self.playbook_version,
            "goal": self.goal,
            "source": self.source,
            "stage_ids": list(self.stage_ids),
            "column_kinds": [list(p) for p in self.column_kinds],
            "requirement_results": [list(r) for r in self.requirement_results],
            "decision_source": self.decision_source.value,
            "candidates_considered": list(self.candidates_considered),
        }
        return findings_digest(payload)


# ── 1. Deterministic column classification ───────────────────────────────────


def classify_columns(profile_findings: dict[str, Any]) -> dict[str, tuple[ColumnKind, ...]]:
    """Classifies each profiled column into zero or more kinds.

    Input: the `findings` dict of an analystkit_profile envelope
    (keys: columns, dama_scores, ...). Pure rules; documented thresholds.
    """
    columns = profile_findings.get("columns")
    if not isinstance(columns, list) or not columns:
        raise PlannerError(
            "Profile findings contain no columns. Run analystkit_profile "
            "on the source first; the planner consumes its findings."
        )

    out: dict[str, tuple[ColumnKind, ...]] = {}
    for i, col in enumerate(columns):
        # Fail closed on malformed profiles: the planner consumes hashed
        # findings envelopes; a column entry that is not a well-formed
        # dict means the input is not a real profile, and classifying
        # garbage silently would poison every downstream decision.
        if not isinstance(col, dict):
            raise PlannerError(
                f"Profile column #{i + 1} is not an object - the planner "
                f"consumes analystkit_profile findings envelopes."
            )
        missing = {"name", "dtype", "total", "nulls", "distinct"} - set(col)
        if missing:
            raise PlannerError(
                f"Profile column #{i + 1} is missing keys {sorted(missing)} "
                f"- not a valid analystkit_profile findings envelope."
            )
        name = str(col["name"])
        dtype = str(col["dtype"]).upper()
        try:
            total = int(col["total"])
            nulls = int(col["nulls"])
            distinct = int(col["distinct"])
        except (TypeError, ValueError):
            raise PlannerError(
                f"Profile column '{col.get('name', f'#{i + 1}')}': total, "
                f"nulls, and distinct must be integers."
            ) from None
        if not (0 <= nulls <= total) or distinct < 0:
            raise PlannerError(
                f"Profile column '{name}' is inconsistent "
                f"(total={total}, nulls={nulls}, distinct={distinct}) - "
                f"refusing to classify a corrupt profile."
            )
        non_null = total - nulls

        kinds: list[ColumnKind] = []
        if total > 0 and distinct / total >= ID_DISTINCT_RATIO:
            kinds.append(ColumnKind.ID_COLUMN)
        if non_null > 0 and distinct == 2:
            kinds.append(ColumnKind.BINARY_TARGET)
        if any(h in dtype for h in TIME_DTYPE_HINTS):
            kinds.append(ColumnKind.TIMESTAMP_COLUMN)
        if any(h in dtype for h in NUMERIC_DTYPE_HINTS):
            kinds.append(ColumnKind.NUMERIC_COLUMN)
        if (
            "VARCHAR" in dtype
            and 0 < distinct <= CATEGORICAL_MAX_DISTINCT
        ):
            kinds.append(ColumnKind.CATEGORICAL_COLUMN)
        out[name] = tuple(kinds)
    return out


# ── 2. Deterministic requirements check ──────────────────────────────────────


def check_requirements(
    playbook: Playbook,
    profile_findings: dict[str, Any],
    source: str,
) -> tuple[tuple[str, bool, str], ...]:
    """Evaluates a playbook's requirements. Returns (check, ok, note) rows.

    Nothing overrides a failed row - not goal wording, not the LLM.
    """
    kinds_by_column = classify_columns(profile_findings)
    present_kinds = {k.value for kinds in kinds_by_column.values() for k in kinds}

    columns = profile_findings["columns"]
    total_rows = int(columns[0]["total"]) if columns else 0

    results: list[tuple[str, bool, str]] = []

    ok = total_rows >= playbook.requirements.min_rows
    results.append((
        f"min_rows >= {playbook.requirements.min_rows}",
        ok,
        f"source has {total_rows:,} rows",
    ))

    for kind in playbook.requirements.required_kinds:
        ok = kind in present_kinds
        holders = [
            name for name, ks in kinds_by_column.items()
            if any(k.value == kind for k in ks)
        ]
        note = f"found in: {', '.join(holders)}" if holders else "no column qualifies"
        results.append((f"required kind '{kind}'", ok, note))

    stype = _source_type(source)
    ok = stype in playbook.requirements.source_types
    results.append((
        f"source type '{stype}' accepted",
        ok,
        f"playbook accepts: {', '.join(playbook.requirements.source_types)}",
    ))
    return tuple(results)


def _source_type(source: str) -> str:
    s = source.lower()
    if s.startswith(("postgres://", "postgresql://")):
        return "postgres"
    if s.startswith("mysql://"):
        return "mysql"
    if s.endswith((".xlsx", ".xls")):
        return "excel"
    if s.endswith((".sqlite", ".db", ".sqlite3")):
        return "sqlite"
    return "csv"


# ── 3. Deterministic goal matching ───────────────────────────────────────────


def _tokens(text: str) -> frozenset[str]:
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in text)
    return frozenset(t for t in cleaned.split() if len(t) > 2)


def _goal_score(goal: str, playbook: Playbook) -> int:
    goal_tokens = _tokens(goal)
    pb_tokens = _tokens(playbook.name.replace("_", " ")) | _tokens(playbook.description)
    return len(goal_tokens & pb_tokens)


# ── 4. LLM ambiguity resolution (bounded, logged, cleanly absent) ────────────


def _llm_resolve(goal: str, candidates: tuple[str, ...]) -> tuple[str, str]:
    """Asks the LLM to choose among candidate names ONLY.

    Returns (chosen_name, rationale). Official Anthropic SDK usage:
    key from ANTHROPIC_API_KEY, messages.create, text blocks.
    A choice outside the candidate list is rejected - the resolver can
    pick, never invent.
    """
    from anthropic import Anthropic

    client = Anthropic()
    prompt = (
        "A user stated this project goal:\n"
        f"  {goal}\n\n"
        "These playbooks all qualify on deterministic requirements:\n"
        + "\n".join(f"  - {c}" for c in candidates)
        + "\n\nRespond with EXACTLY two lines:\n"
        "CHOICE: <one name from the list, verbatim>\n"
        "REASON: <one sentence>"
    )
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(
        block.text for block in message.content
        if getattr(block, "type", "") == "text"
    )
    choice, reason = "", ""
    for line in text.splitlines():
        if line.startswith("CHOICE:"):
            choice = line.removeprefix("CHOICE:").strip()
        elif line.startswith("REASON:"):
            reason = line.removeprefix("REASON:").strip()
    if choice not in candidates:
        raise PlannerError(
            f"LLM resolver chose '{choice}', which is not in the candidate "
            f"list {list(candidates)}. The resolver may pick, never invent. "
            f"Falling back to human choice is required."
        )
    return choice, reason or "no rationale given"


# ── The planner ──────────────────────────────────────────────────────────────


def make_plan(
    goal: str,
    source: str,
    profile_findings: dict[str, Any],
    playbook_dir: Path,
    chosen_playbook: str | None = None,
) -> Plan:
    """Selects a playbook and produces an unapproved Plan.

    chosen_playbook: a human's explicit choice (DecisionSource.HUMAN);
    it still must pass requirements - human choice does not override a
    failed deterministic check any more than the LLM does.
    """
    if not goal.strip():
        raise PlannerError("Goal must not be empty. State what to deliver.")
    paths = sorted(playbook_dir.glob("*.toml"))
    if not paths:
        raise PlannerError(f"No playbooks found in {playbook_dir}.")

    loaded: list[Playbook] = []
    for p in paths:
        try:
            loaded.append(load_playbook(p))
        except PlaybookError as exc:
            raise PlannerError(
                f"Playbook library contains an invalid playbook: {exc}"
            ) from None

    # Requirements: deterministic, non-overridable
    qualified: list[tuple[Playbook, tuple[tuple[str, bool, str], ...]]] = []
    failures: dict[str, list[str]] = {}
    for pb in loaded:
        results = check_requirements(pb, profile_findings, source)
        if all(ok for _, ok, _ in results):
            qualified.append((pb, results))
        else:
            failures[pb.name] = [
                f"{check} - {note}" for check, ok, note in results if not ok
            ]

    if chosen_playbook is not None:
        match = next((q for q in qualified if q[0].name == chosen_playbook), None)
        if match is None:
            reason = failures.get(chosen_playbook)
            if reason:
                raise PlannerError(
                    f"'{chosen_playbook}' fails deterministic requirements: "
                    + "; ".join(reason)
                    + ". Human choice does not override a failed check."
                )
            raise PlannerError(
                f"'{chosen_playbook}' is not in the library. Available: "
                + ", ".join(pb.name for pb in loaded)
            )
        pb, results = match
        return _build_plan(
            pb, results, goal, source, profile_findings,
            DecisionSource.HUMAN, "explicitly chosen by the user",
            tuple(q[0].name for q in qualified),
        )

    if not qualified:
        detail = "; ".join(
            f"{name}: {', '.join(reasons)}" for name, reasons in failures.items()
        )
        raise PlannerError(
            f"No playbook qualifies for this source. {detail}"
        )

    if len(qualified) == 1:
        pb, results = qualified[0]
        return _build_plan(
            pb, results, goal, source, profile_findings,
            DecisionSource.DETERMINISTIC,
            "only playbook whose requirements the source satisfies",
            (pb.name,),
        )

    # Several qualify: deterministic goal scoring
    scored = sorted(
        ((_goal_score(goal, pb), pb, results) for pb, results in qualified),
        key=lambda t: (-t[0], t[1].name),
    )
    top_score = scored[0][0]
    top = [t for t in scored if t[0] == top_score]

    if len(top) == 1 and top_score > 0:
        _, pb, results = top[0]
        return _build_plan(
            pb, results, goal, source, profile_findings,
            DecisionSource.DETERMINISTIC,
            f"highest goal-keyword overlap (score {top_score}) among "
            f"{len(qualified)} qualified playbooks",
            tuple(q[0].name for q in qualified),
        )

    # Genuine ambiguity: LLM if available, else raise for the human
    candidates = tuple(t[1].name for t in top)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise PlannerAmbiguityError(candidates)
    choice, rationale = _llm_resolve(goal, candidates)
    pb, results = next(q for q in qualified if q[0].name == choice)
    return _build_plan(
        pb, results, goal, source, profile_findings,
        DecisionSource.LLM,
        f"LLM resolver chose among tied candidates {list(candidates)}: {rationale}",
        tuple(q[0].name for q in qualified),
    )


def _build_plan(
    pb: Playbook,
    results: tuple[tuple[str, bool, str], ...],
    goal: str,
    source: str,
    profile_findings: dict[str, Any],
    decision_source: DecisionSource,
    rationale: str,
    candidates: tuple[str, ...],
) -> Plan:
    kinds = classify_columns(profile_findings)
    pairs = tuple(
        (name, k.value)
        for name, ks in sorted(kinds.items())
        for k in ks
    )
    return Plan(
        playbook_name=pb.name,
        playbook_version=pb.version,
        playbook_path=str(pb.source_path),
        goal=goal,
        source=source,
        stage_ids=pb.stage_ids(),
        column_kinds=pairs,
        requirement_results=results,
        decision_source=decision_source,
        decision_rationale=rationale,
        candidates_considered=candidates,
        created_at_ist=datetime.now(IST).isoformat(timespec="seconds"),
    )


# ── 5. Human Gate 1 ──────────────────────────────────────────────────────────


def approve_plan(plan: Plan, approver: str) -> Plan:
    """Human Gate 1. Returns an approved copy; the original stays unapproved.

    The executor (build step 4) refuses plans where approved is False.
    """
    if not approver.strip():
        raise PlannerError("Approver name must not be empty - approval is recorded.")
    if plan.approved:
        raise PlannerError("Plan is already approved.")
    return replace(
        plan,
        approved=True,
        approved_by=approver.strip(),
        approved_at_ist=datetime.now(IST).isoformat(timespec="seconds"),
    )


def render_plan(plan: Plan) -> str:
    """Human-readable plan for the approval decision - what will run and why."""
    lines = [
        "EXECUTION PLAN (Human Gate 1 - approval required before anything runs)",
        f"  Playbook : {plan.playbook_name} v{plan.playbook_version}",
        f"  Goal     : {plan.goal}",
        f"  Source   : {plan.source}",
        f"  Decided  : {plan.decision_source.value} - {plan.decision_rationale}",
        f"  Considered: {', '.join(plan.candidates_considered)}",
        f"  Plan hash: {plan.plan_digest()[:16]}...",
        "",
        "  Requirements:",
    ]
    for check, ok, note in plan.requirement_results:
        lines.append(f"    [{'PASS' if ok else 'FAIL'}] {check} ({note})")
    lines.append("")
    lines.append("  Stages, in order:")
    for sid in plan.stage_ids:
        lines.append(f"    -> {sid}")
    lines.append("")
    lines.append(
        f"  Status: {'APPROVED by ' + str(plan.approved_by) if plan.approved else 'NOT APPROVED - execution blocked'}"
    )
    return "\n".join(lines)


def plan_to_json(plan: Plan) -> str:
    """Canonical JSON of the plan for the audit log."""
    body: dict[str, Any] = {
        "playbook_name": plan.playbook_name,
        "playbook_version": plan.playbook_version,
        "playbook_path": plan.playbook_path,
        "goal": plan.goal,
        "source": plan.source,
        "stage_ids": list(plan.stage_ids),
        "column_kinds": [list(p) for p in plan.column_kinds],
        "requirement_results": [list(r) for r in plan.requirement_results],
        "decision_source": plan.decision_source.value,
        "decision_rationale": plan.decision_rationale,
        "candidates_considered": list(plan.candidates_considered),
        "created_at_ist": plan.created_at_ist,
        "approved": plan.approved,
        "approved_by": plan.approved_by,
        "approved_at_ist": plan.approved_at_ist,
        "plan_sha256": plan.plan_digest(),
    }
    return json.dumps(body, indent=2, sort_keys=True)
