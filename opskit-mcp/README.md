# opskit-mcp

OpsKit v4.1 operational-analysis playbooks exposed as MCP tools, each response
wrapped in a canonical-JSON, SHA-256-hashed findings envelope. Delivery Engine
build-sequence step 6: the analystkit-mcp pattern applied to the second kit.

Same source, same config, same `payload_sha256`. A reviewer who was never in
the room can re-run the tool and verify the hash. That is the entire point.

## Tools

| Tool | What it returns |
|---|---|
| `opskit_list_playbooks` | Builtin plus TOML-composed playbooks, with origin marked |
| `opskit_explain_playbook` | Every step's question, rationale, and declared dependencies |
| `opskit_run_playbook` | Schema-versioned findings, captured assumptions, source seal, gate verdict |
| `opskit_drill` | Recursive contribution analysis as structured levels, or an explicit refusal |

## The envelope

```json
{
  "schema": "opskit.envelope/v1",
  "tool": "opskit_run_playbook",
  "opskit_version": "4.1",
  "vendored_opskit_sha256": "f5370d17...",
  "generated_at": "2026-07-11T18:40:00+05:30",
  "payload": { "...deterministic content only..." },
  "payload_sha256": "..."
}
```

The hash covers only the payload. The timestamp lives outside it, so
re-performance reproduces the hash exactly.

## Design decisions worth knowing

**Stdout isolation.** The MCP stdio transport owns stdout for JSON-RPC.
OpsKit prints its role assumptions to stdout by design; every call here runs
under `redirect_stdout`, and the captured assumption lines are returned as
data in the payload (`assumptions`), because what the engine inferred about
your source is audit-relevant fact. A test asserts the protocol stream gets
zero non-protocol bytes across a full run.

**No ambient config.** OpsKit's CLI picks up `./opskit.toml` if present. A
server inheriting configuration from whatever directory it started in would
make the audit trail unable to say which config produced which findings.
Configuration here is explicit-only: no `config_path` means library defaults;
a supplied path that does not exist is an error, never a silent fallback.
Supplied config files are SHA-256 hashed and the resolved thresholds recorded
in every payload.

**Source sealed before execution.** The source file's hash is taken before
the engine ever opens it (TOCTOU discipline, per the Delivery Engine step 4
precedent). A mid-run swap makes re-performance fail loudly against the seal.

**Structured refusal.** `avg:<col>` drills return an explicit refusal record
with the Simpson's-paradox rationale instead of an empty list, so a
downstream engine can log why there is no attribution rather than guessing.

**Metric validated eagerly.** A supplied metric is validated against the
actual schema even when the chosen playbook contains no volume step, closing
the loophole where the audit record would claim an unvalidated metric
produced the findings.

**Vendored, sealed engine.** `_vendor/opskit4.py` is a verbatim copy of the
published OpsKit v4.1; `VENDORED_OPSKIT_SHA256` is recorded and a test
recomputes it from disk. The wrapper never edits the vendored file; bugs
found by integration are fixed upstream (the AnalystKit BOOLEAN precedent).

## Known boundary, documented rather than faked

OpsKit findings carry numbers inside prose text, not as separate fields. The
envelope hashes each finding whole, so finding text can be injected verbatim
under the injected-numbers rule, but individual numbers inside prose cannot
be independently injected. Restructuring the Finding schema is a future
OpsKit version's job, not a wrapper's. Additionally, the upstream
`time_coverage` step phrases record age relative to the run date, so payload
hashes reproduce exactly within a day and for all date-independent findings.

## Run it

```bash
pip install -e .
opskit-mcp            # stdio transport; register with any MCP host
```

Standards traced to: MCP specification and official Python SDK (`mcp>=1.27,<2`;
the SDK's stable v1 line per its own guidance), DuckDB official documentation,
PyPA src layout, Python 3.12+, mypy strict, ruff.

Gates: 29 tests on the planted-answer principle, ruff clean, mypy strict zero
errors, plus a live protocol test against the official MCP client over real
stdio.

Designed, specified, and governed by Mohd Saif Hussain. Implementation
AI-directed; every architectural and security decision human-made and
source-verified.
