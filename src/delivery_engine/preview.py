"""delivery_engine.preview - the pre-flight execution preview (step 16).

The problem this solves: a person runs the engine, waits through the
heavy stages, and only then discovers the playbook wasn't what they
meant - a stage they wanted was missing, the gate threshold was wrong,
the dataset was the wrong one. The fix is to show them exactly what is
about to run BEFORE anything runs, from the two documents that already
govern execution: the loaded playbook and the approved plan.

Constitutional posture:

- The preview ADDS information, never computes it. Every line is read
  from the playbook and the plan - the same objects the executor will
  use. There is no third source of truth to drift.
- The engine core stays NON-INTERACTIVE. `run()` is a library function
  called by 200+ tests, CI, and any future automation; a hardcoded
  "press ENTER" would hang all of them. Interactivity is therefore a
  CALLBACK: entry points (CLI, example scripts) pass `preview_confirm=`
  a callable that shows the text and returns True/False. Tests pass a
  lambda. Automation passes nothing and no pause happens.
- Declining is not an error swallowed - it is an ExecutionStopped with
  an audit entry, exactly like any other refusal in this engine.
- The rendered preview is written into the package as
  `execution_preview.md`, so what the human was shown is itself part
  of the hashed evidence (the manifest hashes every file).
"""
from __future__ import annotations

from collections.abc import Callable

from delivery_engine.planner import Plan
from delivery_engine.playbook import GateMode, Playbook, Stage, StageKind

__all__ = ["ConfirmCallback", "prompt_confirmation", "render_preview"]

# Shows the preview text, returns True to proceed / False to stop.
ConfirmCallback = Callable[[str], bool]

_RULE = "=" * 60


def _stage_line(stage: Stage) -> str:
    kind = stage.kind.value.upper()
    detail = ""
    if stage.kind is StageKind.KIT and stage.tool:
        detail = f" tool={stage.tool}"
    if stage.kind is StageKind.STATS and stage.stat_test:
        detail = f" stat_test={stage.stat_test}"
    if stage.kind is StageKind.AI and stage.slot:
        detail = f" slot={stage.slot}"
        if stage.human_approval:
            detail += " (human approval by hash)"
    gate = f" gate={stage.gate.value}" if stage.gate is not None else ""
    needs = f" needs={list(stage.needs)}" if stage.needs else ""
    return f"  - {stage.stage_id}: {kind}{detail}{gate}{needs}"


def render_preview(playbook: Playbook, plan: Plan) -> str:
    """Renders the human-readable pre-flight summary.

    Pure function of (playbook, plan): same inputs, same text. Reads
    only what the executor itself will read - nothing is computed here.
    """
    lines: list[str] = [
        "PLAYBOOK EXECUTION PREVIEW",
        _RULE,
        f"Dataset: {plan.source}",
        f"Playbook: {playbook.name} v{playbook.version} "
        f"({playbook.source_path.name})",
        f"Goal: {plan.goal}",
        f"Plan digest: {plan.plan_digest()}",
        f"Approved by: {plan.approved_by or 'NOT YET APPROVED'}",
        "",
        "COLUMN CLASSIFICATION (approved at Human Gate 1):",
    ]
    for col, kind in plan.column_kinds:
        lines.append(f"  - {col}: {kind}")
    lines += ["", "REQUIREMENT CHECKS:"]
    for check, ok, note in plan.requirement_results:
        lines.append(f"  - [{'PASS' if ok else 'FAIL'}] {check}: {note}")
    lines += ["", f"STAGES ({len(playbook.stages)}), in order:"]
    for stage in playbook.stages:
        lines.append(_stage_line(stage))
    has_stats = any(s.kind is StageKind.STATS for s in playbook.stages)
    if has_stats:
        lines += [
            "",
            f"STATISTICS: pre-registered alpha = {playbook.alpha} "
            f"(fixed now, before any p-value exists; significance never "
            f"gates)",
        ]
    must_pass = [s.stage_id for s in playbook.stages
                 if s.gate is GateMode.MUST_PASS]
    advisory = [s.stage_id for s in playbook.stages
                if s.gate is GateMode.ADVISORY]
    lines += [
        "",
        "GATES:",
        f"  - must_pass (can stop the run): {must_pass or 'none'}",
        f"  - advisory (recorded, never stop): {advisory or 'none'}",
        "",
        f"DELIVERABLES: {list(playbook.artifacts)}",
        f"OUTPUT FORMATS: {list(playbook.output_formats) or ['markdown']}",
        _RULE,
        "Proceed to execute exactly the above. Decline to stop with an "
        "audit entry and change the playbook or plan first.",
    ]
    return "\n".join(lines)


def prompt_confirmation(text: str) -> bool:
    """The interactive entry-point helper: prints the preview and waits.

    Deliberately NOT called anywhere inside the engine - pass it as
    run(..., preview_confirm=prompt_confirmation) from a CLI or script
    when a human is at the terminal. ENTER (or y/yes) proceeds;
    n/no declines.
    """
    print(text)
    answer = input(
        "Press ENTER to proceed, or type 'n' to cancel: "
    ).strip().lower()
    return answer in ("", "y", "yes")
