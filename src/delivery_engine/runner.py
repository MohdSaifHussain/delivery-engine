"""delivery_engine.runner - the one project runner.

Step 19. Instead of a copy-pasted run_<project>.py per dataset - the
Python edition of the spreadsheet-drift failure mode the error
literature documents - the repo ships ONE runner, tested and hardened
once, that any project drives with configuration:

    python run_project.py --source data/my.csv \
        --goal "audit Q3 claims" --playbook universal_audit \
        --approver "A. Analyst"

Design positions:

- FLAGS WITH INTERACTIVE FALLBACK. Every required input can be a flag
  (scriptable, CI-able) or, when omitted at a terminal, a prompt. The
  step-16 pre-flight preview is shown and confirmed by default; --yes
  skips it for automation.
- GENERATED DRAFTS REQUIRE A NAMED REVIEWER. A playbook living under
  playbooks/generated/ is a draft the pipeline compiled; running it
  demands --playbook-approved-by <name>, recorded in the run goal's
  audit trail. A pipeline must never approve its own rules of
  engagement.
- OVERRIDES ARE LOUD. Raising --max-exception-rate above the engine
  default prints an unmissable warning naming the risk (the July 2026
  fraud-run lesson: a 400% override waved a tool bug into a VP
  package). The flag exists because judgment is human; the noise
  exists because silence is how overrides become habits.
- NOTHING HERE EXTENDS THE ENGINE. This module is entry-point layer
  only: profile -> compatibility report -> plan -> typed approval ->
  run with preview. Every control it touches already exists.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from analystkit_mcp.tools import tool_profile

from delivery_engine import (
    ExecutionStopped,
    approve_plan,
    load_playbook,
    make_plan,
    run,
)
from delivery_engine.compatibility import build_compatibility_report
from delivery_engine.executor import MAX_EXCEPTION_RATE
from delivery_engine.generator import GENERATED_DIR_NAME
from delivery_engine.preview import prompt_confirmation

__all__ = ["main"]


def _ask(value: str | None, question: str) -> str:
    if value:
        return value
    answer = input(f"{question}: ").strip()
    if not answer:
        raise SystemExit(f"Required: {question}")
    return answer


_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")


def _resolve_playbook(arg: str, playbook_dir: Path) -> Path:
    """A .toml path is used as given; anything else must be a strict
    lowercase slug resolved against playbooks/ then
    playbooks/generated/ - no path fragments smuggled through name
    resolution (step-19 hunt, L5)."""
    p = Path(arg)
    if p.suffix == ".toml":
        if p.exists():
            return p
        raise SystemExit(f"Playbook file not found: {p}")
    if not _NAME_RE.match(arg):
        raise SystemExit(
            f"'{arg}' is neither an existing .toml path nor a valid "
            f"playbook name (lowercase letters, digits, underscores)."
        )
    for candidate in (playbook_dir / f"{arg}.toml",
                      playbook_dir / GENERATED_DIR_NAME / f"{arg}.toml"):
        if candidate.exists():
            return candidate
    raise SystemExit(
        f"Playbook '{arg}' not found in {playbook_dir} or "
        f"{playbook_dir / GENERATED_DIR_NAME}."
    )


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(
        description=(
            "Run any dataset through a Delivery Engine playbook: "
            "profile, compatibility, approved plan, pre-flight "
            "preview, governed execution, sealed package."
        )
    )
    ap.add_argument("--source", help="path to the CSV dataset")
    ap.add_argument("--goal", help="what this analysis is for")
    ap.add_argument("--playbook",
                    help="playbook name (curated or generated) or path")
    ap.add_argument("--rules", help="path to a validation-rules JSON "
                                    "(e.g. a generated .rules.json)")
    ap.add_argument("--out", default="output/run",
                    help="output directory (default: output/run)")
    ap.add_argument("--approver",
                    help="your name - recorded at Human Gate 1")
    ap.add_argument("--playbook-approved-by",
                    help="required for playbooks under "
                         "playbooks/generated/: the reviewer's name")
    ap.add_argument("--max-exception-rate", type=float,
                    default=MAX_EXCEPTION_RATE,
                    help="exception-rate gate (default engine value); "
                         "raising it prints a loud warning")
    ap.add_argument("--yes", action="store_true",
                    help="skip the interactive pre-flight confirmation "
                         "(automation mode)")
    ap.add_argument("--playbook-dir", default="playbooks",
                    help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    source = _ask(args.source, "Dataset CSV path")
    goal = _ask(args.goal, "Analysis goal")
    playbook_arg = _ask(args.playbook, "Playbook (name or path)")
    approver = _ask(args.approver, "Your name (Human Gate 1 approver)")

    playbook_dir = Path(args.playbook_dir)
    pb_path = _resolve_playbook(playbook_arg, playbook_dir)

    # Generated drafts: the constitution the pipeline wrote needs a
    # human signature before it governs a run.
    if GENERATED_DIR_NAME in pb_path.parts:
        if not args.playbook_approved_by:
            raise SystemExit(
                f"'{pb_path}' is a GENERATED DRAFT. Read it, then re-run "
                f"with --playbook-approved-by \"Your Name\" to state you "
                f"reviewed its stages and gates. A pipeline must never "
                f"approve its own rules of engagement."
            )
        print(f"Generated playbook approved for use by: "
              f"{args.playbook_approved_by}")

    if args.max_exception_rate > MAX_EXCEPTION_RATE:
        print(
            "\n" + "!" * 70 +
            f"\n!! OVERRIDE: --max-exception-rate="
            f"{args.max_exception_rate} exceeds the engine default "
            f"({MAX_EXCEPTION_RATE}).\n"
            f"!! High exception counts are evidence - of dirty data OR "
            f"of wrong rules.\n"
            f"!! Diagnose before overriding; the audit log will record "
            f"this run's gate.\n" + "!" * 70 + "\n"
        )

    rules: list[dict[str, Any]] = []
    if args.rules:
        rules_path = Path(args.rules)
        if not rules_path.exists():
            raise SystemExit(f"Rules file not found: {rules_path}")
        try:
            rules = json.loads(rules_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"Rules file {rules_path} is not valid JSON "
                f"(line {exc.lineno}): {exc.msg}. Expected a list like "
                f'[{{"column": "id", "rule": "unique"}}].'
            ) from exc
        if not isinstance(rules, list):
            raise SystemExit(
                f"Rules file {rules_path} must contain a JSON LIST of "
                f"rule objects."
            )

    # Fail BEFORE the work, not after: a playbook that validates needs
    # declared rules (the engine will refuse anyway - charter position
    # from step 8); the runner says so up front with the remedy.
    pb_probe = load_playbook(pb_path)
    needs_rules = any(st.tool == "analystkit_validate"
                      for st in pb_probe.stages)
    has_draft_stage = any(
        st.slot is not None and st.slot.value == "rules_draft"
        for st in pb_probe.stages
    )
    if needs_rules and not rules and not has_draft_stage:
        raise SystemExit(
            f"Playbook '{pb_probe.name}' validates data but no rules "
            f"were provided. Pass --rules <file.json> - e.g. generate "
            f"evidence-drafted rules with generate_playbook.py, or "
            f"write a minimal file like "
            f'[{{"column": "your_id", "rule": "unique"}}].'
        )

    print(f"Profiling: {source}")
    envelope = json.loads(tool_profile(source, None))
    findings = envelope["findings"]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = build_compatibility_report(findings, playbook_dir, source)
    (out / "compatibility_report.md").write_text(report, encoding="utf-8")
    print(f"Compatibility report: {out / 'compatibility_report.md'}")

    pb = pb_probe
    plan = make_plan(goal, source, findings, pb_path.parent,
                     chosen_playbook=pb.name)
    plan = approve_plan(plan, approver)

    confirm = None if args.yes else prompt_confirmation
    try:
        final = run(
            plan, pb, rules, out / "final",
            approvals={"plan_approval": approver},
            max_exception_rate=args.max_exception_rate,
            preview_confirm=confirm,
        )
    except ExecutionStopped as exc:
        print(f"\nSTOPPED: {exc}")
        print("The audit log in the output directory records why.")
        raise SystemExit(2) from exc

    print(f"\nPackage sealed: {final}")
    print(f"  manifest:  {final / 'manifest.json'}")
    print(f"  narrative: {final / 'narrative_report.md'}")
    print(f"  handoff:   {final / 'handoff_manifest.json'}")
    return final


if __name__ == "__main__":
    main(sys.argv[1:])
