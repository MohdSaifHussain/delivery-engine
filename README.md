# Delivery Engine

[![CI](https://github.com/MohdSaifHussain/delivery-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/MohdSaifHussain/delivery-engine/actions/workflows/ci.yml)

**Project patterns as governed, executable workflows.**
Agent proposes · deterministic tools dispose · human governs · every claim traceable.

An AI-governed data-analysis pipeline where a language model plans and writes
prose, but never computes a number that reaches a deliverable. Every figure in
every artifact is injected from a hash-verified Findings Store; every stage
passes a gate that can actually fail; every decision is recorded in an
append-only audit log. A reviewer who was never in the room can re-perform any
stage from the delivery package alone and get the same hashes. If they can, it
is evidence. If they cannot, it is just output.

## Start here

- **[QUICKSTART.md](QUICKSTART.md)** — install, run an example in 60
  seconds, run it on your data, write your own playbook, choose your AI
  level. For engineers and non-engineers alike.
- **[examples/](examples/)** — three complete end-to-end runs with real
  committed output: transaction monitoring (compliance), churn analysis
  (business analytics), audit data quality (internal audit).

## The architecture

```
User goal + dataset
        │
        ▼
   PLANNER  ── 80% deterministic classification, 20% LLM (ambiguity only)
        │      Human Gate 1: plan approved before execution
        ▼
   EXECUTOR ── stage contract: declared inputs → execution → output hashed
        │      → gate evaluated → audit entry → next stage
        │
        ├─ KIT stages       AnalystKit (profile, validate, dedupe) and
        │                   OpsKit (weekly-review, drill) via MCP servers,
        │                   findings sealed into the store
        │
        ├─ AI stages        EDA notebook, narrative report, ops report,
        │                   README, PPT — prose and structure only, every
        │                   number injected from the store
        │                   Human Gate 2: AI-drafted rules approved by hash
        │
        ├─ MODEL stage      deterministic fixed-seed baseline; metrics hashed;
        │                   no AI-generated code
        │
        └─ PACKAGE          notebook, reports, PPT, DQ workpaper, README,
                            audit log, manifest (hash tree of the package)
```

## The rules that make it evidence

- **Injected numbers.** AI stages never compute, estimate, or write a number.
  Every figure is pulled from the Findings Store and carries its hash. The
  `NumberInjector` enforces this by construction — an artifact containing a
  number not in the store fails verification.
- **Gates that fail.** A deterministic quality gate that cannot stop the
  pipeline is not a gate. Failed AnalystKit checks halt the run.
- **Content-bound human approval.** Human Gate 2 approves the exact SHA-256 of
  the AI-drafted artifact; approving a stale draft is refused.
- **Re-performability.** Same inputs → same hashes, proven by test at every
  stage. Timestamps live outside hashed content.
- **Playbooks, not code.** A new project type is a new TOML playbook, not new
  engine code. Four archetypes ship: `churn_analysis`,
  `data_quality_review`, `transaction_monitoring_review`, and the
  `ops_review` operational pack.

## Repository layout

| Path | What it is |
|---|---|
| `src/delivery_engine/` | The engine: planner, executor, store, artifacts, model, presentation |
| `playbooks/` | TOML archetypes — the project constitution as data |
| `analystkit-mcp/` | AnalystKit exposed as an MCP server, hashed findings envelopes |
| `opskit-mcp/` | OpsKit exposed as an MCP server, hashed findings envelopes |
| `tests/` | Planted-answer test suites, one per build step |
| `PROJECT_CHARTER.md` | The constitutional document — every design decision, dated |
| `PLAYBOOK_SPEC.md` | The playbook schema and its constitutional rules (V1–V12) |
| `STEP*_DECISIONS.md` | Per-step design records and loophole-hunt results |

## Running the gates

The three gates that guard every commit, mirrored exactly in CI:

```bash
# one-time setup
pip install "git+https://github.com/MohdSaifHussain/analystkit.git"
pip install -e ./analystkit-mcp -e ./opskit-mcp -e ".[dev,ml]"
npm install pptxgenjs          # the presentation stage shells out to it

# the gates
ruff check src tests
mypy src/delivery_engine --strict
pytest -q
```

## Standards

Traced to primary sources: the Model Context Protocol specification and
official Python SDK (tool exposure), DAMA-DMBOK (the six data-quality
dimensions behind the gates), scikit-learn's controlling-randomness guidance
(the deterministic baseline), the PyPA src-layout, and DuckDB's official
documentation (the deterministic query layer). Python 3.12+, `mypy --strict`,
`ruff`, and a planted-answer testing discipline throughout.

---

Designed, specified, and governed by **Mohd Saif Hussain**.
Implementation is AI-directed; every architectural and security decision is
human-made and source-verified.
