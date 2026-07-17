# STEP 19 DECISIONS — The User Journey

**Date:** 17 July 2026 · **Charter:** amended to v0.15 · **Gates at
close:** 291 tests passed, `ruff` clean, `mypy --strict` zero errors.

## What this step is

Until now the repo was superbly documented for its builder and almost
undocumented for its user — the analyst arriving with a CSV and a
deadline. Step 19 is that user's journey, built as three parts of one
thing: a deterministic **playbook generator** (their standard,
compiled), **one hardened runner** (their execution, governed), and
the **user-facing docs** (their map). Zero engine-core changes — the
entire step lives at the entry-point layer, which is itself a safety
property: nothing here can regress steps 1–18.

## The design positions

1. **The draft principle.** A pipeline must never approve its own
   rules of engagement. The generator's output is a DRAFT — header
   notice, `playbooks/generated/` location, and a runner that refuses
   to execute it without `--playbook-approved-by <name>`. This is the
   step-9 rules_draft pattern (draft → human approval → execution)
   applied to the constitution itself, and it was the agreed
   correction to the original generator spec.

2. **No LLM in the compiler.** Generation is deterministic template
   assembly from the profile plus stated answers: same inputs,
   byte-identical output, proven by test. The constitution is the
   compiler's type-checker — every generated file immediately
   re-loads through `load_playbook` (V1–V15); an invalid draft is
   deleted, never left half-valid on disk.

3. **Feasibility gates the menu.** The generator offers stats/model
   stages only when the profile proves a binary target exists;
   otherwise it refuses with the feasible alternatives named. It
   never writes a playbook it knows cannot run.

4. **Rules are evidence-typed.** Drafted allowed-value rules carry
   values in native types — numerics as numbers, booleans as booleans
   — honoring the AnalystKit v2.0.2 per-dtype comparison contract at
   the source. (The tests captured a good lesson here: DuckDB's
   sniffer reads a yes/no column as BOOLEAN, so its drafted rule
   correctly carries booleans, and the v2.0.2 canonicalization
   validates it cleanly end-to-end.)

5. **One runner, not N scripts.** `run_project.py` replaces the
   per-project `run_<name>.py` copy-paste pattern — the Python
   edition of the spreadsheet-drift failure mode Panko's research
   documents. Config drives it: `--source --goal --playbook --rules
   --approver`. Flags with interactive fallback (scriptable for CI,
   prompted at a terminal); the step-16 preview confirmed by default,
   `--yes` for automation.

6. **Fail before the work, and loudly on overrides.** A
   validate-bearing playbook with no rules exits immediately with the
   remedy stated. Raising `--max-exception-rate` above the engine
   default prints an unmissable warning naming the fraud-run lesson:
   exceptions are evidence — of dirty data or of wrong rules —
   diagnose before overriding.

7. **Generated playbooks never enter the archetype lottery.** The
   planner and compatibility report glob `playbooks/*.toml`
   non-recursively (verified before design); `generated/` is
   invisible to goal-matching by construction and runs only when
   named explicitly.

8. **Docs shape** (per the delegated UX decision): the README gains a
   "Who this is for, and why it matters" section — the sixty-second
   pitch, evidenced by the production catches — and `USER_GUIDE.md`
   carries the ten-minute walkthrough, the never-before-written "why
   playbooks" argument (a team's analysis standard frozen as a
   governed, executable document), and "reading the package like a
   reviewer."

## Loophole hunt — found and closed

- **L1 (rude failure, fixed):** a goal containing a double quote,
  newline, or backslash produced invalid TOML; the compile check
  caught and deleted it (never half-valid — the control held), but
  the user's own words shouldn't kill generation. Goal text is now
  sanitized before entering the TOML string; the words survive, the
  file's validity survives.
- **L4 (live trap, fixed):** a draft named after a curated playbook
  (`universal_audit`) generated fine — and would then be silently
  SHADOWED at run time, because the runner resolves curated names
  first. The user would review one playbook and run another. Now a
  refusal that names the trap.
- **L5 (hardening, fixed):** name resolution accepted arbitrary
  strings joined onto the playbook directory — path fragments could
  smuggle through. Names must now match a strict lowercase slug;
  paths must exist as given.
- **L7 (rude failure, fixed):** an invalid rules JSON file died with
  a raw traceback; now a clean exit showing the line, the message,
  and the expected shape.
- **Process note (the M8 lesson, relearned):** a scripted multi-edit
  died on its own quoting and applied nothing; the hunt fixes were
  re-applied as individually verified edits. Substitutions are
  grep-verified before gates run — now standing practice.

## What was built

- `src/delivery_engine/generator.py` — `compile_playbook`, the
  sanitizer, feasibility menu, evidence-typed rule drafting, the
  shadowing refusal.
- `src/delivery_engine/runner.py` — `main`, strict playbook
  resolution, the draft-approval gate, the early rules check, the
  loud override warning.
- `run_project.py`, `generate_playbook.py` — deliberately thin root
  wrappers (the guide tells users to write their own convenience
  wrappers the same three-line way instead of copy-pasting runners).
- `USER_GUIDE.md`; the README "Who this is for" section.
- `tests/test_step19.py` — 19 tests: constitution-valid drafts,
  feasibility refusals, byte-identical determinism, lottery
  invisibility, evidence-typed rules, the draft-approval gate,
  end-to-end generate→approve→run→seal, interactive fallback, the
  override warning, and the four hunt regressions.

## Open items (declared, not hidden)

- A `--formats` flag on the generator (docx/pptx/xlsx deliverables
  exist in the schema; the generator emits markdown-only v1).
- Promotion tooling: moving an earned draft from `generated/` into
  curated `playbooks/` is currently a manual move + version bump.
- The clean fraud re-run and the DataCo supply-chain run remain
  queued as demonstrations, not obligations.
