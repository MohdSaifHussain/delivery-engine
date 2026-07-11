# STEP 6 DECISIONS — opskit-mcp

**Date:** 11 July 2026 · **Scope:** OpsKit v4.1 as the second MCP server,
plus the charter amendment to v0.2. Engine-stage wiring deliberately out of
scope (never two half-built stages at once); it is the step 7 candidate.

## 1. Primary sources verified at build time

- **MCP Python SDK:** the official SDK's own guidance states v1.x is the
  only stable release line and recommends `mcp>=1.27,<2` pinning while v2
  is pre-release. Built and pinned accordingly (`mcp 1.28.1` at build time,
  `FastMCP` from `mcp.server.fastmcp`).
- **MCP stdio transport:** the protocol owns stdout; servers must not write
  non-protocol bytes there; logging belongs on stderr. This is the official
  basis for the stdout-isolation design, and the SDK's own request logging
  was observed landing on stderr in the live test.

## 2. Approved design decisions, as built

1. **Stdout isolation by capture-as-data.** Every OpsKit call runs under
   `redirect_stdout`; the captured assumption lines return in the payload
   as `assumptions`. What OpsKit inferred (time column, categories,
   numerics) is audit-relevant fact, available for future TOCTOU
   comparison against a plan.
2. **Drill exposed as a standalone tool** returning structured levels
   (column, value, current, previous, contribution), with the Simpson's
   refusal made explicit: `refused: true` plus the written rationale,
   never a silent empty list.
3. **Envelope:** `opskit.envelope/v1`, canonical JSON (sorted keys, minimal
   separators, UTF-8), SHA-256 over the payload only; the IST timestamp
   lives outside the hash so re-performance reproduces it.
4. **Explicit-only config.** No ambient `./opskit.toml` pickup (a server
   inheriting config from its start directory is an ambient-authority
   hazard). Supplied config files are hashed; resolved thresholds recorded
   in every payload. A supplied path that does not exist errors rather
   than silently falling back.
5. **No Excel report from the server.** Findings JSON is the contract;
   artifacts are the engine's job.

## 3. Loophole hunt results (two found, both fixed with regression tests)

1. **Hash-after-execution.** The source hash was computed after the run;
   a mid-run swap would have been recorded as if it were the input. Fixed:
   the seal is taken before the engine opens the file, in both
   `run_playbook_payload` and `drill_payload`. The regression test also
   surfaced a bonus defense: a schema-changing swap crashes DuckDB's lazy
   view outright.
2. **Silent bogus metric.** A playbook with no volume step never validated
   a supplied metric, so the audit record could claim `metric=sparkle:x`
   produced the findings. Fixed: eager `resolve_metric` whenever a metric
   is supplied, regardless of playbook composition.

One non-fix worth recording: the custom-playbook test fixture initially
violated OpsKit's declared step dependencies and the engine refused it at
load. The fixture was corrected; the engine's contract enforcement worked
exactly as designed.

## 4. Vendoring decision

OpsKit v4.1 is a deliberate single-file distribution, so opskit-mcp vendors
`opskit4.py` verbatim into `_vendor/` with its SHA-256 recorded as a
constant and a test that recomputes the hash from disk (tamper evidence).
The wrapper never edits the vendored file; integration-discovered bugs go
upstream, per the AnalystKit BOOLEAN-sniffing precedent.

## 5. Documented boundaries (honest, not faked)

- OpsKit findings carry numbers inside prose; the envelope hashes findings
  whole. Verbatim injection of finding text satisfies the injected-numbers
  rule; independent injection of numbers inside prose awaits a future
  OpsKit Finding-schema version, upstream.
- Upstream `time_coverage` phrases record age relative to the run date, so
  payload hashes reproduce exactly within a day and for all
  date-independent findings.

## 6. Final gates

29/29 tests (planted-answer principle throughout, including two loophole
regression tests and two stdout-isolation tests), ruff clean, mypy strict
zero errors, plus a live end-to-end protocol test using the official MCP
client over real stdio: initialize, list_tools (4 tools), run_playbook
(gate=stop on the planted surge), drill (payments at level 1), and a clean
`isError` surface for an unknown playbook.
