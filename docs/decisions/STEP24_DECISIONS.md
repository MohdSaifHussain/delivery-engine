# STEP 24 — DECISIONS

**Build step:** 24 — Model-stage evidence honesty
**Proposed version:** v1.4.0 (MINOR — additive, opt-in, no hash movement)
**Status:** Proposal, pre-build
**Evidence source:** the Meridian Wafer Works forward-deployed engagement
(`FDE_ENGAGEMENT_RECORD.md`), a governed pilot on real semiconductor
wafer-fabrication data (UCI SECOM) run end to end against a working copy of
this engine.

---

## 0. The charter question, answered first

**This step does not violate the charter.** §4.5 states that adding a new
*project type* means writing a new playbook, never modifying the engine — and
that is honoured here: no archetype logic enters the engine. Adding a new
*capability* has always proceeded by numbered build step with an appended
charter amendment: step 10 added the model stage, step 15 stats, step 17 math,
step 18 the six analyst-error guardrails, steps 21–23 the report, lineage and
trend layers. The charter itself provides the mechanism: *"Where a future
decision conflicts with this charter, the charter is either consciously amended
(with a version bump and a dated note) or the decision is wrong."*

This step follows that mechanism. It is Build Step 24, not an exception to the
constitution.

**Precedent for the justification pattern.** Step 18's G1 leakage sentinel was
motivated by an observed production failure — the July 2026 fraud run where a
post-hoc label column produced ROC-AUC 1.0. Every change below is likewise
motivated by a failure observed in a real engagement, not by hypothesis.

---

## 1. The versioning decision (decided before design, because it constrains it)

The charter's v1.2 amendment records the governing rule: *this project's public
API is not `run()` — it is the re-performability contract (§4.8): same inputs →
same hashes.* A change that causes a package sealed under v1.x to re-perform to
a different manifest reads, under this engine's own rules, as *the evidence has
been altered*. That is a breaking change.

**Empirical finding from the engagement.** A working copy implemented these
features as always-on. Re-running the shipped `churn_analysis` example against
it produced:

| Findings | Golden (v1.3) | Working copy | Result |
|---|---|---|---|
| `dq_profile` | `bcfd074d…` | `bcfd074d…` | identical |
| `dq_validate` | `ded2910b…` | `ded2910b…` | identical |
| `dq_dedupe` | `955270cc…` | `955270cc…` | identical |
| `baseline` | `3d720cf9…` | `9a83de91…` | **differs** |

Every metric value was bit-identical (accuracy 0.805224, precision 0.660622,
recall 0.546039, f1 0.59789, roc_auc 0.845464). The hash moved solely because
fields were **added**. Nothing was computed differently.

**Decision: every feature in this step is opt-in, defaulting to present
behaviour.** An existing playbook that declares no new key produces
byte-identical findings, so no sealed package's manifest moves and §4.8 holds.
This makes the step v1.4.0 (MINOR). Had the features shipped always-on it would
be v2.0.0 by the charter's own rule — and the v1.3 amendment, which withdrew
the python-docx migration precisely because it broke hashes for no user-facing
gain, is the precedent for declining that trade.

---

## 2. Change 1 — Metric confidence intervals for the model stage

### The failure observed
In the engagement, the model stage reported `recall 0.423077` with no
uncertainty. That figure was estimated from **26 positive cases**. Its true 95%
interval is [25.5%, 61.1%] — wide enough to contain the previous iteration's
point estimate, meaning an apparent improvement was not statistically
distinguishable. Read bare, the number invited a conclusion the data could not
support.

### Why this belongs in this engine
This is the exact failure G3 exists to prevent one layer up. Step 18's minimum
detectable effect was added so that *"not significant" can never again be
silently read as "no effect."* A recall estimated from few positives is the same
error wearing different clothes: a point estimate presented as if precise.
`CLAUDE.md` roadmap item 4 already carries the intent — *"G2/G3 for model
playbooks — pseudoreplication (G2) and minimum detectable effect (G3)
guardrails currently skip model-only playbooks."* This step closes that item for
the metric case.

### Design
- **Reuse, do not reimplement.** `stats._wilson(count, nobs, alpha)` already
  wraps `statsmodels.stats.proportion.proportion_confint(method="wilson")`. The
  model stage calls that same function. This applies the Single-Reader
  Principle from step 20 — the divergence risk of two implementations of one
  statistic is the same class of bug as two parsers for one file.
- **Sources are already in the register:** Brown, Cai & DasGupta (2001);
  NIST/SEMATECH e-Handbook 7.2.4.1; statsmodels official documentation.
- **Alpha.** V14 makes `[stats] alpha` legal only when a stats stage exists, so
  a model-only playbook has none. The interval therefore uses a **fixed
  constant, disclosed inside the hashed findings**, exactly as V15 requires of
  every math threshold. Where a stats stage *does* exist, the pre-registered
  alpha is used, and which one applied is recorded.
