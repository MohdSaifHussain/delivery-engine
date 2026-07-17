"""delivery_engine.generator - the deterministic playbook compiler.

Step 19. Playbooks are the engine's governing documents; until now,
writing one meant hand-editing TOML against the spec. The generator
compiles a DRAFT playbook for the user's dataset and goal from the same
two authorities the engine already trusts: the AnalystKit profile (what
the data IS) and the user's stated requirements (what the analysis
MUST do). Deterministic template assembly - no LLM anywhere in the
path; same profile + same answers -> the same playbook, byte for byte.

Constitutional posture:

- THE OUTPUT IS A DRAFT. A pipeline must never approve its own rules
  of engagement. Generated playbooks are written to
  playbooks/generated/ with a DRAFT header, and the runner refuses to
  execute them until a human states, by name, that they reviewed the
  playbook - the step-9 rules_draft pattern (draft -> human approval
  -> execution) applied to the constitution itself.
- GENERATED PLAYBOOKS NEVER ENTER THE ARCHETYPE LOTTERY. The planner
  and the compatibility report glob playbooks/*.toml non-recursively;
  playbooks/generated/ is invisible to goal matching by construction
  and must be selected explicitly by the runner.
- THE CONSTITUTION IS THE COMPILER'S TYPE-CHECKER. Every generated
  file is immediately re-loaded through load_playbook (rules V1-V15);
  a draft the constitution rejects is deleted and reported, never left
  on disk half-valid.
- FEASIBILITY GATES THE MENU. Stage kinds are offered only when the
  profiled data can support them (a stats stage without a binary
  target would fail at run time; the generator refuses to write a
  playbook it knows cannot run).
- RULES ARE EVIDENCE-TYPED. Drafted validation rules carry values in
  their native types (numerics as numbers, booleans as booleans) -
  the AnalystKit v2.0.2 per-dtype comparison contract, honored at the
  source.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

from delivery_engine.planner import ColumnKind, classify_columns
from delivery_engine.playbook import PlaybookError, load_playbook

__all__ = ["GeneratedPlaybook", "GeneratorError", "compile_playbook"]

GENERATED_DIR_NAME: Final[str] = "generated"
MAX_ALLOWED_VALUES: Final[int] = 20   # low-cardinality cutoff for rules
NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{2,40}$")

# The stage menu: each entry states what the data must provide. The
# generator offers only what the profile proves feasible.
STAGE_MENU: Final[dict[str, str]] = {
    "math": "descriptive shape (skewness, outliers, entropy, temporal)",
    "stats": "statistical inference (requires a binary target column)",
    "model": "fixed-seed baseline model (requires a binary target)",
}


class GeneratorError(Exception):
    """A generation problem, stated cleanly: what, why, what to do."""


class GeneratedPlaybook:
    """The result: paths plus the record of what was decided and why."""

    def __init__(self, playbook_path: Path, rules_path: Path,
                 decisions: dict[str, Any]) -> None:
        self.playbook_path = playbook_path
        self.rules_path = rules_path
        self.decisions = decisions


def _feasible_stages(kinds: dict[str, tuple[ColumnKind, ...]]) -> dict[str, bool]:
    has_binary = any(ColumnKind.BINARY_TARGET in ks for ks in kinds.values())
    return {
        "math": True,
        "stats": has_binary,
        "model": has_binary,
    }


def _draft_rules(
    source: str,
    profile_findings: dict[str, Any],
    kinds: dict[str, tuple[ColumnKind, ...]],
) -> list[dict[str, Any]]:
    """Deterministic rule drafting from the profile plus observed
    values. Only claims the evidence supports: uniqueness and
    non-nullness for the first id column, allowed-sets for
    low-cardinality columns with their observed values in native
    types. No ranges are invented - a minimum the data happens to
    satisfy today is an assumption, not a requirement, and assumptions
    belong to the human."""
    rules: list[dict[str, Any]] = []
    id_cols = sorted(
        c for c, ks in kinds.items() if ColumnKind.ID_COLUMN in ks
    )
    if id_cols:
        rules.append({"column": id_cols[0], "rule": "unique"})
        rules.append({"column": id_cols[0], "rule": "not_null"})

    # Step 20: values come from the SINGLE READER, not a second
    # read_csv here - drafting rules against a different parser than
    # the one that will validate them is exactly the divergence this
    # step exists to end. This also makes drafting work for Parquet,
    # .xlsx and SQLite sources for free.
    from delivery_engine.sources import load_dataframe

    df = load_dataframe(source)
    try:
        for col in profile_findings.get("columns", []):
            name = col.get("name")
            distinct = int(col.get("distinct", 0))
            if not name or name in id_cols[:1] or name not in df.columns:
                continue
            if 0 < distinct <= MAX_ALLOWED_VALUES:
                series = df[name].dropna()
                values = sorted(set(series.tolist()), key=str)
                if values:
                    rules.append({
                        "column": name,
                        "rule": "allowed",
                        "values": [
                            v.item() if hasattr(v, "item") else v
                            for v in values
                        ],
                    })
    finally:
        del df
    return rules


def _sanitize(text: str) -> str:
    """Goal text enters a TOML string: newlines become spaces, double
    quotes become single quotes, backslashes are dropped. The user's
    words survive; the file's validity does too (step-19 hunt, L1)."""
    return (text.replace("\\", "").replace('"', "'")
            .replace("\n", " ").replace("\r", " ").strip())


