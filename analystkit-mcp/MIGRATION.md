# MIGRATION.md — the planned upgrade path to MCP SDK v2

**Written:** 9 July 2026, at build time — before it is needed. That is the point.

## Current state

This server is built on **mcp 1.28.1**, pinned `mcp>=1.27,<2` — exactly as the
official MCP Python SDK README instructs current builders to do while v2 is
in pre-release. v1.x continues to receive critical bug fixes and security
patches.

## What is coming

Per the official SDK repository (fetched 9 July 2026):

- **MCP specification release: 2026-07-28** — protocol moves from stateful,
  bidirectional to **stateless request/response**
- **SDK v2 stable: targeted 2026-07-27**
- Breaking changes include: **FastMCP renamed to MCPServer**, low-level
  handlers become constructor parameters instead of decorators, snake_case
  field names, stricter validation, a Dispatcher pipeline replacing
  ServerSession

## Why migration will be cheap here

By design, **`server.py` is the only file in this package that imports the
MCP SDK.** Tool logic (`tools.py`) and the findings envelope (`findings.py`)
have zero protocol dependency, and the test suite asserts on findings
content, not SDK internals.

Migration surface:
1. `server.py` — rename `FastMCP` → `MCPServer`, adjust decorator/registration
   syntax per the official v2 migration guide, re-check `ToolAnnotations` import path
2. `pyproject.toml` — change pin to `mcp>=2,<3`
3. `tests/test_server.py` — the in-memory session helper import may move;
   protocol tests updated to the v2 client pattern
4. Nothing else.

## Migration procedure (when v2 stable lands)

1. Fetch the official migration guide (linked from the SDK repo releases page)
2. Create branch `mcp-v2`
3. Apply the three-file change above
4. Run all three gates (ruff, mypy --strict, pytest) — 16 tests must pass unchanged
   in their assertions
5. Run the six-probe loophole hunt against the v2 protocol path
6. Do NOT migrate in the first week of v2 stable unless a needed feature or
   security fix requires it — let the first point releases land. v1.x remains
   officially supported with security patches; there is no forced deadline.

## Rollback

`git revert` of the migration commit restores the v1.x build. The pin
`mcp>=1.27,<2` guarantees pip resolves back to the supported v1 line.
