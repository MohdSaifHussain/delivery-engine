"""analystkit_mcp.server — MCP wiring ONLY. Zero logic lives here.

This is deliberately the only file in the package that imports the MCP
SDK. When SDK v2 stabilizes (targeted 2026-07-27 alongside the
2026-07-28 spec release; FastMCP is renamed MCPServer and decorator
semantics change), migration touches this file and nothing else.
See MIGRATION.md for the planned upgrade path.

Patterns follow the official MCP Python SDK README (v1.x) and the
Anthropic MCP builder guidance:
- server name: {service}_mcp
- tool names: {service}_{action}, snake_case, action-oriented
- Pydantic models for input validation (constraints + descriptions)
- annotations: readOnlyHint=True on every tool — this server mutates nothing
- errors: clean, actionable messages; a user mistake never earns a traceback
- transport: stdio (local-first, per official transport selection guidance)
"""
from __future__ import annotations

import json

from analystkit import AnalystKitError
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from analystkit_mcp import tools

mcp = FastMCP("analystkit_mcp")

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


class SourceInput(BaseModel):
    """A data source AnalystKit can open."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    source: str = Field(
        ...,
        description=(
            "Path to CSV/Excel/SQLite file, or 'postgres://' / 'mysql://' "
            "for a read-only database (credentials via environment "
            "variables: PGHOST, PGUSER, PGPASSWORD, PGDATABASE)."
        ),
        min_length=1,
    )
    table: str | None = Field(
        default=None,
        description="Table name — required for SQLite and database sources.",
    )


class ValidateInput(SourceInput):
    """Source plus declarative validation rules."""

    rules_json: str = Field(
        ...,
        description=(
            "JSON list of rule objects. Supported rules: "
            '{"column": c, "rule": "not_null"} · '
            '{"column": c, "rule": "unique"} · '
            '{"column": c, "rule": "range", "min": 0, "max": 100} · '
            '{"column": c, "rule": "allowed", "values": [...]} · '
            '{"column": c, "rule": "regex", "pattern": "..."} · '
            '{"column": c, "rule": "not_future"}'
        ),
        min_length=2,
    )


class DedupeInput(SourceInput):
    """Source plus optional duplicate-detection key."""

    key: str | None = Field(
        default=None,
        description=(
            "Column to check for duplicate values. Omit for exact "
            "whole-row duplicate detection."
        ),
    )


class ReconcileInput(BaseModel):
    """Two CSV sources to tie out on a shared key."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    left: str = Field(..., description="Path to the left CSV (e.g. transactions).")
    right: str = Field(..., description="Path to the right CSV (e.g. the authoritative reference).")
    key: str = Field(..., description="Shared key column to match on.", min_length=1)
    total_col: str | None = Field(
        default=None,
        description="Numeric column on the left for control-total comparison.",
    )


class ExplainInput(BaseModel):
    """A lesson topic."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    topic: str = Field(
        ...,
        description=(
            "Lesson topic: a DAMA dimension (completeness, uniqueness, "
            "validity, consistency, timeliness, accuracy) or a concept "
            "(reconcile, workpaper)."
        ),
        min_length=1,
    )


def _clean_error(exc: Exception) -> str:
    """Every failure is a clean, actionable message — never a traceback."""
    if isinstance(exc, AnalystKitError):
        return f"Error: {exc}"
    return f"Error: unexpected {type(exc).__name__} — {exc}"


@mcp.tool(name="analystkit_profile", annotations=_READ_ONLY)
def analystkit_profile(params: SourceInput) -> str:
    """DAMA six-dimension data quality profile of a source.

    Returns a canonical findings envelope (JSON) containing per-column
    stats (nulls, distinct, case variants, validity ratio) and the DAMA
    scorecard, with a SHA-256 digest of the findings payload. Accuracy
    is never scored from the dataset alone; use analystkit_reconcile
    against an authoritative source for that.
    """
    try:
        return tools.tool_profile(params.source, params.table)
    except Exception as exc:
        return _clean_error(exc)


@mcp.tool(name="analystkit_validate", annotations=_READ_ONLY)
def analystkit_validate(params: ValidateInput) -> str:
    """Runs declarative validation rules against a source.

    Returns a canonical findings envelope (JSON) with per-rule failure
    counts and sample evidence, SHA-256 hashed. Exceptions are reported,
    never dropped. User-supplied rule values are bound as prepared-
    statement parameters inside AnalystKit — they can never become SQL.
    """
    try:
        rules = json.loads(params.rules_json)
        if not isinstance(rules, list):
            return "Error: rules_json must be a JSON list of rule objects."
        return tools.tool_validate(params.source, params.table, rules)
    except json.JSONDecodeError as exc:
        return f"Error: rules_json is not valid JSON (line {exc.lineno}): {exc.msg}"
    except Exception as exc:
        return _clean_error(exc)


@mcp.tool(name="analystkit_dedupe", annotations=_READ_ONLY)
def analystkit_dedupe(params: DedupeInput) -> str:
    """Detects duplicates: exact whole-row (no key) or key-based.

    Returns a canonical findings envelope (JSON) with duplicate row and
    group counts plus sample groups, SHA-256 hashed.
    """
    try:
        return tools.tool_dedupe(params.source, params.table, params.key)
    except Exception as exc:
        return _clean_error(exc)


@mcp.tool(name="analystkit_reconcile", annotations=_READ_ONLY)
def analystkit_reconcile(params: ReconcileInput) -> str:
    """Ties out two CSV sources: row counts, key matching, control totals.

    Returns a canonical findings envelope (JSON) with matched keys,
    orphans on both sides, and control-total variance, SHA-256 hashed.
    Orphan keys are findings, never garbage — the completeness principle.
    This is the honest path to measuring accuracy: comparison against an
    authoritative source.
    """
    try:
        return tools.tool_reconcile(
            params.left, params.right, params.key, params.total_col
        )
    except Exception as exc:
        return _clean_error(exc)


@mcp.tool(name="analystkit_explain", annotations=_READ_ONLY)
def analystkit_explain(params: ExplainInput) -> str:
    """Built-in lesson on a DAMA dimension or analysis concept.

    Returns plain teaching text with the SQL pattern for the topic.
    Call analystkit_list_lessons to see available topics.
    """
    try:
        return tools.tool_explain(params.topic)
    except Exception as exc:
        return _clean_error(exc)


@mcp.tool(name="analystkit_list_lessons", annotations=_READ_ONLY)
def analystkit_list_lessons() -> str:
    """Lists the lesson topics available from analystkit_explain."""
    return tools.tool_list_lessons()


def main() -> None:
    """Entry point: stdio transport, per official transport selection guidance."""
    mcp.run()


if __name__ == "__main__":
    main()