def _emit_toml(
    name: str,
    goal: str,
    stages: list[str],
    kinds: dict[str, tuple[ColumnKind, ...]],
    min_rows: int,
    alpha: float | None,
) -> str:
    """Deterministic TOML assembly. The header marks the file a DRAFT;
    the body is exactly the schema the constitution enforces."""
    has_id = any(ColumnKind.ID_COLUMN in ks for ks in kinds.values())
    required = ['"binary_target"'] if ("stats" in stages
                                       or "model" in stages) else []
    if has_id:
        required.append('"id_column"')

    lines: list[str] = [
        f"# {name} — GENERATED DRAFT (delivery_engine.generator)",
        "# A pipeline must never approve its own rules of engagement:",
        "# review every stage and gate below, then run it via",
        "# run_project.py with --playbook-approved-by <your name>.",
        "# Compiled deterministically from the dataset profile and the",
        "# stated requirements; validated against PLAYBOOK_SPEC rules",
        "# V1-V15 before being written.",
        "",
        "schema_version = 1",
        "",
        "[playbook]",
        f'name = "{name}"',
        'version = "0.1.0-draft"',
        f'description = "Generated: {_sanitize(goal)[:160]}"',
        "",
        "[requirements]",
        f"min_rows = {min_rows}",
    ]
    if required:
        lines.append(f"required_kinds = [{', '.join(required)}]")
    # Step 20: generated playbooks accept every format the single
    # reader supports - the draft should not be narrower than the
    # engine it runs on.
    lines += ['source_types = ["csv", "parquet", "excel", "sqlite"]', ""]

    if alpha is not None and "stats" in stages:
        lines += ["[stats]", f"alpha = {alpha}", ""]

    lines += [
        "[[stages]]",
        'id = "dq_profile"',
        'kind = "kit"',
        'tool = "analystkit_profile"',
        'gate = "must_pass"',
        "",
        "[[stages]]",
        'id = "dq_validate"',
        'kind = "kit"',
        'tool = "analystkit_validate"',
        'gate = "must_pass"',
        'needs = ["dq_profile"]',
        "",
        "[[stages]]",
        'id = "plan_approval"',
        'kind = "human_gate"',
        'needs = ["dq_profile", "dq_validate"]',
        "",
    ]
    prior = ["dq_profile", "dq_validate", "plan_approval"]
    if "math" in stages:
        lines += [
            "[[stages]]",
            'id = "math"',
            'kind = "math"',
            'math_checks = "all"',
            'gate = "must_pass"',
            f"needs = {json.dumps(prior)}",
            "",
        ]
        prior = [*prior, "math"]
    if "stats" in stages:
        lines += [
            "[[stages]]",
            'id = "stats"',
            'kind = "stats"',
            'stat_test = "full_inference"',
            'gate = "must_pass"',
            f"needs = {json.dumps(prior)}",
            "",
        ]
        prior = [*prior, "stats"]
    if "model" in stages:
        lines += [
            "[[stages]]",
            'id = "baseline"',
            'kind = "model"',
            'gate = "must_pass"',
            f"needs = {json.dumps(prior)}",
            "",
        ]
        prior = [*prior, "baseline"]

    last_analysis = prior[-1]
    lines += [
        "[[stages]]",
        'id = "report"',
        'kind = "ai"',
        'slot = "narrative_report"',
        'numbers_from = "findings_store"',
        "human_approval = false",
        "feeds_deterministic = false",
        f'needs = ["{last_analysis}"]',
        "",
        "[[stages]]",
        'id = "readme"',
        'kind = "ai"',
        'slot = "readme"',
        'numbers_from = "findings_store"',
        "human_approval = false",
        "feeds_deterministic = false",
        'needs = ["report"]',
        "",
        "[[stages]]",
        'id = "package"',
        'kind = "package"',
        'needs = ["report", "readme"]',
        "",
        "[deliverables]",
        'artifacts = ["narrative_report", "readme", "delivery_package", '
        '"audit_log", "manifest"]',
        "",
    ]
    return "\n".join(lines)


