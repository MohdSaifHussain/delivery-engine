"""delivery_engine.compatibility - the Playbook Compatibility Report.

The deterministic front door (build step 14). Before any work runs, an
analyst — engineer or not — can ask one question: "which playbooks can
run on my dataset, and why or why not?" This module answers it as a
readable markdown report.

Design rules:
- It REUSES the planner's own classification and requirement checks
  (classify_columns, check_requirements). The report can therefore never
  disagree with the planner: same functions, same verdicts. No logic is
  duplicated to drift.
- It is a pure function of (profile findings, playbook library, source).
  Same inputs, same report, byte for byte. No AI anywhere.
- It never gates or blocks. It informs. The planner's requirement checks
  remain the enforcement point (nothing overrides a failed row); the
  report is the human-readable surface of the same facts.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from delivery_engine.planner import check_requirements, classify_columns
from delivery_engine.playbook import Playbook, PlaybookError, load_playbook

__all__ = ["CompatibilityError", "build_compatibility_report"]


class CompatibilityError(Exception):
    """A compatibility-report problem, stated cleanly."""


def _load_library(playbook_dir: Path) -> list[Playbook]:
    paths = sorted(playbook_dir.glob("*.toml"))
    if not paths:
        raise CompatibilityError(
            f"No playbooks found in {playbook_dir}. The report needs a "
            f"library to evaluate against."
        )
    loaded: list[Playbook] = []
    for p in paths:
        try:
            loaded.append(load_playbook(p))
        except PlaybookError as exc:
            raise CompatibilityError(
                f"Playbook library contains an invalid playbook: {exc}"
            ) from None
    return loaded


def build_compatibility_report(
    profile_findings: dict[str, Any],
    playbook_dir: Path,
    source: str,
) -> str:
    """Returns a markdown Playbook Compatibility Report.

    For every playbook in the library: does this dataset qualify, and
    check by check, why or why not. Ends with the dataset's classified
    column kinds so the reader can see what the planner sees.
    """
    library = _load_library(playbook_dir)

    columns = profile_findings.get("columns", [])
    total_rows = int(columns[0]["total"]) if columns else 0

    lines: list[str] = [
        "# Playbook Compatibility Report",
        "",
        f"**Source:** `{source}`",
        f"**Rows:** {total_rows:,}  |  **Columns:** {len(columns)}",
        "",
        "Deterministic pre-flight: for each playbook in the library, the "
        "exact requirement checks the planner will enforce, and their "
        "verdicts on this dataset. Nothing here is advisory prose - these "
        "are the same functions the planner runs, so this report cannot "
        "disagree with it.",
        "",
    ]

    qualified: list[str] = []
    for pb in library:
        rows = check_requirements(pb, profile_findings, source)
        ok_all = all(ok for _, ok, _ in rows)
        if ok_all:
            qualified.append(pb.name)
        verdict = "QUALIFIES" if ok_all else "DOES NOT QUALIFY"
        lines += [
            f"## {pb.name} v{pb.version} — {verdict}",
            "",
            f"*{pb.description}*",
            "",
            "| Check | Result | Detail |",
            "|---|---|---|",
        ]
        for check, ok, note in rows:
            mark = "PASS" if ok else "FAIL"
            lines.append(f"| {check} | {mark} | {note} |")
        lines += [
            "",
            f"Deliverable formats: {', '.join(pb.output_formats)}",
            "",
        ]

    lines += [
        "## What the planner sees (classified column kinds)",
        "",
        "| Column | Kind(s) |",
        "|---|---|",
    ]
    kinds_by_column = classify_columns(profile_findings)
    for name in sorted(kinds_by_column):
        kinds = ", ".join(k.value for k in kinds_by_column[name])
        lines.append(f"| {name} | {kinds or '(none)'} |")

    lines += [
        "",
        "## Verdict",
        "",
        (
            f"{len(qualified)} of {len(library)} playbook(s) qualify on "
            f"this dataset: {', '.join(sorted(qualified))}."
            if qualified
            else
            f"0 of {len(library)} playbooks qualify on this dataset. The "
            f"FAIL rows above state exactly what is missing - fix the "
            f"data, or write a playbook whose requirements match it."
        ),
        "",
        "State a goal and run the planner to select among the qualifying "
        "playbooks; a failed check above cannot be overridden by goal "
        "wording or by the LLM.",
        "",
    ]
    return "\n".join(lines)
