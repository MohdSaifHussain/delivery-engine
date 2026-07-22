# STEP 7 DECISIONS — OpsKit engine wiring

**Date:** 11 July 2026 · **Scope:** the OpsKit stage kind in the delivery
engine, the ops_review archetype, schema rule V11, charter amendment to
v0.3. Ops narrative artifacts deliberately out of scope (one stage at a
time); they are the step 8 candidate.

## 1. Design decisions, as built

1. **Transport: direct import of the wrapper's tool layer.** The engine
   calls `opskit_mcp.server.opskit_run_playbook` — the exact function an
   MCP client hits — matching the analystkit_mcp precedent
   (`from analystkit_mcp import tools as kit`). Both kits enter the engine
   the same way; the MCP servers remain the standards artifacts and the
   protocol boundary for external hosts. Consistency decided this fork.
2. **One tool wired: `opskit_run_playbook`.** `opskit_drill` stays
   available on the MCP server; its engine wiring belongs with the ops
   artifacts step that would consume its structured output. Wiring it now
   would produce findings nothing renders — a half-built stage.
3. **Seal verification (charter 4.9 in practice).** The opskit-mcp
   envelope carries its own `payload_sha256`; the engine recomputes it
   before the Findings Store accepts anything. The store verifies the
   kit's seal rather than trusting it. The engine also refuses unknown
   envelope schema ids and — because a seal proves integrity, not shape —
   validates payload shape after the seal.
4. **Gate semantics: insight is not unfitness.** OpsKit marks findings
   CRITICAL for two different reasons. A zero-row shape critical is data
   unfitness and fails `must_pass`. A volume surge or sustained shift is
   the deliverable; it is recorded as evidence in the audit rationale and
   the pipeline continues. This deliberately diverges from OpsKit's CLI
   exit codes (exit 2 on any critical — right for CI, wrong for a
   delivery pipeline). Declared, documented in the spec, tested.
5. **Schema V11, a compatible extension of schema v1.**
   `opskit_run_playbook` stages must declare `ops_playbook` (lowercase
   hyphen keys, e.g. `weekly-review`); no other tool accepts the key.
   Every pre-step-7 playbook remains valid and unchanged in meaning, so
   schema_version stays 1; the spec records the evolution rule.
6. **The ops_review archetype is artifact-light by design:** profile gate
   → ops stage → package (findings, audit log, manifest). The existing
   report/readme builders read `dq_profile`/`dq_validate` findings by id
   and would crash on an ops-only run; rendering OpsKit findings is a
   real build with its own loophole hunt, not a footnote.

## 2. Loophole hunt results (two found, both fixed with regression tests)

1. **Unchecked envelope schema.** The engine consumed any envelope
   without reading its `schema` field; a future `opskit.envelope/v2`
   would have been interpreted by guesswork. Fixed: fail closed on
   anything but `opskit.envelope/v1`.
2. **Sealed-but-malformed payload.** The seal check proves the hash, not
   the shape: a correctly re-sealed payload whose `findings` was not a
   list of finding objects crashed after the seal check with a raw
   traceback. Fixed: shape validation after the seal; a clean
   ExecutionStopped either way.

## 3. Gates and their honest boundary

69/69 tests pass in this environment: test_step7 (13, planted-answer:
the surge insight path, the zero-row unfitness path, tampered seal,
future schema, malformed payload, unknown OpsKit playbook, routing,
reproducibility, V11 violations), test_playbook, test_planner. ruff
clean, mypy strict zero errors across the engine including new code.

**Boundary, stated rather than hidden:** test_executor and test_step5
import `analystkit_mcp`, which lives only in the private delivery-engine
repo and was not uploaded; they could not run here. The step 7 tests
exercise the real opskit_mcp end to end and fake only the
analystkit_profile stage (a planted synthetic envelope, the same
technique test_planner uses for the Anthropic SDK). Full-suite
certification is the commit gate on the local repo:

    cd C:\Users\mohds\delivery-engine
    pip install -e opskit-mcp
    pip install -e .
    pytest -q          (expect 108: the prior 95 plus 13 from step 7)
    ruff check src tests
    mypy src/delivery_engine --strict

## 4. Dependency note

The engine now imports `opskit_mcp` at ops-stage runtime, installed as a
sibling package from the repo (`pip install -e opskit-mcp`), the same
arrangement as analystkit-mcp. Neither is on PyPI; pyproject dependencies
stay as they are, and the arrangement is recorded here.