def compile_playbook(
    source: str,
    goal: str,
    name: str,
    playbook_dir: Path,
    profile_findings: dict[str, Any],
    include_stages: list[str],
    min_rows: int = 100,
    alpha: float = 0.05,
) -> GeneratedPlaybook:
    """Compiles, validates, and writes a DRAFT playbook plus its
    evidence-drafted rules. Raises GeneratorError on any refusal;
    never leaves a half-valid file on disk."""
    if not NAME_RE.match(name):
        raise GeneratorError(
            f"Playbook name '{name}' must be lowercase letters, digits, "
            f"and underscores, starting with a letter (3-41 chars) - it "
            f"becomes a filename and an identifier."
        )
    unknown = sorted(set(include_stages) - set(STAGE_MENU))
    if unknown:
        raise GeneratorError(
            f"Unknown stage selection(s) {unknown}. "
            f"Valid: {sorted(STAGE_MENU)}."
        )
    kinds = classify_columns(profile_findings)
    feasible = _feasible_stages(kinds)
    for st in include_stages:
        if not feasible[st]:
            raise GeneratorError(
                f"Stage '{st}' requires a binary target column and the "
                f"profile found none - the generator refuses to write a "
                f"playbook it knows cannot run. Available for this "
                f"dataset: "
                f"{sorted(k for k, ok in feasible.items() if ok)}."
            )

    curated = {p.stem for p in playbook_dir.glob("*.toml")}
    if name in curated:
        raise GeneratorError(
            f"'{name}' is the name of a curated playbook in "
            f"{playbook_dir}. The runner resolves curated names first, "
            f"so a generated draft with this name would be silently "
            f"SHADOWED - you would review one playbook and run another. "
            f"Choose a distinct name. (step-19 hunt, L4)"
        )

    out_dir = playbook_dir / GENERATED_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    pb_path = out_dir / f"{name}.toml"
    rules_path = out_dir / f"{name}.rules.json"
    if pb_path.exists():
        raise GeneratorError(
            f"{pb_path} already exists. Generated drafts are never "
            f"silently overwritten - delete it deliberately or choose "
            f"another name."
        )

    toml_text = _emit_toml(name, goal, include_stages, kinds, min_rows,
                           alpha if "stats" in include_stages else None)
    pb_path.write_text(toml_text, encoding="utf-8")

    # The constitution as the compiler's type-checker.
    try:
        load_playbook(pb_path)
    except PlaybookError as exc:
        pb_path.unlink(missing_ok=True)
        raise GeneratorError(
            f"The generated playbook violated the constitution and was "
            f"deleted: {exc}"
        ) from exc

    rules = _draft_rules(source, profile_findings, kinds)
    rules_path.write_text(
        json.dumps(rules, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )

    decisions = {
        "name": name,
        "goal": goal,
        "stages_included": list(include_stages),
        "stages_feasible": dict(sorted(feasible.items())),
        "rules_drafted": len(rules),
        "status": (
            "DRAFT - requires human review and "
            "--playbook-approved-by at run time"
        ),
    }
    return GeneratedPlaybook(pb_path, rules_path, decisions)
