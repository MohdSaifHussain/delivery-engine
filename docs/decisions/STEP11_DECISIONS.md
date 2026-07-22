# STEP 11 DECISIONS — the deterministic PPT builder

**Date:** 11 July 2026 · **Scope:** AiSlot.PRESENTATION, delivery_engine.presentation,
churn archetype v1.2.0, charter amendment v0.7.

## 1. Architecture

The PRESENTATION slot lives in the AI stage kind for executor wiring
convenience, but generates NO AI content. Every number on every slide
is a Python literal f-string over the Findings Store snapshot —
the same injected-numbers contract as the narrative report, enforced in
the generator code. The tool chain is pptxgenjs 4.0.1 (PPTX skill:
"create new decks = pptxgenjs"), executed via subprocess after the
generator writes a self-contained JS script.

Slides: title, dataset overview (KPI cards), column profile (table),
validation findings (rule violations or clean pass), operational review
(OpsKit criticals or absent-section note), baseline model (chart +
metrics or absent-section note), evidence trail (hashes on dark navy).

## 2. The integrity seal

The generator script is the auditable artifact. Its SHA-256 is recorded
in the audit log as `sha256`. The hash is computed on the CONTENT script
— the output path replaced with "<OUTPUT_PPTX>" — so same findings
always produce the same hash regardless of the output directory. A
reviewer can regenerate the script from the same findings and compare.

pptxgenjs 4.0.1 embeds a creation timestamp in the OOXML package so
the binary .pptx bytes legitimately differ across runs. This is a tool
limitation, not an engine failure, documented in the reproducibility
test rather than hidden.

## 3. Loopholes found and fixed

1. **Python slice in JS f-string.** store_snapshot.get(...)[:24] inside
   an f-string that forms JS source code produces valid Python but
   syntactically invalid JS (the `[:24]` landed literally in the script).
   Fixed: pre-compute all digest shortenings as Python variables before
   the f-string, inject as plain string literals.
2. **Unused imports.** ruff caught `json` and `sys` leftover from an
   earlier draft; auto-fixed.
3. **Output path in content hash.** The script embeds the .pptx
   output path, so two runs with different tmp_path values produced
   different script hashes — the reproducibility test immediately caught
   this. Fixed: hash is computed on the script with the output path
   replaced by a sentinel string.

One design decision also recorded: accessing `store._entries` was the
original implementation. mypy strict correctly flagged it. Fixed by
adding `all_entries()` as a proper public accessor on FindingsStore —
the right fix rather than a type-ignore comment.

## 4. Gates

156/156 tests (145 prior + 11 new: 4 constitution and script-generator
unit tests, 5 end-to-end tests including planted-number verification and
script-hash reproducibility, plus stale-assertion fixes from the churn
archetype version bump), ruff clean, mypy strict zero errors across 10
source files.

## 5. Changed files

- src/delivery_engine/presentation.py (new)
- src/delivery_engine/playbook.py (AiSlot.PRESENTATION)
- src/delivery_engine/executor.py (slot dispatch + stage runner)
- src/delivery_engine/store.py (all_entries() accessor)
- playbooks/churn_analysis.toml (v1.2.0)
- tests/test_step11.py (new)
- tests/test_playbook.py, tests/test_step10.py (stale assertion fixes)
- PROJECT_CHARTER.md (v0.7)
