# analystkit-mcp

MCP server exposing [AnalystKit](https://github.com/MohdSaifHussain/analystkit) data-quality tools to any MCP-compatible agent — Claude Desktop, Claude Code, or any client speaking the Model Context Protocol.

**Read-only by design. Every finding hash-verified.**

## The six tools

| Tool | What it does |
|---|---|
| `analystkit_profile` | DAMA six-dimension quality scorecard (accuracy never scored — by design) |
| `analystkit_validate` | Declarative validation rules; exceptions reported, never dropped |
| `analystkit_dedupe` | Exact-row or key-based duplicate detection with evidence |
| `analystkit_reconcile` | The tie-out: rows, keys, control totals; orphans are findings |
| `analystkit_explain` | Built-in lessons on all six DAMA dimensions |
| `analystkit_list_lessons` | Lists available lesson topics |

## The findings envelope

Every analysis tool returns canonical JSON with a SHA-256 digest of the findings payload:

```json
{
  "tool": "analystkit_validate",
  "source": "orders.csv",
  "run_at_ist": "2026-07-09T23:41:00+05:30",
  "findings": { "...all computed facts live here..." },
  "sha256": "…digest of findings only — same data, same hash, any day…"
}
```

The timestamp sits **outside** the hash: the same findings always produce the same digest, which is what makes results re-performable evidence rather than just output. The digest algorithm is shared with AnalystKit itself — one algorithm across the ecosystem.

## Design guarantees

- **Read-only, annotated as such.** Every tool declares `readOnlyHint: true`. No tool writes files or mutates data. Database sources inherit AnalystKit's READ_ONLY-by-construction attach.
- **Clean errors, never tracebacks.** A user mistake earns an actionable one-line message.
- **No secret can leak.** Credentials come from environment variables only; error text is redacted against credential values (inherited from AnalystKit, re-verified through the protocol here).
- **Wiring isolated.** `server.py` is the only file importing the MCP SDK — see MIGRATION.md for the planned, three-file upgrade path to SDK v2 (spec 2026-07-28).

## Install & run

```bash
pip install -e .
analystkit-mcp            # runs on stdio transport
```

### Claude Desktop config

```json
{
  "mcpServers": {
    "analystkit": {
      "command": "analystkit-mcp"
    }
  }
}
```

## Standards

mcp pinned `>=1.27,<2` per the official SDK README guidance during the v2 pre-release window. Patterns follow the official MCP Python SDK documentation and Anthropic's MCP builder guidance: `{service}_mcp` naming, Pydantic input models with `extra="forbid"`, typed `ToolAnnotations`, stdio transport for local-first use. Tested through the real protocol via the SDK's in-memory client session — 16 tests on the planted-answer principle, mypy strict, ruff clean.

Part of the **Delivery Engine** project — see PROJECT_CHARTER.md in that repository. This server is build-sequence step 1: the deterministic kits exposed as standard tools, returning the Findings Store envelope the engine will consume.

## License

MIT
