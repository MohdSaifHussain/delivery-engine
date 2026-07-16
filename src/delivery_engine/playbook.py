"""delivery_engine.playbook — playbook loading and constitutional validation.

The charter's non-negotiable principles (PROJECT_CHARTER.md section 4) are
enforced HERE, at load time, as validation rules V1-V9 (PLAYBOOK_SPEC.md).
A playbook that violates the constitution cannot load. This is deliberate:
the engine never has to defend against an unconstitutional playbook at
runtime, because one cannot exist in memory.

Parser: Python stdlib tomllib (docs.python.org) — TOML 1.0.0. Zero new
dependencies. Errors are PlaybookError with teaching-grade messages: what
is wrong, where, and what the valid options are.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

__all__ = [
    "AiSlot",
    "GateMode",
    "Playbook",
    "PlaybookError",
    "Requirements",
    "Stage",
    "StageKind",
    "load_playbook",
]

SUPPORTED_SCHEMA_VERSIONS: Final[frozenset[int]] = frozenset({1})

MANDATORY_DELIVERABLES: Final[frozenset[str]] = frozenset({"audit_log", "manifest"})

KNOWN_KIT_TOOLS: Final[frozenset[str]] = frozenset({
    "analystkit_profile",
    "analystkit_validate",
    "analystkit_dedupe",
    "analystkit_reconcile",
    "opskit_run_playbook",
})

# V14: stats stages must declare WHICH sourced inference suite to run.
# The engine never improvises a statistical method; each key maps to a
# fixed procedure traced to primary sources in delivery_engine.stats.
KNOWN_STAT_TESTS: Final[frozenset[str]] = frozenset({
    "proportion_ci",
    "chi2_independence",
    "mann_whitney",
    "full_inference",
})

# V15: math stages must declare WHICH descriptive check suite to run.
# Each key maps to a fixed, sourced procedure in delivery_engine.mathkit;
# the engine never improvises a method, and every threshold the methods
# use is a fixed constant disclosed inside the findings.
KNOWN_MATH_CHECKS: Final[frozenset[str]] = frozenset({
    "numeric_shape",
    "outliers",
    "distribution_fit",
    "categorical_entropy",
    "temporal",
    "all",
})

# V11: opskit stages must name which OpsKit playbook to run. OpsKit
# playbook keys are lowercase with hyphens (e.g. "weekly-review"),
# distinct from V10's snake_case engine identifiers.
OPSKIT_PLAYBOOK_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

KNOWN_REQUIRED_KINDS: Final[frozenset[str]] = frozenset({
    "binary_target",
    "id_column",
    "timestamp_column",
    "numeric_column",
    "categorical_column",
})

KNOWN_SOURCE_TYPES: Final[frozenset[str]] = frozenset({
    "csv", "excel", "sqlite", "postgres", "mysql",
})

# V10: identifiers are snake_case ASCII. Stage ids and playbook names become
# audit-log references and artifact filenames downstream; anything else
# (empty strings, emoji, spaces) would poison those layers silently.
IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class PlaybookError(Exception):
    """A playbook problem, stated cleanly: what, where, valid options."""


class StageKind(StrEnum):
    KIT = "kit"
    AI = "ai"
    MODEL = "model"
    STATS = "stats"
    MATH = "math"
    HUMAN_GATE = "human_gate"
    PACKAGE = "package"


class GateMode(StrEnum):
    MUST_PASS = "must_pass"
    ADVISORY = "advisory"


class AiSlot(StrEnum):
    EDA_NOTEBOOK = "eda_notebook"
    NARRATIVE_REPORT = "narrative_report"
    README = "readme"
    RULES_DRAFT = "rules_draft"
    OPS_REPORT = "ops_report"
    PRESENTATION = "presentation"


@dataclass(frozen=True, slots=True)
class Requirements:
    """What the dataset must satisfy, checkable from an AnalystKit profile."""

    min_rows: int = 1
    required_kinds: tuple[str, ...] = ()
    source_types: tuple[str, ...] = tuple(sorted(KNOWN_SOURCE_TYPES))


@dataclass(frozen=True, slots=True)
class Stage:
    """One executable stage. Fields beyond (id, kind, needs) are kind-specific."""

    stage_id: str
    kind: StageKind
    needs: tuple[str, ...] = ()
    # kit
    tool: str | None = None
    gate: GateMode | None = None
    ops_playbook: str | None = None    # opskit_run_playbook stages only (V11)
    # stats
    stat_test: str | None = None       # stats stages only (V14)
    # math
    math_checks: str | None = None     # math stages only (V15)
    # ai
    slot: AiSlot | None = None
    numbers_from: str | None = None
    human_approval: bool = False
    feeds_deterministic: bool = False


@dataclass(frozen=True, slots=True)
class Playbook:
    """A validated, constitutional playbook. If you hold one, it is legal."""

    name: str
    version: str
    description: str
    schema_version: int
    requirements: Requirements
    stages: tuple[Stage, ...]
    artifacts: tuple[str, ...]
    output_formats: tuple[str, ...]
    source_path: Path
    alpha: float = 0.05  # V14: pre-registered significance level ([stats])

    def stage_ids(self) -> tuple[str, ...]:
        return tuple(s.stage_id for s in self.stages)


# ── strict-key helpers (V6: unknown keys are rejected everywhere) ────────────


def _only_keys(table: dict[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = set(table) - allowed
    if unknown:
        raise PlaybookError(
            f"{where}: unknown key(s) {sorted(unknown)}. "
            f"Allowed keys: {sorted(allowed)}. "
            f"(V6: unknown keys are rejected — this catches typos before they "
            f"become silent misconfiguration.)"
        )


def _require(table: dict[str, Any], key: str, typ: type, where: str) -> Any:
    if key not in table:
        raise PlaybookError(f"{where}: missing required key '{key}'.")
    value = table[key]
    if not isinstance(value, typ):
        raise PlaybookError(
            f"{where}: key '{key}' must be {typ.__name__}, "
            f"got {type(value).__name__}."
        )
    return value


def _str_list(value: Any, where: str, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PlaybookError(f"{where}: '{key}' must be a list of strings.")
    return tuple(value)


# ── section parsers ──────────────────────────────────────────────────────────


def _parse_requirements(raw: dict[str, Any]) -> Requirements:
    where = "[requirements]"
    _only_keys(raw, frozenset({"min_rows", "required_kinds", "source_types"}), where)

    min_rows = raw.get("min_rows", 1)
    if not isinstance(min_rows, int) or isinstance(min_rows, bool) or min_rows < 1:
        raise PlaybookError(f"{where}: min_rows must be an integer >= 1.")

    required_kinds = _str_list(raw.get("required_kinds", []), where, "required_kinds")
    bad = set(required_kinds) - KNOWN_REQUIRED_KINDS
    if bad:
        raise PlaybookError(
            f"{where}: unknown required_kinds {sorted(bad)}. "
            f"Valid kinds: {sorted(KNOWN_REQUIRED_KINDS)}."
        )

    source_types = _str_list(
        raw.get("source_types", sorted(KNOWN_SOURCE_TYPES)), where, "source_types"
    )
    bad = set(source_types) - KNOWN_SOURCE_TYPES
    if bad:
        raise PlaybookError(
            f"{where}: unknown source_types {sorted(bad)}. "
            f"Valid types: {sorted(KNOWN_SOURCE_TYPES)}."
        )

    return Requirements(
        min_rows=min_rows,
        required_kinds=required_kinds,
        source_types=source_types,
    )


_STAGE_KEYS_COMMON: Final[frozenset[str]] = frozenset({"id", "kind", "needs"})
_STAGE_KEYS: Final[dict[StageKind, frozenset[str]]] = {
    StageKind.KIT: _STAGE_KEYS_COMMON | {"tool", "gate", "ops_playbook"},
    StageKind.AI: _STAGE_KEYS_COMMON
    | {"slot", "numbers_from", "human_approval", "feeds_deterministic"},
    StageKind.MODEL: _STAGE_KEYS_COMMON | {"gate"},
    StageKind.STATS: _STAGE_KEYS_COMMON | {"gate", "stat_test"},
    StageKind.MATH: _STAGE_KEYS_COMMON | {"gate", "math_checks"},
    StageKind.HUMAN_GATE: _STAGE_KEYS_COMMON,
    StageKind.PACKAGE: _STAGE_KEYS_COMMON,
}


def _parse_stage(raw: dict[str, Any], index: int) -> Stage:
    where = f"[[stages]] #{index + 1}"
    stage_id = _require(raw, "id", str, where)
    if not IDENTIFIER_RE.match(stage_id):
        raise PlaybookError(
            f"{where}: id '{stage_id}' is invalid. Stage ids must be "
            f"snake_case ASCII: start with a letter, then letters, digits, "
            f"or underscores, max 64 chars. Ids become audit-log references "
            f"and artifact filenames. (V10)"
        )
    where = f"[[stages]] '{stage_id}'"

    kind_raw = _require(raw, "kind", str, where)
    try:
        kind = StageKind(kind_raw)
    except ValueError:
        raise PlaybookError(
            f"{where}: unknown kind '{kind_raw}'. "
            f"Valid kinds: {sorted(k.value for k in StageKind)}. (V8)"
        ) from None

    _only_keys(raw, _STAGE_KEYS[kind], where)
    needs = _str_list(raw.get("needs", []), where, "needs")

    if kind is StageKind.KIT:
        tool = _require(raw, "tool", str, where)
        if tool not in KNOWN_KIT_TOOLS:
            raise PlaybookError(
                f"{where}: unknown tool '{tool}'. "
                f"Valid tools: {sorted(KNOWN_KIT_TOOLS)}. (V8)"
            )
        gate_raw = _require(raw, "gate", str, where)
        try:
            gate = GateMode(gate_raw)
        except ValueError:
            raise PlaybookError(
                f"{where}: unknown gate '{gate_raw}'. "
                f"Valid gates: {sorted(g.value for g in GateMode)}. (V8)"
            ) from None
        ops_playbook = raw.get("ops_playbook")
        if tool == "opskit_run_playbook":
            if not isinstance(ops_playbook, str) or not ops_playbook:
                raise PlaybookError(
                    f"{where}: tool 'opskit_run_playbook' requires "
                    f"ops_playbook = '<opskit playbook key>' (e.g. "
                    f"'weekly-review'). The engine never guesses which "
                    f"analysis to run. (V11)"
                )
            if not OPSKIT_PLAYBOOK_RE.match(ops_playbook):
                raise PlaybookError(
                    f"{where}: ops_playbook '{ops_playbook}' is invalid. "
                    f"OpsKit playbook keys are lowercase letters, digits, "
                    f"and hyphens, starting with a letter, max 64 chars. (V11)"
                )
        elif ops_playbook is not None:
            raise PlaybookError(
                f"{where}: ops_playbook is only valid on "
                f"tool = 'opskit_run_playbook' stages; tool '{tool}' does "
                f"not accept it. (V11)"
            )
        return Stage(
            stage_id=stage_id, kind=kind, needs=needs, tool=tool, gate=gate,
            ops_playbook=ops_playbook if tool == "opskit_run_playbook" else None,
        )

    if kind is StageKind.AI:
        slot_raw = _require(raw, "slot", str, where)
        try:
            slot = AiSlot(slot_raw)
        except ValueError:
            raise PlaybookError(
                f"{where}: unknown slot '{slot_raw}'. "
                f"Valid slots: {sorted(s.value for s in AiSlot)}. (V8)"
            ) from None
        numbers_from = _require(raw, "numbers_from", str, where)
        if numbers_from != "findings_store":
            raise PlaybookError(
                f"{where}: numbers_from must be 'findings_store' — the only "
                f"accepted value. The AI never computes a number; every figure "
                f"is injected from hashed deterministic findings. (V3, "
                f"charter 4.1: the injected-numbers rule.)"
            )
        human_approval = bool(raw.get("human_approval", False))
        feeds_deterministic = bool(raw.get("feeds_deterministic", False))
        if feeds_deterministic and not human_approval:
            raise PlaybookError(
                f"{where}: feeds_deterministic = true requires "
                f"human_approval = true. AI-authored content feeding the "
                f"deterministic layer is the highest-risk point in the "
                f"architecture and always passes a human gate. (V4, "
                f"charter 4.4: Human Gate 2.)"
            )
        return Stage(
            stage_id=stage_id, kind=kind, needs=needs, slot=slot,
            numbers_from=numbers_from, human_approval=human_approval,
            feeds_deterministic=feeds_deterministic,
        )

    if kind is StageKind.STATS:
        gate_raw = _require(raw, "gate", str, where)
        try:
            gate = GateMode(gate_raw)
        except ValueError:
            raise PlaybookError(
                f"{where}: unknown gate '{gate_raw}'. "
                f"Valid gates: {sorted(g.value for g in GateMode)}. (V8)"
            ) from None
        stat_test = _require(raw, "stat_test", str, where)
        if stat_test not in KNOWN_STAT_TESTS:
            raise PlaybookError(
                f"{where}: unknown stat_test '{stat_test}'. "
                f"Valid tests: {sorted(KNOWN_STAT_TESTS)}. The engine "
                f"never improvises a statistical method - each key maps "
                f"to a fixed, sourced procedure. (V14)"
            )
        if not needs:
            raise PlaybookError(
                f"{where}: stats stages must declare needs - inference "
                f"never runs before at least the deterministic profile "
                f"gate has passed. (V14)"
            )
        return Stage(stage_id=stage_id, kind=kind, needs=needs, gate=gate,
                     stat_test=stat_test)

    if kind is StageKind.MATH:
        gate_raw = _require(raw, "gate", str, where)
        try:
            gate = GateMode(gate_raw)
        except ValueError:
            raise PlaybookError(
                f"{where}: unknown gate '{gate_raw}'. "
                f"Valid gates: {sorted(g.value for g in GateMode)}. (V8)"
            ) from None
        math_checks = _require(raw, "math_checks", str, where)
        if math_checks not in KNOWN_MATH_CHECKS:
            raise PlaybookError(
                f"{where}: unknown math_checks '{math_checks}'. "
                f"Valid checks: {sorted(KNOWN_MATH_CHECKS)}. The engine "
                f"never improvises a descriptive method - each key maps "
                f"to a fixed, sourced procedure. (V15)"
            )
        if not needs:
            raise PlaybookError(
                f"{where}: math stages must declare needs - descriptive "
                f"math never runs before at least the deterministic "
                f"profile gate has passed. (V15)"
            )
        return Stage(stage_id=stage_id, kind=kind, needs=needs, gate=gate,
                     math_checks=math_checks)

    if kind is StageKind.MODEL:
        gate_raw = _require(raw, "gate", str, where)
        try:
            gate = GateMode(gate_raw)
        except ValueError:
            raise PlaybookError(
                f"{where}: unknown gate '{gate_raw}'. "
                f"Valid gates: {sorted(g.value for g in GateMode)}. (V8)"
            ) from None
        if not needs:
            raise PlaybookError(
                f"{where}: model stages must declare needs - a baseline "
                f"never trains before at least the deterministic profile "
                f"gate has passed. (V12)"
            )
        return Stage(stage_id=stage_id, kind=kind, needs=needs, gate=gate)

    return Stage(stage_id=stage_id, kind=kind, needs=needs)


# ── the loader ────────────────────────────────────────────────────────────────


def load_playbook(path: Path) -> Playbook:
    """Loads and constitutionally validates a playbook.

    Raises PlaybookError with a teaching-grade message on any violation.
    Returns a frozen Playbook: if you hold one, it is legal.
    """
    if not path.exists():
        raise PlaybookError(f"Playbook not found: {path}")
    try:
        with path.open("rb") as fh:
            doc: dict[str, Any] = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise PlaybookError(
            f"{path.name} is not valid TOML 1.0.0: {exc}"
        ) from None

    _only_keys(
        doc,
        frozenset({"schema_version", "playbook", "requirements", "stages",
                   "deliverables", "stats"}),
        path.name,
    )

    # V5: schema version
    schema_version = _require(doc, "schema_version", int, path.name)
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise PlaybookError(
            f"{path.name}: schema_version {schema_version} is not supported. "
            f"Supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}. (V5)"
        )

    meta = _require(doc, "playbook", dict, path.name)
    _only_keys(meta, frozenset({"name", "version", "description"}), "[playbook]")
    name = _require(meta, "name", str, "[playbook]")
    if not IDENTIFIER_RE.match(name):
        raise PlaybookError(
            f"[playbook]: name '{name}' is invalid. Playbook names must be "
            f"snake_case ASCII, max 64 chars. (V10)"
        )
    version = _require(meta, "version", str, "[playbook]")
    description = _require(meta, "description", str, "[playbook]")

    requirements = _parse_requirements(doc.get("requirements", {}))

    stages_raw = _require(doc, "stages", list, path.name)
    if not stages_raw:
        raise PlaybookError(f"{path.name}: at least one stage is required.")
    stages = tuple(
        _parse_stage(raw, i) for i, raw in enumerate(stages_raw)
    )

    # V1: unique stage ids
    seen: set[str] = set()
    for s in stages:
        if s.stage_id in seen:
            raise PlaybookError(
                f"Duplicate stage id '{s.stage_id}'. Stage ids must be "
                f"unique. (V1)"
            )
        seen.add(s.stage_id)

    # V2: first stage is a deterministic must-pass gate
    first = stages[0]
    if first.kind is not StageKind.KIT or first.gate is not GateMode.MUST_PASS:
        raise PlaybookError(
            f"The first stage ('{first.stage_id}') must be kind = 'kit' with "
            f"gate = 'must_pass'. Deterministic quality gates run before "
            f"anything else — no AI stage may precede them. (V2, "
            f"charter 4.2.)"
        )

    # V9: needs reference only EARLIER stage ids
    earlier: set[str] = set()
    for s in stages:
        unknown = set(s.needs) - earlier
        if unknown:
            raise PlaybookError(
                f"[[stages]] '{s.stage_id}': needs {sorted(unknown)} — each "
                f"entry must be the id of an EARLIER stage. Stages execute "
                f"top to bottom; forward or unknown references are invalid. "
                f"(V9)"
            )
        earlier.add(s.stage_id)

    # V7: mandatory deliverables
    deliverables = _require(doc, "deliverables", dict, path.name)
    _only_keys(deliverables, frozenset({"artifacts", "formats"}),
               "[deliverables]")
    artifacts = _str_list(
        _require(deliverables, "artifacts", list, "[deliverables]"),
        "[deliverables]", "artifacts",
    )
    missing = MANDATORY_DELIVERABLES - set(artifacts)
    if missing:
        raise PlaybookError(
            f"[deliverables]: artifacts must include {sorted(missing)}. "
            f"The audit log and manifest are what make a delivery package "
            f"re-performable evidence rather than just output. (V7, "
            f"charter 4.8.)"
        )

    # V13: optional output formats (Step 13). Backward-compatible — a
    # playbook with no formats key defaults to markdown, so every
    # pre-Step-13 playbook keeps its exact meaning.
    valid_formats = {"markdown", "docx", "pptx", "xlsx", "pdf"}
    if "formats" in deliverables:
        output_formats = tuple(_str_list(
            deliverables["formats"], "[deliverables]", "formats",
        ))
        unknown = set(output_formats) - valid_formats
        if unknown:
            raise PlaybookError(
                f"[deliverables]: unknown output format(s) "
                f"{sorted(unknown)}. Valid: {sorted(valid_formats)}. (V13)"
            )
        if not output_formats:
            raise PlaybookError(
                "[deliverables]: formats, if present, must list at least "
                "one format. Omit the key entirely for markdown-only. (V13)"
            )
    else:
        output_formats = ("markdown",)

    # V14: optional [stats] table - the PRE-REGISTERED significance
    # level. It is part of the playbook the human approves at Human
    # Gate 1, fixed before any p-value exists. Absent = 0.05 (the
    # conventional default), declared here rather than hidden in code
    # paths. Any stats stage uses exactly this alpha.
    alpha = 0.05
    if "stats" in doc:
        stats_tbl = _require(doc, "stats", dict, path.name)
        _only_keys(stats_tbl, frozenset({"alpha"}), "[stats]")
        raw_alpha = stats_tbl.get("alpha", 0.05)
        if isinstance(raw_alpha, bool) or not isinstance(
            raw_alpha, (int, float)
        ):
            raise PlaybookError(
                "[stats]: alpha must be a number strictly between 0 and "
                "1 (e.g. 0.05). (V14)"
            )
        alpha = float(raw_alpha)
        if not (0.0 < alpha < 1.0):
            raise PlaybookError(
                f"[stats]: alpha {alpha} is out of range - it must be "
                f"strictly between 0 and 1. Alpha is pre-registered and "
                f"approved at Human Gate 1, never chosen after seeing "
                f"results. (V14)"
            )
    has_stats_stage = any(s.kind is StageKind.STATS for s in stages)
    if "stats" in doc and not has_stats_stage:
        raise PlaybookError(
            "[stats] is declared but no stage has kind = 'stats'. A "
            "pre-registered alpha with nothing to apply it to is a "
            "silent-typo hazard. (V14)"
        )

    return Playbook(
        name=name,
        version=version,
        description=description,
        schema_version=schema_version,
        requirements=requirements,
        stages=stages,
        artifacts=artifacts,
        output_formats=output_formats,
        source_path=path,
        alpha=alpha,
    )
