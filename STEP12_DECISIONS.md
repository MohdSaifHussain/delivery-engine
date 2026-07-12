# STEP 12 DECISIONS — GitHub Actions CI (and the completion of v0.1)

**Date:** 11 July 2026 · **Scope:** the CI workflow, a root README with
CI badge, charter amendment to v0.8. This step closes the last open item
in the charter's Section 10 definition of done.

## 1. Why this is a step, not an afterthought

Section 10 lists "all three quality gates green with CI" as a success
criterion, and Section 7 requires CI "green from first commit." Green
locally is not the bar the charter set — green on push is. Until a push
triggered CI and it passed, the v0.1 thin slice was not done by its own
definition. This step is completion, not expansion.

## 2. The workflow

`.github/workflows/ci.yml` runs on push and PR to main. One job,
`gates`, mirrors the exact local sequence:

- Python 3.12 (the project's floor) via actions/setup-python@v5
- Node 24 via actions/setup-node@v6 (the presentation stage shells out
  to pptxgenjs)
- npm install pptxgenjs at the repo root — the same node_modules
  location the executor's discovery checks first, and the same a
  developer uses locally
- analystkit from its public git source, then the two MCP servers
  editable, then the engine with [dev,ml] extras
- markitdown[pptx] installed so the one PPT content-scan test RUNS
  instead of skipping — CI executes the fullest possible suite
- ruff check, then mypy --strict, then pytest -q

Action versions pinned to the major per official actions/setup-node
guidance (checkout@v5, setup-node@v6, setup-python@v5): @v-major tracks
patches without going stale or floating to an unreviewed default branch.
Concurrency cancels superseded runs on the same ref; permissions are
read-only (the workflow needs no write scope).

## 3. Validated before committed, not merely written

A CI file that only runs on push is hoped, not tested. Before commit,
the workflow was reproduced locally: a fresh venv, a clean copy of the
repo, the exact install sequence from the YAML, then all three gates.
Result: ruff clean, mypy strict zero errors, and **156 passed, 0
skipped** — the markitdown-gated PPT test that skips on the Windows dev
machine runs green in the CI-equivalent environment. The node_modules
discovery resolved the repo-root install correctly, confirming the same
path logic that the step-11 Windows hotfix corrected.

## 4. The README

The repo had no root README — a portfolio project's front page was
missing. Added one: the CI badge, the thesis, the architecture diagram
in brief, the rules that make output evidence, the repo layout, and the
gate-running instructions. Focused on what a reviewer needs to
understand the project in one screen, not a wall of text.

## 5. What "done" means now

Every original box on the architecture diagram has real, tested,
re-performable code, and CI proves it from a clean checkout. All six of
Section 10's success criteria are satisfied. The v0.1 thin slice is
complete. Remaining work is expansion — new archetypes are new TOML
files with test suites, no engine changes — and is consciously optional,
not a gap in the foundational build.

## 6. Changed files

- .github/workflows/ci.yml (new)
- README.md (new — root)
- PROJECT_CHARTER.md (v0.8; Section 10 CI criterion marked satisfied)
- STEP12_DECISIONS.md (new)
