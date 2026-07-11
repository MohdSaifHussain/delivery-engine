# STEP 8 DECISIONS — ops narrative artifacts

**Date:** 11 July 2026 · **Scope:** the ops_report AI slot, the
inject_from_findings provenance control, ops_review archetype v1.1.0,
charter amendment to v0.4.

## 1. Design decisions, as built

1. **New slot, not generalized builders.** ops_report is its own declared
   AiSlot with its own builder. The existing report/readme builders keep
   reading dq_profile/dq_validate; no shared branching code path.
2. **The central problem: OpsKit findings carry numbers inside prose.**
   "Volume rose 140% (35 -> 84)" is a claim whose numbers the
   NumberInjector never emitted, so verify_artifact_numbers would
   correctly reject a report quoting it. The dishonest fixes were
   rejected by name: wrapping finding text in backticks (gaming the
   claims-surface extraction) or loosening the verifier. The honest fix:
   those numbers ARE hashed-store content. The injector gained
   **inject_from_findings(stage_id, text)**: it proves the exact string
   exists as a value inside that stage's stored findings BEFORE
   registering its numeric tokens. Non-verbatim text raises StoreError.
   Provenance by construction, not builder discipline — and any number a
   builder writes itself still fails verification (tested).
3. **Declared inputs.** The report stage's needs[0] names the OpsKit
   findings stage it renders (stage contract 4.7). An ops_report stage
   with no needs is refused with a clean ExecutorError.
4. **ops_review v1.1.0:** report stage added (ai / ops_report /
   numbers_from = findings_store), package now needs it, ops_report added
   to deliverables. Backward-compatible schema extension; the spec's
   evolution note updated.
5. **Optional LLM paragraph** reuses the existing labeled pattern with
   clean absence when no API key is present.
6. **Artifacts stay timestamp-free** (charter 4.8): the report is
   byte-reproducible across runs, proven by manifest hash equality.

## 2. Loophole hunt results (two found, both fixed with regression tests)

1. **Silent omission by severity.** A finding with an unexpected severity
   landed in the counts but vanished from the rendered narrative — the
   report would claim 8 findings and show 7. Fixed: unknown severities
   fail closed with a named error.
2. **Raw crash on wrong needs target.** needs[0] pointing at a non-OpsKit
   stage (a profile) hit payload["findings"] and crashed with a raw
   KeyError. Fixed: the builder validates OpsKit shape (list of objects
   with severity and text) and raises a clean StoreError naming the fix.

## 3. Gates

119/119 tests (107 prior + 12 new: five unit tests of the verbatim
provenance control including the near-miss refusal, three end-to-end
ops_report tests including byte-reproducibility, two loophole
regressions, two constitution checks), ruff clean, mypy strict zero
errors. Run in the full environment with the real analystkit-mcp,
opskit-mcp, and analystkit packages installed.

## 4. Changed files

- src/delivery_engine/store.py (inject_from_findings + _iter_strings)
- src/delivery_engine/playbook.py (AiSlot.OPS_REPORT)
- src/delivery_engine/artifacts.py (build_ops_report, fail-closed shape
  and severity validation)
- src/delivery_engine/executor.py (filename map, dispatch branch,
  declared-inputs check)
- playbooks/ops_review.toml (v1.1.0)
- tests/test_step8.py (new)
- PLAYBOOK_SPEC.md, PROJECT_CHARTER.md (v0.4)
