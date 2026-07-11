# PROJECT CHARTER — Delivery Engine

**Version:** 0.5
**Date:** 9 July 2026 (v0.1 founding) · amended 11 July 2026 (v0.2, v0.3, v0.4, v0.5)
**Amendment record (v0.5):** Build-sequence step 9 recorded as built: the
transaction_monitoring_review archetype, the first playbook composing the
full system (both kits, Human Gate 2, dual narratives) with ZERO engine
changes - the playbooks-not-code principle (4.5) demonstrated at full
scale. Design lesson recorded: the planner's tie-break is lexical, so
archetype descriptions are part of the routing contract; descriptions
must be lexically differentiated, and routing regression tests pin the
contract.
**Amendment record (v0.4):** Build-sequence step 8 recorded as built: the
ops_report AI slot renders OpsKit findings into a narrative under the
injected-numbers rule. The rule was extended, not weakened: the injector
gained inject_from_findings, which proves a quoted string exists verbatim
inside the stage's hashed findings before registering its numeric tokens -
provenance by construction. Section 8's deferred list updated accordingly.
**Amendment record (v0.3):** Build-sequence step 7 recorded as built:
OpsKit wired into the engine as a kit stage (tool `opskit_run_playbook`,
schema rule V11, archetype ops_review), with envelope seal verification
and declared insight-vs-unfitness gate semantics. Section 8's deferred
list updated: OpsKit engine wiring is done; ops narrative artifacts
(report/readme built from OpsKit findings) are the named next deferral.
**Amendment record (v0.2):** Build-sequence steps 5 and 6 recorded as built.
Section 8's deferred list updated: OpsKit integration has begun via
opskit-mcp; engine-stage wiring is the explicitly remaining deferred piece.
Section 9 updated with the as-built sequence. Section 4.9 added: the
layered-defense observation from the step 5 loophole hunt, recorded as
charter-level evidence that the architecture composes.
**Owner:** Mohd Saif Hussain — designer, specifier, governor
**Status:** Approved architecture, pre-build
**Companion artifact:** delivery-engine-architecture.png (the one-page system diagram)

This document is the constitution of the Delivery Engine project. Any session,
any tool, any collaborator working on this project starts here. Where a future
decision conflicts with this charter, the charter is either consciously amended
(with a version bump and a dated note) or the decision is wrong.

---

## 1. Problem statement

Anyone who has to deliver a data project — analyst, data scientist, consultant,
freelancer, student, internal ops professional — spends the first 60–70% of the
project lifecycle on repeatable scaffolding: understanding the dataset,
validating quality, exploring, documenting, building a baseline, packaging the
deliverables. This work follows recognizable professional patterns, yet is
redone manually from scratch on every project.

Meanwhile, 2026's agentic AI tools chain LLM agents to generate these artifacts
fast — but unverifiably. They fabricate numbers, cannot produce evidence for
their claims, and their output cannot be re-performed. Fast and untrustworthy.

The gap in the market: nobody is building the version where the delivered
project **proves itself** — where every number traces to a deterministic
computation, every AI decision is logged with its rationale, and a reviewer
who was never in the room can re-perform any stage and get the same result.

## 2. The one-line thesis

**Encode professional project patterns as executable, governed workflows:
agent proposes, deterministic tools dispose, human governs, every claim
traceable.**

The Delivery Engine takes a dataset plus a plain-English goal and produces a
complete, professional project package — notebook, report, presentation,
workpaper, README, repo structure — where every artifact meets an evidence
standard, not just a plausibility standard.

## 3. Lineage — what this builds on

This project is the third level of one consistent idea across the owner's
portfolio:

- **AnalystKit** (v2.0, live on GitHub) encoded the data quality pattern:
  DAMA six dimensions, planted-answer testing, workpaper discipline, the
  deterministic-findings → SHA-256 → AI-narrative audit boundary.
- **OpsKit** (v4.1) encoded the operational analysis pattern — and invented
  the mechanism this project scales up: **domain patterns declared as TOML
  playbooks, executed by a small, tested, unchanging engine.**
- **The Delivery Engine** encodes the pattern of patterns: how a professional
  turns a dataset and a goal into a finished deliverable.

