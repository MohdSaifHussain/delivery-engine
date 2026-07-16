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
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from delivery_engine.artifacts import (
    build_eda_notebook,
    build_narrative_report,
    build_ops_report,
    build_readme,
)
from delivery_engine.audit import AuditLog, write_manifest
from delivery_engine.planner import Plan
from delivery_engine.playbook import AiSlot, GateMode, Playbook, Stage, StageKind
from delivery_engine.rules_draft import draft_digest, draft_rules
from delivery_engine.store import (
    FindingsStore,
    NumberInjector,
    verify_artifact_numbers,
)

__all__ = ["MAX_EXCEPTION_RATE", "ExecutionStopped", "ExecutorError", "run"]

# Step 16: the pre-flight confirmation callback - receives the rendered
# preview text, returns True to proceed.
PreviewConfirm = Callable[[str], bool]

MAX_EXCEPTION_RATE: Final[float] = 0.10

ARTIFACT_FILENAMES: Final[dict[AiSlot, str]] = {
    AiSlot.EDA_NOTEBOOK: "eda_notebook.ipynb",
    AiSlot.NARRATIVE_REPORT: "narrative_report.md",
    AiSlot.README: "README.md",
    AiSlot.OPS_REPORT: "ops_report.md",
    AiSlot.PRESENTATION: "delivery_package.pptx",
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
    approvals: dict[str, str | dict[str, str]] | None = None,
    max_exception_rate: float = MAX_EXCEPTION_RATE,
    preview_confirm: PreviewConfirm | None = None,
) -> Path:
    """Executes an approved plan against its playbook. Returns out_dir.

    preview_confirm (step 16): optional callable receiving the rendered
    pre-flight preview text and returning True to proceed or False to
    stop. Entry points with a human at the terminal pass
    delivery_engine.preview.prompt_confirmation; tests pass a lambda;
    automation passes nothing and no pause happens. The engine core
    stays non-interactive by design - a library that blocks on stdin
    hangs every test, CI job, and scheduled run that calls it.
    Declining stops the run with an audit entry, like any refusal.
    The rendered preview is written to execution_preview.md either way,
    so what the human was shown is part of the hashed evidence.

    approvals:
      - human_gate stages: {stage_id: approver_name}
      - AI stages with human_approval=true (e.g. rules_draft):
        {stage_id: {"approver": name, "sha256": draft_digest}} - the
        approval is CONTENT-BOUND: it names the exact draft reviewed.
        The two-phase flow: run once, the pipeline stops at the gate
        and writes the draft with its hash; review; re-run supplying
        the hash. A mismatched hash is a different draft and is refused.
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
        s.stage_id for s in playbook.stages
        if s.kind is StageKind.HUMAN_GATE
        or (s.kind is StageKind.AI and s.human_approval)
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
    has_rules_draft = any(
        s.kind is StageKind.AI and s.slot is AiSlot.RULES_DRAFT
        for s in playbook.stages
    )
    if has_validate and not rules and not has_rules_draft:
        raise ExecutorError(
            "This playbook includes analystkit_validate but no rules were "
            "provided and it has no rules_draft stage. Declare expectations "
            "before running."
        )
    if has_rules_draft and rules:
        raise ExecutorError(
            "Two sources of rules: this playbook drafts rules for Human "
            "Gate 2 approval, AND explicit rules were supplied. Silent "
            "precedence would make one of them decorative - refusing. "
            "Either pass no rules (the approved draft runs) or use a "
            "playbook without a rules_draft stage."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "findings").mkdir(exist_ok=True)

    # ── Step 16: the pre-flight preview. Rendered from the same two
    # documents the executor runs from (no third source of truth),
    # written into the package (the manifest will hash it), and - only
    # when an entry point supplies a callback - shown for confirmation
    # BEFORE any heavy stage runs. Declining is an audited stop.
    from delivery_engine.preview import render_preview

    preview_text = render_preview(playbook, plan)
    (out_dir / "execution_preview.md").write_text(
        preview_text + "\n", encoding="utf-8"
    )
    if preview_confirm is not None and not preview_confirm(preview_text):
        audit.record(
            "preflight", "preview", "declined",
            "human reviewed the execution preview and declined to "
            "proceed; nothing was executed",
        )
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            "preflight",
            "execution declined at the pre-flight preview; adjust the "
            "playbook or plan and re-run with a FRESH output directory "
            "(this one now holds the declined preview and its audit "
            "entry - stopped runs keep their evidence, the step-9 rule)",
        )
    if preview_confirm is not None:
        audit.record(
            "preflight", "preview", "confirmed",
            "human reviewed the execution preview and confirmed",
        )

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
            raw = approvals.get(stage.stage_id)
            approver = raw if isinstance(raw, str) else None
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
            _run_ai_stage(
                stage, plan, store, injector, audit, out_dir, playbook,
                approvals, ctx,
            )
        elif stage.kind is StageKind.MODEL:
            _run_model_stage(stage, plan, store, audit, out_dir)
        elif stage.kind is StageKind.STATS:
            _run_stats_stage(stage, plan, playbook, store, audit, out_dir)
        elif stage.kind is StageKind.MATH:
            _run_math_stage(stage, plan, store, audit, out_dir)
        elif stage.kind is StageKind.PACKAGE:
            _build_deliverable_documents(
                playbook, plan, store, audit, out_dir
            )
            # Step 16: the multi-team handoff receipt - checks
            # pre-populated from the sealed findings, signatures null
            # (the engine never signs for a human). Written BEFORE the
            # manifest so the manifest hashes it.
            from delivery_engine.handoff import write_handoff

            write_handoff(out_dir, plan, playbook, store)
            audit.record(
                stage.stage_id, "package:handoff", "written",
                "handoff_manifest.json written: per-team checks "
                "generated from the hashed findings, signature fields "
                "null for humans to fill; the manifest hashes this file",
            )
            audit.record(
                stage.stage_id, "package", "sealed",
                "audit log sealed; the manifest is written next and hashes "
                "every file in the package including this log - nothing is "
                "written after the manifest",
            )
            audit.write(out_dir / "audit_log.jsonl")
            write_manifest(out_dir, store.digests(), plan.plan_digest())

    return out_dir


def _build_deliverable_documents(
    playbook: Playbook,
    plan: Plan,
    store: FindingsStore,
    audit: AuditLog,
    out_dir: Path,
) -> None:
    """Step 13: build the playbook's declared output formats and verify
    each one. markdown is produced by the AI artifact stages and needs no
    work here. For docx/pptx/xlsx/pdf, every number is injected from the
    store snapshot; the produced file is then verified — a HARD gate on
    store-sourced numbers (a missing number stops the pipeline), a SOFT
    check on prose sections (logged, non-fatal)."""
    formats = [f for f in playbook.output_formats if f != "markdown"]
    if not formats:
        return

    from delivery_engine.documents import (
        DocumentError,
        build_documents,
        verify_document_numbers,
    )

    snap = {
        sid: findings for sid, (findings, _) in store.all_entries().items()
    }
    snap["_digests"] = store.digests()

    try:
        results = build_documents(
            formats, snap, plan.source, plan.goal, out_dir
        )
    except DocumentError as exc:
        audit.record(
            "documents", "document_build", "error", str(exc)[:300]
        )
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped("documents", str(exc)) from None

    for fmt, info in results.items():
        verdict = verify_document_numbers(
            out_dir / info["file"], fmt, snap
        )
        if not verdict["ok"]:
            reason = (
                f"{fmt} deliverable is missing store-sourced number(s) "
                f"{verdict['missing_numbers'][:8]} — a finding was dropped "
                f"from the document. Hard gate: the pipeline stops rather "
                f"than ship a deliverable that omits a computed figure."
            )
            audit.record(
                "documents", f"document:{fmt}", "verification_failed", reason
            )
            audit.write(out_dir / "audit_log.jsonl")
            raise ExecutionStopped("documents", reason)
        soft = (
            f"; soft check: {len(verdict['missing_sections'])} prose "
            f"section(s) absent" if verdict["missing_sections"] else ""
        )
        audit.record(
            "documents", f"document:{fmt}", "verified",
            f"{fmt} deliverable built and verified — "
            f"{verdict['numbers_checked']} store-sourced number(s) present "
            f"(script sha256: {info['script_sha256'][:16]}...){soft}",
            sha256=info["script_sha256"],
        )


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
    if stage.tool == "opskit_run_playbook":
        _run_opskit_stage(stage, plan, store, audit, out_dir, ctx)
        return

    from analystkit_mcp import tools as kit

    try:
        if stage.tool == "analystkit_profile":
            envelope = json.loads(kit.tool_profile(plan.source, None))
        elif stage.tool == "analystkit_validate":
            effective_rules = rules or ctx.get("approved_drafted_rules", [])
            if not effective_rules:
                raise ExecutorError(
                    f"Stage '{stage.stage_id}': no rules available - the "
                    f"rules_draft stage did not run or was not approved."
                )
            envelope = json.loads(
                kit.tool_validate(plan.source, None, effective_rules)
            )
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


def _run_presentation_stage(
    stage: Stage,
    plan: Plan,
    store: FindingsStore,
    audit: AuditLog,
    out_dir: Path,
) -> None:
    """Deterministic PPT builder (step 11).

    Collects a snapshot of ALL findings in the store, builds a
    self-contained pptxgenjs JS script (a pure function of those
    findings), executes it via Node.js, and records the script's
    SHA-256 in the audit trail. Every number on every slide is a Python
    literal injected from the store snapshot - the script IS the
    auditable artifact; a reviewer can regenerate it from the same
    findings and compare hashes.

    The node_modules path is discovered at runtime so the stage works
    on both the build machine and the user's Windows machine after
    they install the npm package.
    """
    from delivery_engine.presentation import (
        PresentationError,
        build_presentation_script,
        run_script,
    )

    # Discover node_modules: repo-level first (created by npm install
    # pptxgenjs in the delivery-engine directory — the canonical location
    # on both Linux and Windows), then the build-machine path.
    candidate_paths = [
        str(Path.cwd() / "node_modules"),
        "/home/claude/pptwork/node_modules",
        str(Path(plan.source).parent / "node_modules"),
    ]
    node_modules = next(
        (p for p in candidate_paths if (Path(p) / "pptxgenjs").exists()),
        None,
    )
    if node_modules is None:
        reason = (
            "pptxgenjs not found in any of: "
            + ", ".join(candidate_paths)
            + ". Install it with: npm install pptxgenjs (or "
            + "npm install -g pptxgenjs). The presentation stage fails "
            + "loudly on a missing dependency."
        )
        audit.record(stage.stage_id, "presentation", "error", reason)
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(stage.stage_id, reason)

    snapshot = store.all_entries()
    store_snapshot = {
        sid: findings for sid, (findings, _) in snapshot.items()
    }
    store_snapshot["_digests"] = store.digests()

    out_pptx = out_dir / "delivery_package.pptx"
    try:
        script = build_presentation_script(
            store_snapshot, plan.source, plan.goal,
            str(out_pptx), node_modules,
        )
        script_sha256 = run_script(script, out_pptx)
    except PresentationError as exc:
        audit.record(stage.stage_id, "presentation", "error", str(exc)[:300])
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(stage.stage_id, str(exc)) from None

    audit.record(
        stage.stage_id, "presentation", "artifact_written",
        f"pptxgenjs deck written ({out_pptx.stat().st_size:,} bytes); "
        f"generator script sha256: {script_sha256[:16]}... — "
        f"same findings reproduce the same script and the same deck",
        sha256=script_sha256,
    )


def _run_model_stage(
    stage: Stage,
    plan: Plan,
    store: FindingsStore,
    audit: AuditLog,
    out_dir: Path,
) -> None:
    """The deterministic baseline model stage (step 10).

    The stage decides nothing: target and features come from the plan's
    classified column kinds - the same classification the human approved
    at Human Gate 1. Training is fixed-seed and fully deterministic
    (delivery_engine.model docstring cites the scikit-learn
    controlling-randomness guidance). Metrics land in the Findings Store
    hashed; AI stages may narrate them, never compute them.

    Gate semantics: must_pass fails when a valid baseline CANNOT be
    trained (missing dependency, wrong class count, plan/source drift,
    too-small minority class). Metric VALUES never gate - the engine
    holds no opinion on how good a baseline should be; that judgment is
    explicitly the human's (charter section 5).
    """
    from delivery_engine.model import ModelError, train_baseline

    kinds = list(plan.column_kinds)
    targets = [c for c, k in kinds if k == "binary_target"]
    if not targets:
        reason = (
            "plan carries no binary_target column - the baseline model "
            "stage requires one (the playbook's requirements should have "
            "demanded required_kinds = ['binary_target'])"
        )
        audit.record(stage.stage_id, "model:baseline", "fail", reason)
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(stage.stage_id, reason)
    # Disclosed deterministic selection: the first binary_target in plan
    # column order - the same order the human saw and approved at Human
    # Gate 1. All candidates and the rule are recorded in the hashed
    # findings and the audit entry; the report names the target. Not a
    # silent guess, not a refusal (a yes/no flag column is ordinary data,
    # and refusing on it would make the archetype unusable).
    target = targets[0]
    id_cols = {c for c, k in kinds if k == "id_column"}
    numeric = [c for c, k in kinds
               if k == "numeric_column" and c != target and c not in id_cols]
    categorical = [c for c, k in kinds
                   if k == "categorical_column" and c != target
                   and c not in id_cols]

    try:
        findings = train_baseline(plan.source, target, numeric, categorical)
        findings["target_candidates"] = sorted(set(targets))
        findings["target_selection"] = (
            "first binary_target in plan column order (plan approved at "
            "Human Gate 1); candidates listed under target_candidates"
        )
    except ModelError as exc:
        outcome = "fail" if stage.gate is GateMode.MUST_PASS else "advisory_flag"
        audit.record(stage.stage_id, "model:baseline", outcome, str(exc)[:300])
        audit.write(out_dir / "audit_log.jsonl")
        if stage.gate is GateMode.MUST_PASS:
            raise ExecutionStopped(stage.stage_id, str(exc)) from None
        return

    digest = store.put(stage.stage_id, findings)
    (out_dir / "findings" / f"{stage.stage_id}.json").write_text(
        store.to_json(stage.stage_id), encoding="utf-8"
    )
    audit.record(
        stage.stage_id, "model:baseline", "pass",
        f"deterministic baseline trained on target '{target}' (selected "
        f"as first binary candidate of {sorted(set(targets))}) "
        f"(seed {findings['random_seed']}, stratified "
        f"{findings['n_train']}/{findings['n_test']} split); metrics "
        f"stored hashed - metric values never gate, training feasibility "
        f"does (declared step 10 semantics)",
        sha256=digest,
    )


def _run_stats_stage(
    stage: Stage,
    plan: Plan,
    playbook: Playbook,
    store: FindingsStore,
    audit: AuditLog,
    out_dir: Path,
) -> None:
    """The deterministic statistical inference stage (step 15).

    The stage decides nothing: target and feature columns come from the
    plan's classified kinds - the classification the human approved at
    Human Gate 1 - and alpha comes pre-registered from the playbook's
    [stats] table, approved with the same plan, before any p-value
    existed. The suite of tests is the playbook's declared stat_test
    (V14); every method is fixed and traced to primary sources in
    delivery_engine.stats.

    Gate semantics, the step-10 principle extended: must_pass fails when
    inference CANNOT be produced (missing dependency, plan/source drift,
    degenerate target, nothing testable). SIGNIFICANCE NEVER GATES - a
    pipeline that stops or proceeds on p-values is p-hacking machinery.
    That judgment is explicitly the human's (charter section 5).
    """
    from delivery_engine.stats import StatsError, run_inference

    kinds = list(plan.column_kinds)
    targets = [c for c, k in kinds if k == "binary_target"]
    if not targets:
        reason = (
            "plan carries no binary_target column - the inference stage "
            "requires one (the playbook's requirements should have "
            "demanded required_kinds = ['binary_target'])"
        )
        audit.record(stage.stage_id, "stats:inference", "fail", reason)
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(stage.stage_id, reason)
    # Disclosed deterministic selection - the same rule, wording, and
    # disclosure the model stage uses (step 10): first binary_target in
    # the plan column order the human approved at Human Gate 1.
    target = targets[0]
    id_cols = {c for c, k in kinds if k == "id_column"}
    numeric = [c for c, k in kinds
               if k == "numeric_column" and c != target and c not in id_cols]
    categorical = [c for c, k in kinds
                   if k == "categorical_column" and c != target
                   and c not in id_cols]

    stat_test = stage.stat_test or "full_inference"
    try:
        findings = run_inference(
            plan.source, stat_test, target, categorical, numeric,
            playbook.alpha,
        )
        findings["target_candidates"] = sorted(set(targets))
        findings["target_selection"] = (
            "first binary_target in plan column order (plan approved at "
            "Human Gate 1); candidates listed under target_candidates"
        )
    except StatsError as exc:
        outcome = "fail" if stage.gate is GateMode.MUST_PASS else "advisory_flag"
        audit.record(stage.stage_id, "stats:inference", outcome, str(exc)[:300])
        audit.write(out_dir / "audit_log.jsonl")
        if stage.gate is GateMode.MUST_PASS:
            raise ExecutionStopped(stage.stage_id, str(exc)) from None
        return

    digest = store.put(stage.stage_id, findings)
    (out_dir / "findings" / f"{stage.stage_id}.json").write_text(
        store.to_json(stage.stage_id), encoding="utf-8"
    )
    n_tests = len(findings.get("tests", []))
    n_props = len(findings.get("proportions", []))
    n_skips = len(findings.get("skipped", []))
    audit.record(
        stage.stage_id, "stats:inference", "pass",
        f"deterministic inference on target '{target}' "
        f"(suite '{stat_test}', pre-registered alpha "
        f"{findings['alpha']}): {n_tests} hypothesis test(s) with "
        f"Benjamini-Hochberg FDR control, {n_props} Wilson interval(s), "
        f"{n_skips} skip(s) recorded with reasons; findings stored "
        f"hashed - significance never gates, feasibility does (declared "
        f"step 15 semantics)",
        sha256=digest,
    )


def _run_math_stage(
    stage: Stage,
    plan: Plan,
    store: FindingsStore,
    audit: AuditLog,
    out_dir: Path,
) -> None:
    """The deterministic descriptive math stage (step 17).

    Columns come from the plan's classified kinds - approved at Human
    Gate 1, never auto-detected behind the human's back. The declared
    math_checks suite (V15) selects which fixed, sourced procedures
    run; every threshold those procedures use is a constant disclosed
    inside the hashed findings. Findings never gate; feasibility does
    (missing dependency, plan/source drift, nothing measurable).
    """
    from delivery_engine.mathkit import MathError, run_math

    kinds = list(plan.column_kinds)
    id_cols = {c for c, k in kinds if k == "id_column"}
    binary = {c for c, k in kinds if k == "binary_target"}
    # M2 (step-17 hunt): a two-valued column is a category wearing a
    # number's clothes - skewness, tail percentiles, and distribution
    # fits on 0/1 data are noise. Binary columns are excluded from the
    # numeric suite (they remain available to the stats stage, where
    # they belong); the exclusion is disclosed in the findings.
    numeric = [c for c, k in kinds
               if k == "numeric_column" and c not in id_cols
               and c not in binary]
    categorical = [c for c, k in kinds
                   if k == "categorical_column" and c not in id_cols]
    timestamps = [c for c, k in kinds
                  if k == "timestamp_column" and c not in id_cols]

    checks = stage.math_checks or "all"
    try:
        findings = run_math(plan.source, checks, numeric, categorical,
                            timestamps)
        findings["column_selection"] = (
            "numeric, categorical, and timestamp kinds from the plan "
            "approved at Human Gate 1; id columns excluded; two-valued "
            "(binary_target) columns excluded from the numeric suite - "
            "shape statistics on 0/1 data are noise, and inference on "
            "them belongs to the stats stage"
        )
    except MathError as exc:
        outcome = "fail" if stage.gate is GateMode.MUST_PASS else "advisory_flag"
        audit.record(stage.stage_id, "math:descriptive", outcome,
                     str(exc)[:300])
        audit.write(out_dir / "audit_log.jsonl")
        if stage.gate is GateMode.MUST_PASS:
            raise ExecutionStopped(stage.stage_id, str(exc)) from None
        return

    digest = store.put(stage.stage_id, findings)
    (out_dir / "findings" / f"{stage.stage_id}.json").write_text(
        store.to_json(stage.stage_id), encoding="utf-8"
    )
    counts = {k: len(findings[k]) for k in
              ("numeric", "outliers", "distribution_fit", "categorical",
               "temporal")}
    audit.record(
        stage.stage_id, "math:descriptive", "pass",
        f"deterministic descriptive math (suite '{checks}'): "
        f"{counts['numeric']} numeric shape profile(s), "
        f"{counts['outliers']} MAD outlier scan(s), "
        f"{counts['distribution_fit']} distribution fit(s) with the "
        f"Lilliefors correction, {counts['categorical']} entropy "
        f"profile(s), {counts['temporal']} temporal profile(s), "
        f"{len(findings['skipped'])} skip(s) recorded with reasons; all "
        f"thresholds fixed constants disclosed in the findings; "
        f"findings stored hashed - descriptive values never gate "
        f"(declared step 17 semantics)",
        sha256=digest,
    )


def _run_opskit_stage(
    stage: Stage,
    plan: Plan,
    store: FindingsStore,
    audit: AuditLog,
    out_dir: Path,
    ctx: dict[str, Any],
) -> None:
    """The OpsKit kit stage (step 7 wiring).

    Same consumption pattern as analystkit stages: the engine imports the
    MCP wrapper's tool layer directly - the same function an MCP client
    would hit - and stores the deterministic payload as findings.

    SEAL VERIFICATION (layered defense, charter 4.9): the opskit-mcp
    envelope carries its own payload_sha256, computed by the wrapper. The
    engine recomputes it before storing. A mismatch means the payload was
    altered between the wrapper and the engine - the store verifies the
    kit's seal rather than trusting it.

    GATE SEMANTICS, declared: OpsKit marks findings CRITICAL for two very
    different reasons - data unfitness (zero rows) and operational insight
    (a volume surge, a sustained shift). Unfitness fails must_pass;
    insight IS the deliverable and is recorded as evidence. A pipeline
    that stops precisely when it finds something interesting would be a
    broken control. This deliberately diverges from OpsKit's CLI exit
    codes (exit 2 on any critical), which are right for CI and wrong for
    a delivery pipeline.
    """
    from opskit_mcp.envelope import sha256_of
    from opskit_mcp.server import opskit_run_playbook

    assert stage.ops_playbook is not None  # guaranteed by playbook V11
    try:
        envelope = opskit_run_playbook(stage.ops_playbook, plan.source)
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

    payload = dict(envelope["payload"])
    schema = str(envelope.get("schema", ""))
    if schema != "opskit.envelope/v1":
        audit.record(
            stage.stage_id, f"kit:{stage.tool}", "unknown_envelope_schema",
            f"envelope schema '{schema}' is not the supported "
            f"'opskit.envelope/v1' - refusing to interpret it",
        )
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            stage.stage_id,
            f"opskit envelope schema '{schema}' is not supported by this "
            f"engine version. Fail closed: unknown schemas are never "
            f"interpreted by guesswork.",
        )
    claimed = str(envelope.get("payload_sha256", ""))
    recomputed = sha256_of(payload)
    if claimed != recomputed:
        audit.record(
            stage.stage_id, f"kit:{stage.tool}", "seal_mismatch",
            f"envelope claims payload sha256 {claimed[:16]}... but the "
            f"payload recomputes to {recomputed[:16]}... - the payload "
            f"was altered between the kit and the engine",
        )
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            stage.stage_id,
            "opskit envelope seal mismatch: the payload does not hash to "
            "its claimed sha256. Evidence that cannot verify its own seal "
            "does not enter the Findings Store.",
        )

    findings = payload.get("findings")
    if not isinstance(findings, list) or not all(
        isinstance(f, dict) for f in findings
    ):
        audit.record(
            stage.stage_id, f"kit:{stage.tool}", "malformed_payload",
            "payload.findings is not a list of finding objects - the seal "
            "proves integrity, not shape; refusing malformed content",
        )
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            stage.stage_id,
            "opskit payload is malformed: findings is not a list of "
            "finding objects. A correctly sealed payload with the wrong "
            "shape is still refused.",
        )

    digest = store.put(stage.stage_id, payload)
    (out_dir / "findings" / f"{stage.stage_id}.json").write_text(
        store.to_json(stage.stage_id), encoding="utf-8"
    )

    unfit = [
        f for f in findings
        if f.get("severity") == "CRITICAL" and f.get("step") == "shape"
    ]
    insight_criticals = sum(
        1 for f in findings
        if f.get("severity") == "CRITICAL" and f.get("step") != "shape"
    )

    if unfit:
        reason = (
            f"opskit '{stage.ops_playbook}' found the source unfit: "
            f"{unfit[0].get('text', 'shape critical')}"
        )
        outcome = "fail" if stage.gate is GateMode.MUST_PASS else "advisory_flag"
        audit.record(
            stage.stage_id, f"kit:{stage.tool}", outcome, reason, sha256=digest
        )
        if stage.gate is GateMode.MUST_PASS:
            audit.write(out_dir / "audit_log.jsonl")
            raise ExecutionStopped(stage.stage_id, reason)
        return

    audit.record(
        stage.stage_id, f"kit:{stage.tool}", "pass",
        f"opskit '{stage.ops_playbook}': {len(findings)} finding(s), "
        f"{insight_criticals} operational critical(s) recorded as evidence "
        f"(insight criticals do not stop the pipeline - declared step 7 "
        f"gate semantics); wrapper seal verified",
        sha256=digest,
    )


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
    approvals: dict[str, str | dict[str, str]],
    ctx: dict[str, Any],
) -> None:
    assert stage.slot is not None  # guaranteed by playbook validation (V8)
    if stage.slot is AiSlot.RULES_DRAFT:
        _run_rules_draft_stage(stage, store, audit, out_dir, approvals, ctx)
        return
    if stage.slot is AiSlot.EDA_NOTEBOOK:
        text = build_eda_notebook(store, injector, plan.source)
    elif stage.slot is AiSlot.NARRATIVE_REPORT:
        text = build_narrative_report(store, injector, plan.source, plan.goal)
    elif stage.slot is AiSlot.README:
        text = build_readme(
            store, injector, plan.source, plan.goal, playbook.artifacts
        )
    elif stage.slot is AiSlot.OPS_REPORT:
        # Declared inputs (stage contract 4.7): the first entry in needs
        # names the stage whose findings this report renders.
        if not stage.needs:
            raise ExecutorError(
                f"Stage '{stage.stage_id}': slot 'ops_report' requires "
                f"needs to name the OpsKit findings stage it renders - "
                f"declared inputs, never guessed."
            )
        text = build_ops_report(
            store, injector, plan.source, plan.goal, stage.needs[0]
        )
    elif stage.slot is AiSlot.PRESENTATION:
        _run_presentation_stage(stage, plan, store, audit, out_dir)
        return   # file written directly; normal text path skipped
    else:
        raise ExecutorError(
            f"Stage '{stage.stage_id}': slot '{stage.slot}' is not "
            f"executable in this version."
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


def _run_rules_draft_stage(
    stage: Stage,
    store: FindingsStore,
    audit: AuditLog,
    out_dir: Path,
    approvals: dict[str, str | dict[str, str]],
    ctx: dict[str, Any],
) -> None:
    """Human Gate 2, content-bound (charter 4.4).

    Phase 1 (no approval): draft, write rules_draft.json with its hash,
    stop the pipeline. Phase 2 (approval quoting the hash): verify the
    hash matches THIS draft, record who approved what, hand the rules to
    the deterministic layer via the run context.
    """
    profile_stage = stage.needs[0] if stage.needs else "dq_profile"
    rules, rationales = draft_rules(store.get(profile_stage))
    if not rules:
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            stage.stage_id,
            "the profile justified no draftable rules - declare rules "
            "explicitly instead of running the rules_draft archetype",
        )
    digest = draft_digest(rules)

    draft_doc = {
        "stage": stage.stage_id,
        "drafted_from": profile_stage,
        "rules": rules,
        "rationales": rationales,
        "sha256": digest,
        "how_to_approve": (
            "Review every rule and rationale. To approve, re-run with "
            f'approvals={{"{stage.stage_id}": {{"approver": "<your name>", '
            f'"sha256": "{digest}"}}}}. The hash binds the approval to '
            "exactly this draft."
        ),
    }
    (out_dir / "rules_draft.json").write_text(
        json.dumps(draft_doc, indent=2, sort_keys=True), encoding="utf-8"
    )

    raw = approvals.get(stage.stage_id)
    if raw is None:
        audit.record(
            stage.stage_id, "ai:rules_draft", "awaiting_human_gate_2",
            f"{len(rules)} rule(s) drafted with rationales; draft written "
            f"to rules_draft.json; approval must quote sha256 {digest[:16]}...",
            sha256=digest,
        )
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            stage.stage_id,
            "Human Gate 2: engine-drafted rules await content-bound "
            "approval. Review rules_draft.json and re-run quoting its "
            "sha256. (Charter 4.4)",
        )
    if (
        not isinstance(raw, dict)
        or not str(raw.get("approver", "")).strip()
        or "sha256" not in raw
    ):
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            stage.stage_id,
            "Human Gate 2 approval for a feeds_deterministic stage must be "
            'content-bound: {"approver": name, "sha256": draft_hash}.',
        )
    if raw["sha256"] != digest:
        audit.record(
            stage.stage_id, "ai:rules_draft", "approval_hash_mismatch",
            f"approval quotes {raw['sha256'][:16]}... but this draft is "
            f"{digest[:16]}... - a different draft was reviewed",
            sha256=digest,
        )
        audit.write(out_dir / "audit_log.jsonl")
        raise ExecutionStopped(
            stage.stage_id,
            "Human Gate 2: approval hash does not match this draft. What "
            "was reviewed is not what would run - refusing. Re-review "
            "rules_draft.json and approve its current sha256.",
        )

    ctx["approved_drafted_rules"] = rules
    audit.record(
        stage.stage_id, "ai:rules_draft", "approved",
        f"{len(rules)} drafted rule(s) approved by {raw['approver']} - "
        f"content-bound to sha256 {digest[:16]}...; handed to the "
        f"deterministic layer",
        sha256=digest,
    )
