# STEP 16 DECISIONS — Pre-flight Preview & Handoff Manifest

**Date:** 15 July 2026 · **Charter:** amended to v0.12 · **Gates at
close:** 227 tests passed, `ruff` clean, `mypy --strict` zero errors.

## What this step is

Two additions to how the engine meets the humans around it, both purely
additive — zero changes to existing playbooks, zero broken tests.

**The pre-flight preview** answers "what exactly is about to run?"
before anything runs. **The handoff manifest** answers "what must each
team check, against which evidence?" after everything has run. Between
them, the package now covers the full human journey: see it before,
verify it after, sign it by hand.

## The preview — design decisions

1. **A pure function of the governing documents.** `render_preview(
   playbook, plan)` reads only the loaded playbook and the approved
   plan — the same two objects the executor executes from. Stages in
   order with their gates and needs, the approved column
   classification, requirement check results, the pre-registered alpha
   when a stats stage exists, deliverables and output formats, and the
   plan digest so the preview is bound to the exact plan. Nothing is
   computed; there is no third source of truth to drift from the
   executor's behavior.

2. **The engine core stays non-interactive — the one deliberate
   deviation from the original spec, recorded with its reason.** The
   requested behavior was a hardcoded pause for ENTER inside the run.
   `run()` is a library function invoked by 227 tests, CI, and any
   future scheduled automation; a blocking `input()` inside it hangs
   all of them. The constitutional resolution: interactivity is a
   CALLBACK. `run(..., preview_confirm=...)` accepts a callable that
   receives the rendered preview and returns True/False. A terminal
   entry point passes `delivery_engine.preview.prompt_confirmation`
   (which prints and waits, exactly the requested UX); tests pass
   lambdas; automation passes nothing and no pause happens.

3. **Declining is an audited refusal, not a swallowed exit.** The run
   stops with `ExecutionStopped("preflight", ...)` before any stage
   executes, and the audit log records the decline. Stopped runs keep
   their evidence (the step-9 rule), so the decline message directs
   the human to a fresh output directory for the re-run.

4. **What the human saw is evidence.** The rendered preview is written
   to `execution_preview.md` in every run, confirmed or not, and the
   manifest hashes it like any other file.

## The handoff manifest — design decisions

1. **Checks are generated from what actually ran.** The four teams —
   data engineering, QA/quality control, compliance, manager — get
   checks derived from the stages present in the Findings Store: the
   row count from the hashed profile, re-performance of validation
   rules, the statistical tests with their pre-registered alpha and
   the ASA effect-size reminder, manifest and audit verification, and
   the manager's narrative approval. A pipeline without a stats stage
   gets no stats check; nothing is templated as if every pipeline were
   the same.

2. **Every check carries its evidence.** Checks reference the SHA-256
   of the sealed findings they are about — the reviewer verifies
   against the same hashes the artifacts injected from. No new
   computation, no second source of truth.

3. **Signatures start null and stay null.** The engine never signs for
   a human. Signing is a human act; the engine prepares the paper.

4. **Written before `manifest.json`, therefore hashed by it.** A
   forged signature after packaging changes the file hash and fails
   package verification — proven by test.

5. **No timestamps inside the file** (the step-9 rule: timestamps live
   outside hashed content; the audit log records when).

## Loophole hunt — found and closed

- **H1 (real bug, fixed):** the first implementation of the
  data-engineering row-count check read `row_count` from the profile
  findings — a key that does not exist in the AnalystKit envelope
  (the truth lives in per-column `total` values). The check would
  have shipped saying "verify the row count matches None": a
  fabricated check around a number the engine did not have. The
  planted test caught it before it ever ran end-to-end. Now the count
  comes from the per-column totals; if they disagree or are absent,
  NO row-count check is written — the engine never invents a check.
- **H4 (UX trap, closed):** declining the preview leaves the preview
  file and audit entry in `out_dir` (stopped runs keep their
  evidence), which means a naive re-run into the same directory hits
  the stale-files refusal. The decline message now says so explicitly
  and directs the human to a fresh directory; the interaction of the
  two refusals is under regression test.
- **H8 (untested surface, closed):** `prompt_confirmation` itself is
  tested via monkeypatched stdin — ENTER/y/yes proceed, n declines,
  and the preview text is verified to have been printed.
- **Verified:** the preview is deterministic (same inputs, same
  text); the preview file appears in the manifest with a matching
  hash; declining executes nothing (no findings are sealed); the
  handoff is byte-identical across re-runs; every evidence digest in
  the handoff matches a digest actually sealed in `findings/`; the
  handoff's `plan_sha256` matches the approved plan's digest.

## What was built

- `src/delivery_engine/preview.py` — `render_preview` (pure),
  `prompt_confirmation` (the terminal helper), `ConfirmCallback`.
- `src/delivery_engine/handoff.py` — `build_handoff`, `write_handoff`.
- `executor.py` — `run(..., preview_confirm=None)`; preview rendered,
  written, and optionally confirmed before the stage loop; handoff
  written at package time before the manifest; three new audit entry
  kinds (`preview confirmed/declined`, `package:handoff written`).
- `tests/test_step16.py` — 15 tests: preview purity and completeness,
  confirmation semantics, handoff integrity, tamper detection, hunt
  regressions.

## Open items (declared, not hidden)

- Step 17: the universal descriptive math layer (MAD outliers,
  entropy, VaR, distribution fitting with the Lilliefors correction,
  date gaps/trends) as a governed stage over plan-classified columns.
- Step 18 (deferred by decision): two-tier output structure and
  domain-specific narrative vocabulary — a migration, to be planned
  as one.
- A thin CLI entry point that wires `prompt_confirmation` in by
  default would make the preview the default interactive experience.
