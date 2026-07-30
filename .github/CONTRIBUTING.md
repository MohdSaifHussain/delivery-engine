# Contributing to Delivery Engine

Thank you for your interest in contributing. This project is built on a
strict governance principle: **agent proposes, deterministic tools dispose,
human governs, every claim traceable.** All contributions must uphold this.

## Before you start

Read these two files — they are the constitutional documents:

- [PROJECT_CHARTER.md](../PROJECT_CHARTER.md) — the architecture principles,
  the seven non-negotiable rules, and every design decision
- [CLAUDE.md](../CLAUDE.md) — the governance rules for Claude Code sessions
  (also useful for understanding what the engine does and does not allow)

## What we welcome

- **Bug reports** — use the Bug Report issue template
- **Feature requests** — use the Feature Request issue template
- **Playbook contributions** — new TOML playbooks in `playbooks/`
  (this is the correct way to add new analysis archetypes — never modify
  the executor to add business logic). A new playbook's `description` is
  a routing surface — the planner matches goal wording against it — so it
  must land with its own routing regression tests, and tests for its
  nearest lexical neighbors, per the standing rule from build step 9
- **Documentation improvements** — README, USER_GUIDE, QUICKSTART, STEP
  decision records
- **Test improvements** — planted-answer tests following the existing pattern

## What we do not accept

- Changes that bypass or weaken a human gate
- Changes that allow a number to enter a deliverable without being injected
  from the hashed Findings Store (the Injected-Numbers Rule, Charter §4.1)
- Changes that modify the executor to add archetype-specific business logic
  (use a playbook instead, Charter §4.5)
- Changes that break mypy --strict or ruff clean

## Development setup

```bash
git clone https://github.com/MohdSaifHussain/delivery-engine.git
cd delivery-engine
pip install -e ./analystkit-mcp -e ./opskit-mcp -e ".[dev,ml,docs,stats]"
npm install pptxgenjs docx
python -m pytest -q   # expect: 446 passed, 1 skipped
```

> [!NOTE]
> If the package is not installed editable in your environment (`pip show
> delivery-engine` doesn't point at your checkout), run gates and tests
> with `PYTHONPATH=src` so imports resolve to your working copy instead of
> whatever is on the path, e.g. `PYTHONPATH=src python -m pytest -q`.

## The four gates — all must pass before any commit

```bash
python -m pytest -q                    # tests
python -m mypy src/ --strict           # type checking
python -m ruff check src/ tests/       # linting
python -m ruff format --check src/ tests/   # formatting
```

**Do not submit a PR with failing gates.** CI enforces this — a PR with
red CI will not be reviewed.

## Commit message convention

Follow the pattern used throughout the repo:

```
type(scope): short description

Longer explanation if needed. Reference the charter section if relevant
(e.g. "Charter §4.1 — injected-numbers rule").
```

Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`

## Pull request process

1. Create a branch from `main`: `git checkout -b feature/your-feature`
2. Make your changes — run all four gates
3. Open a PR against `main` using the PR template
4. The maintainer will review against the charter principles
5. Merge only after all gates are green and the maintainer has approved

## The loophole hunt

Before submitting, ask yourself: "What is the sneakiest way this change
could produce a wrong result and not fail a test?" Document your answer
in the test file's docstring. This is a project discipline, not optional.

## Questions

Open a GitHub Issue or Discussion. Do not email.
