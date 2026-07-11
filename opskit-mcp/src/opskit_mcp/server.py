"""opskit-mcp server: MCP wiring only. Zero logic lives here.

Each tool delegates to a pure function in ``service.py`` and wraps the
result in the hashed envelope. Exceptions of type ``OpsKitError`` carry
readable messages; FastMCP surfaces them to the client as tool errors —
a user mistake never earns a raw traceback.

Transport is stdio per the MCP specification: the protocol owns stdout,
and all OpsKit prints are captured inside the service layer.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from opskit_mcp import service
from opskit_mcp.envelope import wrap

mcp = FastMCP("opskit-mcp")


@mcp.tool()
def opskit_list_playbooks(config_path: str | None = None) -> dict[str, Any]:
    """List available OpsKit playbooks (builtin plus any composed in the
    supplied opskit.toml). Returns a hashed envelope; each playbook entry
    carries its key, title, description, step sequence, and origin."""
    return wrap("opskit_list_playbooks", service.list_playbooks_payload(config_path))


@mcp.tool()
def opskit_explain_playbook(
    playbook: str, config_path: str | None = None
) -> dict[str, Any]:
    """Explain one playbook: every step's question, rationale, and declared
    dependencies. Returns a hashed envelope."""
    return wrap(
        "opskit_explain_playbook",
        service.explain_playbook_payload(playbook, config_path),
    )


@mcp.tool()
def opskit_run_playbook(
    playbook: str,
    source: str,
    table: str | None = None,
    metric: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    """Run an OpsKit playbook over a CSV / Excel / SQLite / Parquet source.

    Returns a hashed envelope whose payload carries the schema-versioned
    findings, the captured role assumptions, the source file's SHA-256,
    the resolved configuration, and a gate verdict: 'stop' if any finding
    is CRITICAL, else 'pass'. Deterministic: same source, same config,
    same payload_sha256."""
    return wrap(
        "opskit_run_playbook",
        service.run_playbook_payload(playbook, source, table, metric, config_path),
    )


@mcp.tool()
def opskit_drill(
    source: str,
    table: str | None = None,
    metric: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    """Recursive contribution analysis on the window-over-window delta,
    returned as structured data: one record per conditioning level with
    column, value, current, previous, and contribution share.

    Additive metrics only (count, sum:<col>). For avg:<col> the payload is
    an explicit refusal record citing the Simpson's-paradox rationale —
    attribution of non-additive metrics is refused, never fabricated."""
    return wrap(
        "opskit_drill",
        service.drill_payload(source, table, metric, config_path),
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