Don't automate tasks. Automate the workflow that connects tasks into a
deliverable.

## 4. Non-negotiable architecture principles

These are not preferences. Each is stated with its rationale. Violating any of
them means the build has failed regardless of how well it demos.

### 4.1 The injected-numbers rule
The AI never computes, estimates, or writes a number. Every figure in every
generated artifact is injected from the Findings Store and carries its hash.
AI writes prose, structure, and code — never facts.
*Rationale:* a report where the AI wrote "churn is 23.4%" and nobody verified
it is worse than no report, because it looks professional. This rule must be
architecturally enforced (the artifact templating layer only accepts numbers
from the store), not enforced by prompt instruction.

### 4.2 Deterministic quality gates
AnalystKit and OpsKit run as must-pass gates. A failed gate stops the
pipeline. No AI stage may override, soften, or route around a failed gate.
*Rationale:* a control that cannot fail is not a control.

### 4.3 The Findings Store is the audit boundary
All deterministic outputs land in canonical JSON (sort_keys), SHA-256 hashed.
These are the only numbers any AI stage may consume. Same findings → same
hash → re-performable evidence.
*Rationale:* pattern proven at small scale in AnalystKit v2.0's --ai flag.
This project scales it up; it does not reinvent it.

### 4.4 Two human gates, architecturally placed
- **Human Gate 1:** the Planner's selected playbook and execution plan are
  shown for approval before anything executes.
- **Human Gate 2:** any AI-authored content that would feed back into the
  deterministic layer (generated validation rules, feature definitions, model
  choices) requires explicit human approval before use.
*Rationale:* Gate 2 exists because AI-authored rules feeding the deterministic
layer is the one place the audit boundary could be poisoned. This is the
single highest-risk point in the architecture.

### 4.5 Playbooks, not code
Project archetypes are declared as TOML playbooks. Adding a new project type
means writing a new playbook — never modifying the engine. The engine stays
small, tested, gated; the pattern library grows.
*Rationale:* the OpsKit v4 principle. Also the quiet biggest idea: users can
encode THEIR OWN professional patterns as playbooks. The product is not just
our patterns — it is a format for professionals to encode theirs.

