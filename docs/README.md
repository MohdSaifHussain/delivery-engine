# Design archive

## The founding architecture diagram (v0.1)

![Founding architecture diagram of the Delivery Engine. The pipeline flows in four stages. Stage one, User Input and the Playbook Library, feeds the Planner. Stage two, the Planner, does 80 percent deterministic classification and 20 percent LLM work for ambiguity only, then stops at Human Gate 1 for plan approval before execution. Stage three, the Execution Engine, runs stage by stage under a stage contract: deterministic quality gates from AnalystKit and OpsKit feed a hash-verified Findings Store; bounded AI agent slots write prose and structure only; the injected-numbers rule forbids AI from computing any figure; Human Gate 2 approves AI-authored rules before they feed the deterministic layer; and an append-only audit log records every step. Stage four, the Delivery Package, assembles the notebook, report, PowerPoint, data-quality workpaper, README, audit log, and a manifest that is a hash tree of the whole package. The closing principle: a reviewer who was never in the room can re-perform any stage from the package alone and get the same hashes.](delivery-engine-architecture.png)

This is the **founding architecture diagram**, drawn at the project's
first stage (v0.1). It is preserved here as the project's original
design artifact.

The **current** pipeline is the rendered flowchart in the
[project overview (README.md)](../README.md#the-architecture); that
flowchart is the canonical, up-to-date architecture. This image is kept
as history — the shape the engine was born with, before the stats,
math, and analyst-error guardrail stages were added.

Per the [project charter (PROJECT_CHARTER.md)](../PROJECT_CHARTER.md),
this diagram and the charter together form the project's original
context package.
