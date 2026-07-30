# STEP 25 — DECISIONS

**Build step:** 25 — Generator schema-currency: surface the step-24 keys
**Proposed version:** v1.6.0 (MINOR — additive; generated-draft semantics unchanged)
**Status:** Proposal, pre-build
**Motivation (observed, not hypothesised):** the July 2026 docs-coverage audit
confirmed `generator.py` has no knowledge of the step-24 model-stage keys
(`metric_ci`, `split`, `n_splits`). Drafts it produces remain valid under the
v1.5.0 loader (verified empirically), but the generator can never surface the
engine's evidence-honesty options — a shipped authoring tool silently behind
its own engine's schema.

## 1. The design position: commented suggestions, feasibility-gated

The generator emits the step-24 keys as **TOML comments inside the model-stage
block**, never as active keys:

```toml
[[stages]]
id = "baseline"
kind = "model"
gate = "must_pass"
needs = ["dq_gate", "dq_rules"]
# Opt-in evidence options (see USER_GUIDE.md and PLAYBOOK_SPEC.md, V12):
# metric_ci = true          # Wilson 95% CIs on recall/precision (statsmodels/NIST)
# split = "walk_forward"    # time-ordered evaluation (scikit-learn TimeSeriesSplit)
# n_splits = 5              # legal only with split = "walk_forward"
```

Why comments and not active keys:
- **Draft semantics are unchanged.** A comment is invisible to `tomllib`, so the
  draft loads and means exactly what a step-19 draft meant. No golden findings
  move anywhere; nothing about §4.8 is touched.
- **The draft principle is preserved.** A pipeline never approves its own rules
  of engagement; by the same logic a generator should not *activate* evaluation
  choices on the human's behalf. It surfaces them; the human uncomments —
  which is itself the approval act.
- **Feasibility-gating, the generator's own pattern, extends naturally:** the
  `split`/`n_splits` suggestion lines are emitted **only when the profile
  classifies a `timestamp_column`** (a time-ordered split without one is a
  feasibility refusal at run time — suggesting it would teach users to write
  playbooks that refuse to run). `metric_ci` is suggested whenever a model
  stage is drafted, since it is feasible wherever the stage is.

## 2. Determinism contract

Unchanged in kind: same profile + same answers → byte-identical draft. The
template gains fixed lines; the function stays pure. Any existing test pinning
generator output bytes is updated **consciously in this step** — that is the
one place goldens legitimately move, because the generator's output is a draft
for human approval, not sealed evidence.

**Correction (2026-07-31), found during Phase 0 verification, same
append-only pattern as STEP24's versioning correction:** the premise above
assumed a byte-pinning test for generated model-stage output already
existed. It does not. `tests/test_step19.py` is the only test file that
imports `delivery_engine.generator`, and every `compile_playbook(...)` call
in it passes `include_stages` of `["math"]`, `["stats"]`, or
`["math", "stats"]` — never `"model"`. The model-stage branch of
`_emit_toml` (the `if "model" in stages:` block) therefore has zero content
or byte assertions against it today. The "goldens legitimately move" clause
is consequently **vacuous for this step**: there is nothing existing to
move. `tests/test_step25.py` is not an update to prior coverage — it is the
first content coverage the model-stage emission branch has ever had,
closing a latent test gap as a side effect of adding the comment lines.

## 3. Tests (planted-answer)

New `tests/test_step25.py`:
1. Draft from a profile **with** a classified timestamp column contains all
   three commented suggestion lines.
2. Draft from a profile **without** one contains the `metric_ci` line and
   **not** the `split`/`n_splits` lines.
3. Both drafts load through `load_playbook` and are semantically identical to
   pre-step-25 drafts (the comments change nothing the loader sees).
4. Byte-determinism: two generations from the same inputs are identical.

Loophole hunt candidates: comment lines colliding with V6 strict parsing
(they must not — comments are not keys); a dataset whose timestamp column is
also the id column; hostile column names inside the comment text.

## 4. Release notes

Charter amendment (append-only, next number in sequence): Build Step 25, the
commented-suggestion design and its draft-principle rationale, the
feasibility gate on `split`. CHANGELOG under the accumulating `[Unreleased]` →
released as 1.6.0. `pyproject.toml` → 1.6.0. PLAYBOOK_SPEC and USER_GUIDE need
no changes (the keys are already documented there; the generator now points at
them).

*A generator that outruns its engine writes invalid drafts; one that lags it
hides the engine's honesty. Schema-currency is part of the contract.*
