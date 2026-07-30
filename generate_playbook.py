#!/usr/bin/env python
"""Compile a DRAFT playbook for YOUR dataset and goal.

    python generate_playbook.py --source data/my.csv \
        --goal "monthly claims audit" --name claims_audit \
        --include math,stats

Flags omitted at a terminal are asked interactively. The output is a
DRAFT under playbooks/generated/ plus a .rules.json of evidence-drafted
validation rules; review both, then run via run_project.py with
--playbook-approved-by "Your Name". Logic lives (typed, tested, gated)
in delivery_engine.generator.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analystkit_mcp.tools import tool_profile

from delivery_engine.generator import (
    STAGE_MENU,
    GeneratorError,
    compile_playbook,
)


def _ask(value: str | None, question: str) -> str:
    if value:
        return value
    answer = input(f"{question}: ").strip()
    if not answer:
        raise SystemExit(f"Required: {question}")
    return answer


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source")
    ap.add_argument("--goal")
    ap.add_argument("--name")
    ap.add_argument("--include",
                    help="comma-separated stages: " + ",".join(STAGE_MENU))
    ap.add_argument("--min-rows", type=int, default=100)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--playbook-dir", default="playbooks")
    args = ap.parse_args(argv)

    source = _ask(args.source, "Dataset CSV path")
    goal = _ask(args.goal, "Analysis goal")
    name = _ask(args.name, "Playbook name (lowercase_slug)")
    if args.include is None:
        print("Available analysis stages:")
        for key, desc in STAGE_MENU.items():
            print(f"  {key:7s} {desc}")
        raw = input("Include (comma-separated, blank for math only): ")
        include = [s.strip() for s in raw.split(",") if s.strip()] or ["math"]
    else:
        include = [s.strip() for s in args.include.split(",") if s.strip()]

    print(f"Profiling: {source}")
    envelope = json.loads(tool_profile(source, None))
    try:
        result = compile_playbook(
            source, goal, name, Path(args.playbook_dir),
            envelope["findings"], include,
            min_rows=args.min_rows, alpha=args.alpha,
        )
    except GeneratorError as exc:
        raise SystemExit(f"REFUSED: {exc}") from exc

    print(json.dumps(result.decisions, indent=2))
    print(f"\nDRAFT playbook: {result.playbook_path}")
    print(f"Drafted rules:  {result.rules_path}")
    print(
        "\nNext: read both files, then run:\n"
        f'  python run_project.py --source "{source}" --goal "{goal}" '
        f"--playbook {name} --rules {result.rules_path} "
        f'--approver "Your Name" --playbook-approved-by "Your Name"'
    )


if __name__ == "__main__":
    main(sys.argv[1:])
