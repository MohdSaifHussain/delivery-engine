# STEP 10 DECISIONS — the deterministic baseline model stage

**Date:** 11 July 2026 · **Scope:** StageKind.MODEL, the fixed-seed
baseline trainer, churn archetype v1.1.0, charter amendment to v0.6.

## 1. The reframing decision (conscious charter amendment)

The original diagram placed "Baseline Model" under the bounded AI slots:
"code generated, run deterministically." v1 deliberately generates NO
code. Training a baseline classifier over columns the planner already
classified — and the human already approved — is charter 4.6's lesson
again: a deterministic problem wearing an AI costume. The strongest
sandbox is executing no generated code at all; section 11's sandboxing
question is answered by deferral, and custom AI-authored training code,
if it ever arrives, comes behind Human Gate 2 like drafted rules do.

## 2. Determinism, sourced

scikit-learn's own common-pitfalls documentation ("Controlling
randomness"): for reproducible results across executions, every
random_state=None must be removed; passing INTEGERS is the safest,
preferred option. Both the stratified splitter and the estimator take
the same fixed integer seed (42), recorded in the findings. Metrics are
rounded to 6 decimals as a DECLARED contract so same-environment
re-performance reproduces the findings hash exactly. Proven by test:
two training runs produce identical findings; two full package runs
produce identical baseline digests and identical narrative reports.

## 3. Declared gate semantics

must_pass fails when a valid baseline CANNOT be trained: missing
scikit-learn (clean error naming delivery-engine[ml]), non-binary
target, minority class under 10 rows, plan/source column drift, all
feature rows null. Metric VALUES never gate — the engine holds no
opinion on how good a baseline should be; that judgment is explicitly
the human's (charter section 5). Planted-signal testing: the churn
fixture's target is a deterministic function of tenure, so the baseline
MUST reach roc_auc > 0.95 — a specific planted answer, not a smoke test.

## 4. Loophole hunt (three found; two fail-closed fixes, one design pivot)

1. **Null crash.** A null in any feature row surfaced as a raw sklearn
   error. Fixed: rows with nulls in used columns are dropped and the
   count recorded in the hashed findings (n_rows_dropped_nulls); refusal
   if too little data survives.
2. **Identifier leakage.** A numeric id classifies as both id_column and
   numeric_column and entered the feature set. Fixed: id-classified
   columns never train.
3. **Silent target pick.** With two binary columns the stage silently
   trained on whichever came first. The first fix attempt REFUSED on
   multiple candidates — and the existing step-4 test suite immediately
   proved that wrong: any ordinary yes/no flag column tripped it, making
   the archetype unusable on real data (the over-engineering guardrail,
   fired by the tests). Final design: DISCLOSED deterministic selection —
   first binary candidate in the plan column order the human approved at
   Human Gate 1, with all candidates and the selection rule recorded in
   the hashed findings, the audit rationale, and visible in the report.

Also observed: a post-approval target drift is caught by the step 4
TOCTOU control at dq_profile before the model stage ever runs — the
third documented instance of layered defense (charter 4.9), with the
model stage's own class-count refusal as the second layer behind it.

## 5. Gates

145/145 tests (127 prior + 18 new), ruff clean, mypy strict zero errors
across 9 source files. New dependency: scikit-learn>=1.5 as the [ml]
optional extra; a must_pass model stage fails loudly if absent, never
silently skips.

## 6. Changed files

- src/delivery_engine/model.py (new)
- src/delivery_engine/playbook.py (StageKind.MODEL, V12)
- src/delivery_engine/executor.py (model dispatch + runner)
- src/delivery_engine/artifacts.py (optional baseline section,
  clean-absence)
- playbooks/churn_analysis.toml (v1.1.0)
- pyproject.toml ([ml] extra)
- tests/test_step10.py (new)
- PLAYBOOK_SPEC.md, PROJECT_CHARTER.md (v0.6)