- **Findings shape (added only when enabled):** `n_positives_in_test`,
  `recall_ci95`, `precision_ci95`, `alpha`, `alpha_source`, and a caveat naming
  the positive count.
- **Gate semantics unchanged.** Step 10's declared rule stands: metric values
  never gate, training feasibility does. An interval is disclosure, never a stop.

### Schema
New optional model-stage key `metric_ci = true|false` (default `false`).
Validated under V12's existing model-stage clause. Absent key → findings
byte-identical to v1.3.

---

## 3. Change 2 — Evaluation-split honesty for time-ordered data

### The failure observed
SECOM's row order encodes time. The engine correctly quarantined the timestamp
as a *feature* (it was classified `timestamp_column` and excluded), but
evaluation still used a random stratified split — which interleaves future and
past units across train and test. A fab deploys forward in time, so the random
split measured something the deployment will never experience.

Re-running under walk-forward evaluation was decisive: mean fold recall **39.3%**
against the random split's 42.31% — close on average, but with a fold range of
**0% to 70%**. One fold caught nothing at all. The random split had concealed
that volatility completely.

### Why this belongs in this engine
G1, the leakage sentinel, exists because *the answer key must not hide in the
features*. Training on the future and testing on the past is the temporal form
of the same violation, and it is invisible to G1 because no single feature is
implicated — the *split* is. scikit-learn states the position plainly in its own
documentation for `TimeSeriesSplit`: it provides indices for time-ordered data
*where other cross-validation methods are inappropriate, as they would lead to
training on future data and evaluating on past data.*

This is an evidence control, not a modelling feature. It does not make the
baseline a better model; it makes the baseline's reported number honest about
what it measured. That distinction is what keeps it inside §4.5's spirit and
inside step 10's declared scope of the model stage as a *reference point*.

### Design
- **Source:** scikit-learn `TimeSeriesSplit` official documentation. The
  standards register already names *"scikit-learn's controlling-randomness
  guidance"* for this stage.
- **The ordering column comes from the plan, never guessed** — the step-17
  principle. If `split = "time_ordered"` or `"walk_forward"` is declared and the
  plan classifies no `timestamp_column`, that is a **feasibility refusal naming
  the remedy**, not a silent fall back to row order. A requirement that says
  nothing is worse than no requirement (step 20).
- **Findings record which split ran**, the ordering column, and per-fold train
  size, test size, positive count, and metrics — plus mean and range across
  folds. The range is the finding; a mean alone would rebuild the concealment.
- **Determinism holds:** `TimeSeriesSplit` is deterministic given ordered input;
  the fixed seed continues to govern the estimator.

### Schema
New optional model-stage keys `split = "random" | "time_ordered" |
"walk_forward"` (default `"random"`) and `n_splits` (integer, default 5, legal
only with `split = "walk_forward"`). Enum-validated under V8; the conditional
legality of `n_splits` follows the V11 precedent, where a key is legal only for
the tool that accepts it.

---

## 4. Change 3 — Identifier-aware injected-numbers scanning (bug fix)

### The failure observed
A dataset whose columns are named `sensor_001 … sensor_590` crashed the
narrative stage. `verify_artifact_numbers` read the digits inside `sensor_060`
as an unprovenanced numeric claim and raised, so **no package sealed at all**.
Any user whose column names contain digits — `Q1_2024`, `col_1`, `stage_2_yield`
— hits this. The engine cannot produce a deliverable for such a dataset.

### Why the obvious fix is wrong
The tempting repair is to loosen the number regex with identifier boundary
lookarounds. **That would weaken a control the charter explicitly celebrates.**
Step 17's amendment records that the claims scan *"caught the un-injected digits
in the literal tokens `p95` and `p99` before the end-to-end test could pass, the
charter working as designed."* A blanket boundary rule would stop catching
`p95`, because a letter precedes the digits. The fix would silently retire a
guard the constitution names as working.

### Design — allowlist by known identifier, not by shape
The scanner exempts a digit token **only when it is part of a token that exactly
matches a column name present in the approved plan / hashed profile.** The
engine already knows those names; they are governed data, approved at Human Gate
1, not inferred from the text.

- `sensor_060` — exempt, because `sensor_060` is a known column. Correct: it is
  an identifier, not a claim, and cannot be "injected" as a number because it is
  not one.
- `p95` — still caught, because `p95` is not a column name. The step-17
  behaviour is preserved exactly.
- `42.7%` — still caught. Bare fabricated figures are unaffected.

This narrows the exemption to the precise, provable case and leaves the rule's
strength intact everywhere else. It is a bug fix restoring intended behaviour,
not a relaxation.

### Schema
None. No playbook change; no new key. Behaviour is identical for every dataset
whose column names contain no digits, so no existing package's artifacts change.

---

## 5. Test plan — planted-answer discipline

New suite `tests/test_step24.py`, following §7: fixtures contain known issues
and tests verify exactly those are found.

