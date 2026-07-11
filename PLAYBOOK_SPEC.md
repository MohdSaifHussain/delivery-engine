# PLAYBOOK_SPEC.md — Delivery Engine Playbook Schema v1

**Status:** Approved (build step 2 of PROJECT_CHARTER.md section 9)
**Format:** TOML 1.0.0 (parseable by Python stdlib `tomllib`, docs.python.org)
**Date:** 10 July 2026

A playbook is a project archetype declared as data. The engine executes
playbooks; it is never modified to support a new project type (charter 4.5).

**The constitution is machine-enforced.** The loader validates every playbook
against the charter's non-negotiable principles. A playbook that violates the
constitution fails to load with a clean, numbered error. The rules:

| Rule | Enforces | Charter |
|---|---|---|
| V1 | Stage ids are unique | 4.7 stage contract |
| V2 | The first stage is a deterministic kit stage with `gate = "must_pass"` | 4.2 gates before anything |
| V3 | Every AI stage declares `numbers_from = "findings_store"` — the only accepted value | 4.1 injected-numbers rule |
| V4 | Any AI stage with `feeds_deterministic = true` also has `human_approval = true` | 4.4 Human Gate 2 |
| V5 | `schema_version` is a supported version (currently: 1) | controlled evolution |
| V6 | Unknown keys anywhere are rejected (strict parsing, no silent typos) | loophole discipline |
| V7 | Deliverables include `audit_log` and `manifest` — always | 4.8 re-performability |
| V8 | Enum fields only accept declared values | no undefined behavior |
| V9 | Stage `needs` references only earlier stage ids (no forward/unknown refs) | executable ordering |
| V10 | Stage ids and playbook names are snake_case ASCII (max 64 chars) | ids become audit references and filenames |
| V11 | `tool = "opskit_run_playbook"` stages declare `ops_playbook` (lowercase/hyphen key, e.g. `"weekly-review"`); no other tool accepts the key | the engine never guesses which analysis to run |

## Version choice, sourced

TOML 1.1.0 released 2025-12-18 (toml.io/en/v1.1.0). Python stdlib `tomllib`
(the parser this engine uses, per docs.python.org) implements TOML 1.0.0;
ecosystem adoption of 1.1 is still under coordination (discuss.python.org,
Jan 2026). Playbooks therefore use TOML 1.0.0 constructs only. When tomllib
adopts 1.1, playbooks may use new syntax without a schema change.

## Schema

```toml
schema_version = 1                    # V5: must be supported

[playbook]
name = "churn_analysis"              # snake_case identifier
version = "1.0.0"                    # playbook's own semver
description = "..."                  # one line, human-readable

[requirements]                        # checked against AnalystKit profile
min_rows = 100                        # optional, default 1
required_kinds = ["binary_target", "id_column"]   # optional
                                      # allowed kinds: binary_target,
                                      # id_column, timestamp_column,
                                      # numeric_column, categorical_column
source_types = ["csv", "excel", "sqlite", "postgres", "mysql"]  # optional

[[stages]]                            # ordered; executed top to bottom
id = "dq_gate"                        # V1: unique
kind = "kit"                          # V8: kit | ai | human_gate | package
tool = "analystkit_profile"           # kit stages: which MCP tool
gate = "must_pass"                    # V8: must_pass | advisory
                                      # V2: first stage must be kit+must_pass

[[stages]]
id = "dq_rules"
kind = "kit"
tool = "analystkit_validate"
gate = "must_pass"
needs = ["dq_gate"]                   # V9: only earlier ids

[[stages]]                            # step 7: the OpsKit stage
id = "ops_review"
kind = "kit"
tool = "opskit_run_playbook"          # V8: now a declared tool
ops_playbook = "weekly-review"        # V11: which OpsKit playbook; required
gate = "must_pass"                    # fails on data unfitness (zero rows);
                                      # operational criticals (surges,
                                      # shifts) are evidence, never a stop
needs = ["dq_gate"]

[[stages]]
id = "eda"
kind = "ai"
slot = "eda_notebook"                 # V8: eda_notebook | narrative_report |
                                      #     readme | rules_draft
numbers_from = "findings_store"       # V3: mandatory, only accepted value
human_approval = false
feeds_deterministic = false           # V4: if true, human_approval must be true
needs = ["dq_gate", "dq_rules"]

[[stages]]
id = "package"
kind = "package"
needs = ["eda"]

[deliverables]                        # V7: audit_log + manifest mandatory
artifacts = ["eda_notebook", "readme", "workpaper", "audit_log", "manifest"]
```

## Design principles

1. **Declarative only.** A playbook contains no code, no expressions, no
   templating. It names stages, tools, slots, and gates. Behavior lives in
   the tested engine, never in the playbook.
2. **Fail closed.** Anything not explicitly allowed is rejected: unknown
   keys, unknown enum values, unknown stage kinds, forward references.
3. **Users can write playbooks** — that is the product's quiet biggest idea
   — which is exactly why validation is strict and errors are teaching-grade:
   every error says what is wrong, where, and what the valid options are.
4. **The engine stays small.** The loader returns frozen dataclasses. The
   executor (build step 4) consumes them. New archetypes are new TOML files.

## Schema evolution note (step 7)

Step 7 added the `opskit_run_playbook` tool and the `ops_playbook` stage key
as a **backward-compatible extension of schema v1**: every playbook valid
before step 7 remains valid and means the same thing. New declared values
and new optional-by-tool keys extend the constitution; they do not break it.
A change that altered the meaning of an existing playbook would require
schema_version 2.

## Out of scope for schema v1 (deferred consciously)

- Conditional stages / branching (playbooks are linear in v1)
- Parallel stage execution
- Parameterized playbook templates
- Cross-playbook composition (OpsKit-style includes)
- User-defined AI slots

Each of these lands, if ever, as schema_version 2+ with a documented
migration path — never as a silent extension of v1.
