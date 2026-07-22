# STEP 9 DECISIONS — transaction_monitoring_review archetype

**Date:** 11 July 2026 · **Scope:** one archetype built deeply (charter
section 9: one stage or one playbook at a time), charter amendment to
v0.5. Zero engine changes — the entire step is one TOML file plus tests.

## 1. Why this archetype

The completeness question made executable: does a transaction feed
contain what it should, and did its volume behave? A silent volume drop
in a monitoring feed is the classic completeness failure — a
misconfigured feed can exclude millions of transactions from monitoring
with nothing visibly wrong until someone checks the trend. The archetype
maps the transaction-monitoring domain (ATL/BTL context, feed
completeness, data lineage) onto the engine's existing controls.

## 2. What it composes (first playbook to use the full system)

dq_profile (must_pass) → rules_draft (Human Gate 2, content-bound) →
dq_validate (must_pass, consumes the approved draft) → dq_dedupe
(advisory) → ops_review (OpsKit weekly-review, seal-verified, insight
criticals recorded as evidence) → narrative_report + ops_report (dual
narratives under the injected-numbers rule) → readme → package.

## 3. The loophole this step found and fixed

**Lexical routing collision.** The archetype's first description
contained the words "data quality", which tied it with the
data_quality_review archetype on that archetype's own goal wording —
10 existing planted tests failed the moment the file entered the
library, exactly as they should. Root cause: the planner's tie-break is
lexical, which makes archetype DESCRIPTIONS part of the routing
contract. Fix: the description was lexically differentiated (the tokens
"data quality" removed); regression tests pin both directions (the TM
goal routes to TM, the DQ goal still routes to DQ). A standing
archetype-authoring rule was written into the charter.

## 4. Observed pre-existing limitation (recorded, not fixed here)

The NumberInjector's emitted-token allowlist is cumulative across an
entire run, so a token injected for one artifact is allowlisted in all
later artifacts of the same run. Every token still traces to the
Findings Store, so charter 4.1 holds; per-artifact provenance is the
sharper property a future version could enforce with per-stage
injectors. Present since step 4; surfaced by this being the first
two-report archetype.

## 5. Gates

127/127 tests (119 prior + 8 new: composition and requirements checks,
both routing directions pinned, two-phase end-to-end with dual
narratives on real kits, full audit-story check, richest-package
reproducibility, Human Gate 2 wrong-hash refusal inside the
composition), ruff clean, mypy strict zero errors. Run with the real
analystkit, analystkit-mcp, and opskit-mcp installed.

## 6. Changed files

- playbooks/transaction_monitoring_review.toml (new)
- tests/test_step9.py (new)
- PROJECT_CHARTER.md (v0.5)
