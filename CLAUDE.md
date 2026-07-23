# CLAUDE.md — Delivery Engine

This file governs every Claude Code session on this repository.
Read it before touching any code. Where this file conflicts with
a suggestion that seems reasonable, this file wins.

---

## What this project is

A governance-first analytical workflow engine. The core thesis:
**agent proposes, deterministic tools dispose, human governs,
every claim traceable.** Built by Mohd Saif Hussain directing
Claude as AI collaborator across 23 documented build steps.

The constitutional document is `PROJECT_CHARTER.md`. Read it.
The interactive version is `docs/PROJECT_CHARTER.html`.

---

## Non-negotiable rules — violating any of these means the build has failed

### The Injected-Numbers Rule (§ 4.1)
The AI **never** computes, estimates, or writes a number into a
deliverable. Every figure in every generated artifact is injected
from the Findings Store (hashed JSON in `findings/`) and carries
its SHA-256. AI writes prose, structure, and code — **never facts**.

If you are writing a narrative, report, or document stage: pull
numbers from `findings_store`, inject them with `inject_from_findings`.
Never hardcode a figure. Never compute one inline.

### Deterministic Quality Gates (§ 4.2)
AnalystKit and OpsKit run as must-pass gates. A failed gate stops
the pipeline. No AI stage may override, soften, or route around
a failed gate. Never set `gate = "optional"` on a DQ stage.

### The Findings Store is the Audit Boundary (§ 4.3)
All deterministic outputs land in canonical JSON (`json.dumps(...,
sort_keys=True)`), SHA-256 hashed. These are the only numbers
any AI stage may consume. Same findings → same hash → re-performable
evidence. Never change the serialization format.

### Two Human Gates, Architecturally Placed (§ 4.4)
- **Gate 1** — plan approval before anything executes
- **Gate 2** — content-bound approval by SHA-256 before AI-authored
  rules feed back into the deterministic layer

Never remove or bypass a gate. Never auto-approve Gate 2 in
production code (examples may auto-approve for demo purposes only).

### Playbooks, Not Code (§ 4.5)
Adding a new project type = writing a new TOML playbook in
`playbooks/`. Never modify the executor to add an archetype.
The engine stays small, tested, gated.

### The Success Test (§ 4.8)
A reviewer who was never in the room can re-perform any stage
from the delivery package alone and get the same hashes.
If your change breaks this, it does not ship.

---

## Build commands

```bash
# Run the full test suite
python -m pytest -q

# Run with coverage
python -m pytest --cov=delivery_engine -q

# Type checking (must be zero errors)
mypy src/ --strict

# Linting (must be clean)
ruff check src/ tests/

# Format
ruff format src/ tests/

# Run a specific example (from repo root)
python examples/audit_data_quality/run_example.py

# Generate a visual report on a package
python generate_report.py examples/audit_data_quality/output/final

# Build Docker image
docker build -t delivery-engine .

# Run tests in container
docker run --rm delivery-engine
```

**All four must be green before any commit:**
`pytest` + `mypy --strict` + `ruff check` + `ruff format --check`

---

## Architecture

```
src/delivery_engine/
  planner.py      — 80% deterministic project-type classification
  executor.py     — runs stages, enforces gates, manages findings store
  store.py        — canonical JSON + SHA-256 hashing
  baseline.py     — deterministic sklearn model (fixed seeds)
  stats.py        — Wilson CIs, Fisher, Mann-Whitney, BH FDR
  math_stage.py   — distribution fitting, MAD outliers, entropy
  report.py       — deterministic HTML visual report (pure function)
  trend.py        — across-runs trend report (reads run_NNN lineage)
  lineage.py      — sequenced immutable run_NNN folders
  compatibility.py — playbook compatibility report
  sources.py      — single-reader principle: one loading path
  documents/      — docx, pptx, xlsx, pdf generation (Node-backed)

analystkit-mcp/   — DQ profiling, validation, deduplication tools
opskit-mcp/       — operational review tools
playbooks/        — TOML archetypes (never modify the engine to add one)
examples/         — 7 committed verified packages with report.html
```

---

## Code conventions

- Python 3.12+, PEP 695 generics, `mypy --strict` zero errors
- `ruff` for linting and formatting — no exceptions
- Dataclasses with `frozen=True, slots=True` for immutable domain objects
- No mutable global state
- Every new public function gets a test
- Tests use `tmp_path` (pytest fixture) for isolation — never write to the actual `examples/` in tests
- Loophole hunt before every commit: ask "what's the sneakiest way this could produce a wrong result and not fail a test?"

---

## What NOT to do

- Never write a number into a narrative/report — always inject from findings
- Never add `gate = "optional"` to a DQ stage
- Never modify `executor.py` to add business logic for a new archetype
- Never commit without running all four gates (pytest + mypy + ruff check + ruff format)
- Never hardcode a file path — use `pathlib.Path` and relative paths
- Never use `subprocess` to call Python from Python — import directly
- Never change `sort_keys=True` in findings serialization
- Never bypass the Single-Reader Principle in `sources.py`
- Never commit the PaySim CSV (493 MB) or any large dataset to the repo

---

## v1.1 roadmap (current sprint)

These are the planned features for v1.1.0. Work on `release/v1.1` branch.
Each must pass the full gate before merging:

1. **Step 21 math charts** — extend `report.py` and `generate_report.py`
   to visualize math-stage findings (distribution fit, outliers, entropy,
   temporal). Currently math findings live in `findings/math.json` but
   are not charted in `report.html`. The report is a pure function —
   same findings → byte-identical HTML. Maintain that invariant.

2. **Python-docx/pptx migration** — replace Node (pptxgenjs, docx) in
   `src/delivery_engine/documents/` with pure Python (python-docx,
   python-pptx, openpyxl). This drops Node from Docker and simplifies
   the image. **CRITICAL:** must re-prove determinism after migration —
   same inputs → same file bytes. Run the full test suite and confirm
   hashes are stable across runs before merging.

3. **Human-declared-final** — the engine reports a green state as fact;
   a named human declaring a run final is a separate governance act.
   Same pattern as Human Gate 2 (content-bound, SHA-256 referenced).

4. **G2/G3 for model playbooks** — pseudoreplication (G2) and minimum
   detectable effect (G3) guardrails currently skip model-only playbooks.

5. **Timeliness metric** — investigate why timeliness shows 0.0% on
   examples with no date column; "not scored" may be more honest there.

6. **Examples gallery** — `examples/index.html` needs white-background
   redesign (current version uses dark glassmorphism — good but not
   readable enough). Maintain all data, links, and filter functionality.

---

## How to resume in a new session

The context package is `PROJECT_CHARTER.md` + this file.
State which v1.1 item is active. Every decision that amends the
charter gets written back with a version bump.
