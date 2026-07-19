# STEP 22 DECISIONS — Run Lineage: Sequenced, Immutable Run Folders

**Date:** 19 July 2026 · **Charter:** amended to v0.18 · **Gates at
close:** 347 tests passed (+16), `ruff` clean, `mypy --strict` zero
errors.

## The problem (analytically correct, not invented)

Cleaning a messy dataset is iterative, never one-shot — true even with
enterprise tooling. You profile, find issues, fix some, re-run, find
the issues the first fix exposed, fix those, re-run again; routinely 3
to 10 iterations. That lifecycle — messy to clean across several
attempts — is the most audit-relevant artifact the engine produces,
and it must be preserved as evidence, never overwritten.

The executor already refuses a non-empty output directory (stale files
must not be hash-certified as a new run's evidence). That safety rule
and the need to keep history were in tension: overwriting to re-run
loses the lineage.

## The resolution: satisfy the safety rule, don't change it

Each run seals into its own fresh, sequentially numbered folder, so the
executor always receives an empty directory and its safety rule holds
by construction. Nothing about the executor changed. The lineage layer
sits in front of it.

## The anchor decision: run sequence number, NOT date

Two iterations can happen the same afternoon or weeks apart. A date
records WHEN, not WHICH ATTEMPT. `run_001`, `run_002`, ... is the
identity: monotonically increasing, never reused, never renumbered. The
generation date lives inside each run's report as metadata (Step 21),
not as the folder's identity.

## Design positions

1. **The filesystem is the ledger.** A dataset's output area holds
   `run_001 .. run_NNN` in order, each a complete, hash-sealed package.
   No database, no hidden counter — the directory listing is the only
   source of truth, which is what makes it trustworthy: a reviewer
   opens `run_003` and `run_005` side by side and sees completeness
   climbing and exceptions shrinking.

2. **Never refill a gap.** If an earlier run folder is deleted by hand,
   the next run is still highest+1, never the deleted number. A missing
   `run_002` is visible history — evidence that something was removed —
   not a slot to silently reuse. Proven by test.

3. **Never overwrite.** If the computed next folder somehow already
   exists, the engine fails loudly rather than clobbering a sealed run.

4. **Strict recognition.** A run folder is exactly `run_` + at least
   three digits, and must be a directory. A file named `run_005`, a
   folder named `run_bad`, `RUN_001`, `run_007x`, or a stray note are
   all ignored, so the ledger's ordering cannot be corrupted by
   incidental files.

5. **Numeric ordering, not lexical.** Runs sort by their integer value,
   so `run_009 -> run_010 -> run_100` orders correctly and the next
   number is a true maximum, not a string-sort artifact. 4-digit and
   larger runs coexist with 3-digit ones.

6. **Opt-in.** Lineage is a `--lineage` flag on the runner. Without it,
   behaviour is exactly as before (a flat output directory). With it,
   the run seals into the next `run_NNN` under the output area. No
   existing workflow changes silently.

## Determinism and folder discipline (verified, not assumed)

Two runs on the SAME input produce IDENTICAL findings hashes — this is
determinism working, not a conflict: same input, same hash. When the
data is actually cleaned between runs, the input differs, so the hashes
differ, and that difference IS the evidence of remediation. Verified
empirically: dq_profile / dq_validate / math digests matched
byte-for-byte across two runs on identical data.

Each run folder is physically separate (distinct inodes; no shared or
overwritten files) and its manifest hashes only its own package (no
cross-run references, relative paths within the package), so any run
folder can be moved, copied, or verified in isolation. The internal
`final/` layout is the engine's existing sealed-package structure —
Step 22 adds no mess, it only wraps each run in a numbered folder.

## Loophole hunt — found and closed (with regressions)

- **H1 (verified safe):** numeric not lexical ordering — `run_100`
  never sorts before `run_009`; the next number is a true integer max.
- **H2 (verified safe):** 4-digit runs (`run_1000 -> run_1001`) work;
  no width ceiling.
- **H3 (verified safe):** a *file* named `run_005` is ignored — only
  directories count, so a stray file cannot corrupt the ledger.
- **H4 (verified safe):** strict name recognition rejects `RUN_001`,
  `run_00`, `run_007x`, leading-space; only genuine `run_NNN` matches.
- **H5 (verified safe):** a symlinked output area resolves to the real
  directory and seals correctly.

## What was built

- `src/delivery_engine/lineage.py` — `run_number`, `existing_runs`,
  `next_run_dir`, `LineageError`, `RUN_DIR_RE`. Stdlib only (`pathlib`,
  `re`); no DuckDB, no version-sensitive API — verified empirically on
  real directories rather than by doc-check.
- `src/delivery_engine/runner.py` — the opt-in `--lineage` flag; when
  set, the output resolves to `next_run_dir(out)` before the executor
  runs. The executor is untouched.
- `tests/test_step22.py` — 16 tests: number parsing, sequencing,
  immutability (deleted-middle-not-refilled, never-overwrites,
  restart-only-when-empty), ledger integrity (stray files, area-is-a-
  file error), runner integration (seals into run_001 with a real
  sealed package), and the five hunt regressions.

## Open items (declared, not hidden)

- **Human-declared final (deferred to its own increment):** the
  "all-green = final" signal must NOT be an engine decision — all-green
  means zero exceptions against the rules the human wrote, not that the
  data is objectively correct. The engine should REPORT the green state
  as a fact and a NAMED HUMAN declares a run final (same pattern as
  Human Gate 2 and null signatures). Captured here so it is not lost;
  it lands as a small follow-on, not silently.
- **Step 23 (trend report):** a deterministic across-runs report
  reading `run_001 .. run_NNN` and drawing exceptions per attempt and
  completeness climbing — the remediation journey as one picture. Now
  UNBLOCKED by this step. Same determinism and injected-numbers
  discipline as Step 21: every point is a hashed finding from some
  run_NNN, nothing computed, nothing decided by AI.
