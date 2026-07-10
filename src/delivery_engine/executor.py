"""delivery_engine.executor - the stage-contract loop.

Charter 4.7, every stage, no exceptions:
  1. declared inputs (from the playbook)
  2. execution (kit command or bounded AI slot)
  3. output hashed
  4. gate evaluated (pass / stop / human)
  5. audit entry written
  6. next stage

Enforcement, by construction:
  - an unapproved plan is refused (Human Gate 1, charter 4.4)
  - a plan that does not match the loaded playbook is refused (drift check)
  - a failed must_pass gate STOPS the pipeline; nothing overrides it
    (charter 4.2); advisory gates record and continue
  - a human_gate stage without a recorded approval STOPS the pipeline
  - AI slots receive only the FindingsStore and the NumberInjector -
    there is no code path from an AI slot to the raw data

Gate semantics for v0.1 (declared defaults, documented, testable):
  - any kit tool error fails its gate
  - dq profile fails must_pass when the source has zero rows
  - validate fails must_pass when the exception rate exceeds
    MAX_EXCEPTION_RATE (default 0.10) - exceptions are evidence, but a
    source where more than 10% of rows violate declared rules is not fit
    for downstream analysis until investigated
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from delivery_engine.artifacts import (
    build_eda_notebook,
    build_narrative_report,
    build_readme,
)
from delivery_engine.audit import AuditLog, write_manifest
from delivery_engine.planner import Plan
from delivery_engine.playbook import AiSlot, GateMode, Playbook, Stage, StageKind
from delivery_engine.store import (
    FindingsStore,
    NumberInjector,
    verify_artifact_numbers,
)

__all__ = ["MAX_EXCEPTION_RATE", "ExecutionStopped", "ExecutorError", "run"]

MAX_EXCEPTION_RATE: Final[float] = 0.10

ARTIFACT_FILENAMES: Final[dict[AiSlot, str]] = {
    AiSlot.EDA_NOTEBOOK: "eda_notebook.ipynb",
    AiSlot.NARRATIVE_REPORT: "narrative_report.md",
    AiSlot.README: "README.md",
}


class ExecutorError(Exception):
    """A setup or contract problem - the run never started properly."""


class ExecutionStopped(Exception):  # noqa: N818 - a control outcome, not a defect
    """A gate stopped the pipeline. This is the system WORKING."""

    def __init__(self, stage_id: str, reason: str) -> None:
        self.stage_id = stage_id
        self.reason = reason
        super().__init__(f"Pipeline stopped at stage '{stage_id}': {reason}")


def run(
    plan: Plan,
    playbook: Playbook,
    rules: list[dict[str, Any]],
    out_dir: Path,
    approvals: dict[str, str] | None = None,
    max_exception_rate: float = MAX_EXCEPTION_RATE,
) -> Path:
    """Executes an approved plan against its playbook. Returns out_dir.

    approvals: {stage_id: approver_name} for human_gate stages. A
    human_gate without an entry stops the pipeline - gates cannot be
    bypassed by omission.
    """
    audit = AuditLog()
    approvals = approvals or {}

    # ── Pre-flight: Human Gate 1, approvals mapping, clean out_dir ──
    if not plan.approved:
        raise ExecutorError(
            "Plan is not approved. Human Gate 1 (approve_plan) must pass "
            "before execution. (Charter 4.4)"
        )
    if not plan.approved_by or not plan.approved_at_ist:
        raise ExecutorError(
            "Plan approval metadata is incomplete (approver or timestamp "
            "missing). An approval that cannot say who and when is not an "
            "approval. Re-approve via approve_plan. (Charter 4.4)"
        )
    valid_gates = {
        s.stage_id for s in playbook.stages if s.kind is StageKind.HUMAN_GATE
    }
    stray = set(approvals) - valid_gates
    if stray:
        raise ExecutorError(
            f"Approvals given for nonexistent gate(s) {sorted(stray)}. "
            f"Valid human gates in this playbook: {sorted(valid_gates)}. "
            f"Refusing - approvals must map exactly to gates."
        )
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ExecutorError(
            f"Output directory {out_dir} is not empty. The manifest hashes "
            f"every file in the package; stale files from a previous run "
            f"would be certified as this run's evidence. Use a fresh "
            f"directory."
        )
    if plan.playbook_name != playbook.name or plan.playbook_version != playbook.version:
        raise ExecutorError(
            f"Plan/playbook mismatch: plan is for {plan.playbook_name} "
            f"v{plan.playbook_version}, loaded playbook is {playbook.name} "
            f"v{playbook.version}. Refusing to run a drifted plan."
        )
    if plan.stage_ids != playbook.stage_ids():
        raise ExecutorError(
            "Plan stage list does not match the playbook. The playbook "
            "changed after the plan was approved - re-plan and re-approve."
        )
    has_validate = any(s.tool == "analystkit_validate" for s in playbook.stages)
    if has_validate and not rules:
        raise ExecutorError(
            "This playbook includes analystkit_validate but no rules were "
            "provided. Declare expectations before running."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "findings").mkdir(exist_ok=True)

    store = FindingsStore()
    injector = NumberInjector(store)
    ctx: dict[str, Any] = {
        "plan_column_kinds": tuple(plan.column_kinds),
    }  # run context: facts stages learn + integrity anchors from the plan

    audit.record(
        "plan", "human_gate_1", "approved",
        f"approved by {plan.approved_by} at {plan.approved_at_ist}; "
        f"decision was {plan.decision_source.value}: {plan.decision_rationale}",
        sha256=plan.plan_digest(),
    )
    from delivery_engine.planner import plan_to_json

    (out_dir / "plan.json").write_text(plan_to_json(plan), encoding="utf-8")

    # ── The stage loop: the contract, every stage, no exceptions ──
    for stage in playbook.stages:
        if stage.kind is StageKind.KIT:
            _run_kit_stage(
                stage, plan, rules, store, audit, out_dir,
                max_exception_rate, ctx,
            )
        elif stage.kind is StageKind.HUMAN_GATE:
            approver = approvals.get(stage.stage_id)
            if not approver:
                audit.record(
                    stage.stage_id, "human_gate", "stopped",
                    "no approval recorded for this gate - gates cannot be "
                    "bypassed by omission",
                )
                audit.write(out_dir / "audit_log.jsonl")
                raise ExecutionStopped(
                    stage.stage_id,
                    "human gate has no recorded approval. Approve "
                    "explicitly to continue. (Charter 4.4)",
                )
            audit.record(
                stage.stage_id, "human_gate", "approved",
                f"approved by {approver}",
            )
        elif stage.kind is StageKind.AI:
            _run_ai_stage(stage, plan, store, injector, audit, out_dir, playbook)
        elif stage.kind is StageKind.PACKAGE:
            audit.record(
                stage.stage_id, "package", "sealed",
                "audit log sealed; the manifest is written next and hashes "
                "every file in the package including this log - nothing is "
                "written after the manifest",
            )
            audit.write(out_dir / "audit_log.jsonl")
            write_manifest(out_dir, store.digests(), plan.plan_digest())

    return out_dir


def _run_kit_stage(
    stage: Stage,
    plan: Plan,
    rules: list[dict[str, Any]],
    store: FindingsStore,
    audit: AuditLog,
    out_dir: Path,
    max_exception_rate: float,
    ctx: dict[str, Any],
) -> None:
    from analystkit_mcp import tools as kit

    try:
        if stage.tool == "analystkit_profile":
            envelope = json.loads(kit.tool_profile(plan.source, None))
        elif stage.tool == "analystkit_validate":
            envelope = json.loads(kit.tool_validate(plan.source, None, rules))
        elif stage.tool == "analystkit_dedupe":
            envelope = json.loads(kit.tool_dedupe(plan.source, None, None))
        else:
            raise ExecutorError(
                f"Stage '{stage.stage_id}': tool '{stage.tool}' is not "
                f"executable in v0.1."
            )
    except (ExecutorError, ExecutionStopped):
        raise
    except Exception as exc:
        audit.record(
            stage.stage_id, f"kit:{stage.tool}", "error", str(exc)[:300]
        )
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            stage.stage_id, f"kit tool failed: {exc}"
        ) from None

    findings = dict(envelope["findings"])
    digest = store.put(stage.stage_id, findings)
    (out_dir / "findings" / f"{stage.stage_id}.json").write_text(
        store.to_json(stage.stage_id), encoding="utf-8"
    )

    passed, reason = _evaluate_gate(stage, findings, max_exception_rate, ctx)
    outcome = "pass" if passed else (
        "fail" if stage.gate is GateMode.MUST_PASS else "advisory_flag"
    )
    audit.record(
        stage.stage_id, f"kit:{stage.tool}", outcome, reason, sha256=digest
    )

    if not passed and stage.gate is GateMode.MUST_PASS:
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(stage.stage_id, reason)


def _evaluate_gate(
    stage: Stage,
    findings: dict[str, Any],
    max_exception_rate: float,
    ctx: dict[str, Any],
) -> tuple[bool, str]:
    """Gate semantics for v0.1 - declared, documented, testable."""
    if stage.tool == "analystkit_profile":
        columns = findings.get("columns", [])
        total = int(columns[0]["total"]) if columns else 0
        ctx["rows"] = total  # later gates need the denominator
        if total == 0:
            return False, "source has zero rows - nothing to analyse"
        # TOCTOU control: the source may have changed between planning and
        # execution. The plan recorded the classified column kinds at
        # approval time; a fresh classification must still contain them.
        plan_pairs = ctx.get("plan_column_kinds")
        if plan_pairs is not None:
            from delivery_engine.planner import classify_columns

            fresh = classify_columns(findings)
            fresh_pairs = {
                (name, k.value) for name, ks in fresh.items() for k in ks
            }
            missing = set(plan_pairs) - fresh_pairs
            if missing:
                return False, (
                    f"source drifted since plan approval: classified kinds "
                    f"{sorted(missing)} no longer hold. Re-plan and "
                    f"re-approve against the current source."
                )
        return True, f"profiled {total:,} rows across {len(columns)} columns"

    if stage.tool == "analystkit_validate":
        results = findings.get("results", [])
        exceptions = int(findings.get("total_exceptions", 0))
        # The profile ran first (playbook rule V2 guarantees it) and
        # recorded the denominator in the run context.
        rows = int(ctx.get("rows", 0)) or 1
        rate = exceptions / rows
        if rate > max_exception_rate:
            return False, (
                f"exception rate {rate:.1%} exceeds the declared gate "
                f"threshold {max_exception_rate:.0%} "
                f"({exceptions:,} exceptions) - source is not fit for "
                f"downstream analysis until investigated"
            )
        return True, (
            f"{len(results)} rules evaluated, {exceptions:,} exceptions "
            f"({rate:.1%}) - within the declared threshold"
        )

    if stage.tool == "analystkit_dedupe":
        dup = int(findings.get("duplicate_rows", 0))
        return True, f"{dup:,} duplicate row(s) found - recorded as evidence"

    return True, "no gate semantics defined; recorded"


def _run_ai_stage(
    stage: Stage,
    plan: Plan,
    store: FindingsStore,
    injector: NumberInjector,
    audit: AuditLog,
    out_dir: Path,
    playbook: Playbook,
) -> None:
    assert stage.slot is not None  # guaranteed by playbook validation (V8)
    if stage.slot is AiSlot.EDA_NOTEBOOK:
        text = build_eda_notebook(store, injector, plan.source)
    elif stage.slot is AiSlot.NARRATIVE_REPORT:
        text = build_narrative_report(store, injector, plan.source, plan.goal)
    elif stage.slot is AiSlot.README:
        text = build_readme(
            store, injector, plan.source, plan.goal, playbook.artifacts
        )
    else:
        raise ExecutorError(
            f"Stage '{stage.stage_id}': slot '{stage.slot}' is not "
            f"executable in v0.1 (rules_draft arrives with Human Gate 2 "
            f"wiring in a later step)."
        )

    # The injected-numbers rule, verified before the artifact may exist
    kind = "ipynb" if stage.slot is AiSlot.EDA_NOTEBOOK else "markdown"
    verify_artifact_numbers(text, injector, kind=kind)

    filename = ARTIFACT_FILENAMES[stage.slot]
    path = out_dir / filename
    path.write_text(text, encoding="utf-8")

    from delivery_engine.audit import file_sha256

    audit.record(
        stage.stage_id, f"ai:{stage.slot.value}", "artifact_written",
        f"{filename} built from findings store only; injected-numbers "
        f"rule verified against {len(injector.emitted)} emitted tokens",
        sha256=file_sha256(path),
    )
