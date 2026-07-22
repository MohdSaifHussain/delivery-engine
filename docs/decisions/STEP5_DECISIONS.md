# STEP5_DECISIONS.md - decisions made in build step 5

**Date:** 10 July 2026

## 1. Human Gate 2 is content-bound, two-phase

Approving "the rules stage" would be meaningless if the rules could
differ from what was reviewed. The approval therefore quotes the SHA-256
of the exact draft: phase 1 writes rules_draft.json with rules,
per-rule rationales, its hash, and how-to-approve instructions, then
stops; phase 2 re-runs with {"approver": name, "sha256": hash}. A hash
mismatch means a different draft and is refused with the reason stated.
What was reviewed is what runs.

## 2. Drafting is deterministic in v0.2

Only rules the profile findings can justify are drafted (not_null for
fully-complete columns, unique for id-ratio columns, not_future for
timestamp columns), each with a written rationale. No LLM in the
drafting path: the draft must hash identically on every run for
content-bound approval to work. allowed/range drafting needs
value-level findings the profile envelope does not carry - deferred,
documented, not faked.

## 3. Dual rule sources fail closed

A playbook with a rules_draft stage refuses explicit rules at
pre-flight. Silent precedence between an approved draft and supplied
rules would make one of them decorative.

## 4. OpsKit integration: DEFERRED, deliberately

OpsKit v4.1 is a separate published project with its own playbook
engine. Integrating it properly means either (a) wrapping it as a
second MCP server (the analystkit-mcp pattern, build-sequence step 1
applied again) or (b) teaching this engine to call OpsKit playbooks as
kit stages. Both are real builds deserving their own loophole hunts -
not a footnote to step 5. Charter section 9 principle: never two
half-built stages at once. OpsKit integration is the natural step 6,
starting with opskit-mcp.

## 5. Layered defense, observed

During the step 5 loophole hunt, a source swapped AFTER Human Gate 2
approval was caught by the step 4 TOCTOU control (fresh profile vs
plan's classified kinds) at the first gate. Controls built for one
surface covered the next - evidence the architecture composes.