### 4.6 The planner is 80% deterministic, 20% LLM
Project-type classification (tabular? binary target? timestamps? which
archetype's requirements are met?) is decided by rules over the AnalystKit
profile output. The LLM resolves only genuine ambiguity in goal wording, and
its decision plus rationale is logged. The LLM never overrides a failed
requirements check.
*Rationale:* "decide the project type" is a deterministic problem wearing an
AI costume. Rules are cheaper, reliable, and testable.

### 4.7 The stage contract (every stage, no exceptions)
1. Declared inputs (from the playbook)
2. Execution (kit command or bounded AI slot)
3. Output hashed
4. Gate evaluated (pass / stop / human)
5. Audit entry written (append-only, IST-timestamped)
6. Next stage

### 4.8 The success test (the definition of done for the whole system)
A reviewer who was never in the room can re-perform any stage from the
delivery package alone and get the same hashes. If they can, it is evidence.
If they cannot, it is just output.

### 4.9 Layered defense, observed (recorded v0.2)
During the step 5 loophole hunt, a source swapped AFTER Human Gate 2
approval was caught by the step 4 TOCTOU control (fresh profile compared
against the plan's classified kinds) at the first gate. A control built for
one surface covered the next. This is recorded as evidence that the
architecture composes: gates and seals designed independently protect each
other's blind spots. Future stages preserve this property by sealing
declared inputs before execution; the opskit-mcp wrapper applies the same
ordering, taking the source hash before the engine opens the file.

## 5. What this is NOT (anti-scope)

- **Not an assignment-submission machine.** Positioning is: "accelerates
  project creation while exposing every step, every decision, every rationale."
  Students can learn from it; it is not optimized for submitting work without
  understanding it. This is both an ethical position and an adoption
  requirement (institutions increasingly reject opaque AI submissions).
- **Not a replacement for professional judgment.** It automates the first
  60–70% of the lifecycle (setup, understanding, validation, exploration,
  documentation, baseline, packaging). The remaining 30–40% — iterative
  experimentation, domain feature engineering, business judgment — is
  explicitly the human's.
- **Not image / audio / deep-learning territory in v1.** The deterministic
  kits are built for structured/tabular data. That is the lane.
- **Not a pile of chained agents.** Anyone can chain twelve agents; LangChain
  tutorials do it. The differentiator is the evidence standard. If a build
  decision trades evidence for demo-speed, the decision is wrong.

## 6. Standards register — official sources only

Every component is designed against a primary source, fetched and verified at
build time (the AnalystKit v2.0 discipline). No generic blog posts.

| Component | Governing source |
|---|---|
| Tool exposure (kits as agent tools) | Model Context Protocol (MCP) specification — modelcontextprotocol.io |
| Agent orchestration patterns | Anthropic official agent design documentation / docs.claude.com |
| AI API usage | Official Anthropic Python SDK documentation |
| Data quality gates | DAMA-DMBOK six dimensions (as implemented in AnalystKit) |
| Deterministic engine | DuckDB official documentation (identifiers, prepared statements, READ_ONLY attach, secrets warnings) |
| Packaging & layout | PyPA Python Packaging User Guide (src layout, PEP 621) |
| Python stdlib behaviors | docs.python.org only |
| Project lifecycle language | PMBOK (charter, deliverables, gates) — used for vocabulary, not bureaucracy |
| Typing / language standards | Python 3.12+, PEP 695, mypy --strict, ruff |

Rule: if a component's design cannot cite its source, it does not ship.

## 7. Engineering standards (inherited, non-negotiable)

The AnalystKit v2.0 bar applies to every component:
- mypy --strict, zero errors; py.typed marker
- ruff clean (E, F, W, I, N, UP, B, C4, SIM, RUF)
- pytest on the planted-answer principle: fixtures contain known issues,
  tests verify exactly those are found
- Adversarial loophole hunts before any version ships; every fix lands with
  a regression test proving the old failure
- Frozen slots dataclasses, StrEnum, timezone-aware IST, atomic writes,
  no side effects on import, clean AnalystKitError-style errors (a user
  mistake never earns a raw traceback)
- src layout; CLI/dispatch layers contain zero logic
- GitHub Actions CI (ruff + mypy strict + pytest) green from first commit
- Development framing: designed, specified, and governed by Mohd Saif
  Hussain; implementation AI-directed; every architectural and security
  decision human-made and source-verified

## 8. Scope of the thin slice (v0.1) — the first build

One vertical slice, end to end, every gate real:

1. **One archetype:** churn_analysis (most universally understood)
2. **Planner:** deterministic matching over AnalystKit profile + requirements
   check against the playbook; LLM only for goal-wording ambiguity; Human
   Gate 1 approval
3. **Deterministic gates:** AnalystKit profile + validate (must_pass);
   findings → Findings Store (canonical JSON + SHA-256)
4. **One AI stage:** EDA notebook generation under the injected-numbers rule
5. **Documentation stage:** README + short report, narrative from findings
   JSON only
6. **Packaging stage:** professional repo structure + audit log + manifest
   (hash tree of the entire package)

**Explicitly deferred past v0.1:** model training stage, PPT generation,
OpsKit integration, feature-engineering agent, dashboard agent, multiple
archetypes, user-authored playbook validation tooling.

*(v0.2 status of this list: a second archetype and the rules_draft slot with
Human Gate 2 landed in step 5. OpsKit integration began in step 6 with
opskit-mcp, exposing OpsKit v4.1 as the second MCP server with hashed
envelopes, completed its engine wiring in step 7 (the ops_review
archetype), and gained narrative artifacts in step 8 (the ops_report
slot). The OpsKit integration track is complete; opskit_drill engine
wiring remains available as a future enhancement when an artifact
consumes its structured output. Model training, PPT
generation, feature-engineering agent, dashboard agent, and user-authored
playbook validation tooling remain deferred.)*

## 9. Build sequence

1. **MCP wrappers first.** Expose AnalystKit (and later OpsKit) commands as
   MCP servers per the official specification. Small build, standards-based,
   independently useful, and the foundation the engine calls through.
2. **Playbook schema.** The TOML format is the constitution of the runtime
   system — designed with charter-level rigor before the engine exists.
3. **Planner** (deterministic core + logged LLM ambiguity resolution +
   Human Gate 1).
4. **Thin slice** (Section 8) working end to end with the audit trail.
5. **Expansion:** one stage or one playbook at a time, each with its own
   tests and its own loophole hunt. Never two half-built stages at once.

**As built (v0.2):**

| Step | Delivered | Gates at completion |
|---|---|---|
| 1 | analystkit-mcp: AnalystKit tools via MCP, hashed findings envelope | green |
| 2 | Playbook schema: constitutional rules V1-V10, churn archetype | green |
| 3 | Planner: 80/20 deterministic/LLM, Human Gate 1 | green |
| 4 | Executor: stage contract, Findings Store, audit log, first package | green |
| 5 | rules_draft slot with content-bound Human Gate 2 (approval quotes the draft's SHA-256), second archetype; a genuine AnalystKit bug (BOOLEAN sniffing) found by integration, fixed upstream | 95/95 tests, mypy strict, ruff |
| 6 | opskit-mcp: OpsKit v4.1 as the second MCP server; four tools, hashed envelopes, stdout isolation per MCP stdio spec, explicit-only config with hashing, source sealed before execution, structured Simpson's refusal, eager metric validation; two loopholes found and fixed with regression tests; live protocol test against the official MCP client | 29/29 tests, mypy strict, ruff |

| 7 | OpsKit engine wiring: `opskit_run_playbook` kit tool with schema rule V11 (`ops_playbook` key), the ops_review archetype, envelope seal verification (schema check, hash recomputation, post-seal shape validation), declared insight-vs-unfitness gate semantics; two loopholes found and fixed with regression tests | 69/69 runnable tests, mypy strict, ruff; full-suite certification on the private repo |

| 8 | ops_report AI slot: OpsKit findings rendered under the injected-numbers rule via inject_from_findings (verbatim provenance proven before token registration); ops_review archetype to v1.1.0; two loopholes found and fixed with regression tests | 119/119, mypy strict, ruff |

| 9 | transaction_monitoring_review archetype: both kits + Human Gate 2 + dual narratives composed in one playbook, zero engine changes; lexical routing collision found during build, fixed in the archetype description, pinned with regression tests | 127/127, mypy strict, ruff |

Step 10 candidates: the model-training stage (sandboxing question,
section 11) or PPT generation.

Standing archetype-authoring rule (from step 9): a new playbook's
description is a routing surface. Before adding an archetype, check its
description tokens against the library for collisions, and land it with
routing regression tests for its own goal AND the goals of its nearest
lexical neighbors.

## 10. Success criteria for v0.1

- The re-performability test (4.8) passes on the churn slice: a second run
  on the same inputs reproduces the same finding hashes, and the manifest
  verifies.
- Zero numbers in any generated artifact that do not trace to the Findings
  Store (verified by test, not by inspection).
- A failed AnalystKit gate stops the pipeline (verified by planted bad data).
- Human Gates 1 and 2 cannot be bypassed by any input (verified by test).
- All three quality gates green (ruff, mypy strict, pytest) with CI.
- The audit log alone is sufficient to reconstruct what happened and why.

## 11. Open questions (decided later, consciously)

- Engine runtime: single Python package vs. orchestrator framework.
  Bias: own small engine (playbook executor), calling kits via MCP —
  consistent with "the engine stays small."
- Notebook generation format: .ipynb JSON directly vs. jupytext .py.
  Decide against official Jupyter format documentation.
- Where model-training code executes in later versions (sandboxing question).
- Naming. Working title: Delivery Engine. Candidates preserved: AI Project
  Workflow Engine. Decide before first public commit.
- Licensing (MIT default per portfolio precedent; revisit if this becomes
  a product rather than a portfolio piece).

## 12. How to resume this project in any new session

Upload two files: **PROJECT_CHARTER.md** (this document) and
**delivery-engine-architecture.png**. State which build-sequence step is
active. That is the complete context package. Any decision made in a session
that amends this charter gets written back into it with a version bump.

---

*A stage that cannot fail is not a gate. A number without a hash does not
enter a deliverable. A project that cannot be re-performed is just output.*