**Backward compatibility (the load-bearing tests)**
1. A model playbook declaring none of the new keys produces a `baseline`
   findings digest byte-identical to the v1.3 golden. This is the §4.8 test for
   this step and it must pass before anything else is considered.
2. Every shipped example re-runs to its committed golden manifest.

**Change 1**
3. Planted: a test set with a known positive count. The recorded
   `n_positives_in_test` equals it, and `recall_ci95` matches
   `stats._wilson` called directly on the same counts — proving one
   implementation, not two.
4. The disclosed alpha appears inside the hashed findings; when a stats stage
   pre-registers alpha, that value is used and `alpha_source` says so.
5. A metric value outside its interval is impossible by construction; a
   degenerate case (zero positives) records a disclosed skip with a reason, never
   a crash and never a fabricated interval.

**Change 2**
6. Planted: a dataset whose late period carries all the signal. The random split
   reports high recall; `walk_forward` reports the low-recall fold — the concealment
   is demonstrated, not asserted.
7. `split = "time_ordered"` with no classified timestamp column is a clean
   feasibility refusal naming the remedy, not a row-order fallback.
8. Per-fold records include the fold range; two runs on the same input produce
   identical fold hashes.

**Change 3 — the loophole hunt**
9. `sensor_060` in narrative prose no longer raises, and the package seals.
10. **`p95` in template text still raises** — the step-17 catch survives. This
    test is the reason the allowlist design was chosen over a regex loosening.
11. A bare fabricated `42.7%` still raises.
12. A column named `95` (adversarial: a column name that *is* a number) does not
    become a laundering channel for arbitrary figures — the exemption matches the
    whole token against known names and cannot be used to smuggle a claim.

---

## 6. Adversarial loophole hunt — candidates to close before ship

Per §7, hunted before the version ships; each fix lands with a regression test
proving the old failure.

- **H1 — exemption laundering.** Can a hostile or unlucky column name turn the
  identifier allowlist into a hole through which any number passes? (Test 12.)
- **H2 — alpha smuggling.** Can `metric_ci` be used to introduce an
  un-pre-registered alpha that later reads as a significance claim? Mitigated by
  disclosing alpha and its source inside the hashed findings, and by metric
  values never gating.
- **H3 — fold-count abuse.** Does a large `n_splits` on a small dataset produce
  folds with zero positives, and is that a disclosed skip rather than a
  divide-by-zero or a silent 0.0 that reads as a real result?
- **H4 — timestamp trust.** If the classified timestamp column contains ties or
  nulls, is ordering deterministic and disclosed, or silently arbitrary?
- **H5 — mean-only concealment.** Can a consumer read the walk-forward block and
  see only the mean? The range must be structurally adjacent to it in the findings,
  not derivable-only.

---

## 7. Release checklist alignment (CLAUDE.md)

Applies in full. Specifically:

- All four gates green: `pytest -q`, `mypy src/ --strict`,
  `ruff check src/ tests/`, `ruff format --check src/ tests/`
- `pyproject.toml` bumped to 1.4.0; `pip install -e . --no-deps`
- README test-count badge and the Docker test count updated to the new total
- CHANGELOG `[Unreleased]` promoted per Keep a Changelog 1.1.0
- **PROJECT_CHARTER amendment record appended — never editing an existing
  amendment**, recording: Build Step 24, the opt-in versioning decision and the
  hash evidence behind it, and the three changes with their sources
- `PLAYBOOK_SPEC.md` updated with the new optional model-stage keys under V12,
  and the schema-evolution note extended — these are backward-compatible
  extensions of schema v1; every playbook valid before step 24 remains valid and
  means the same thing
- CLAUDE.md roadmap: item 4 (G2/G3 for model playbooks) marked partially closed
- Examples: **not re-run**, because opt-in defaults mean no example output
  changes. That is the intended outcome and should be verified, not assumed.

---

## 8. What was deliberately excluded

The engagement also produced class weighting, feature scaling, median
imputation, threshold tuning to an operating budget, and coefficient-based
signal attribution. **None are proposed for this engine.**

Step 10 declared the model stage a *deterministic baseline* — a reference point,
and the narrative report says so in its own words: *"This is a reference point
for human modeling work, not a delivered model."* §5 places iterative
experimentation and domain feature engineering explicitly on the human's side of
the line. Those five changes make the baseline a *better model*, which is
precisely the 30–40% the charter reserves for professional judgment.

The imputation case is worth naming, because it looked most like a defect: on
SECOM the baseline refused to train, since no row was complete across all 590
sensors. The engine's error said *"fix completeness first — that is what the DQ
gates are for."* That is not a bug. It is the architecture holding its line, and
it should not be softened.

They remain valuable where they were built — in the engagement's own workspace,
as the record of a real customer problem. They do not belong in the engine.

---

*A stage that cannot fail is not a gate. A number without a hash does not enter a
deliverable. A project that cannot be re-performed is just output.*
