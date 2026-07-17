# USER GUIDE — Running Your Project Through the Delivery Engine

This guide is for the analyst who just arrived with a CSV and a
deadline. The [README](README.md) explains what the engine is; the
[PLAYBOOK_SPEC](PLAYBOOK_SPEC.md) defines what is legal; this document
shows you how to get from *your* dataset to a sealed, reviewable
package — in about ten minutes the first time, about one minute after
that.

## Why playbooks (the part nobody wrote down until now)

A playbook is **your team's analysis standard, frozen as a governed,
executable document**. When you write one, you are not configuring a
tool — you are codifying "this is how we audit claims / monitor
transactions / compare segments, every time, with the same gates, in
an order that cannot be skipped." The TOML file *is* the methodology:
reviewable in a pull request, versioned in git, identical for every
analyst who runs it. The engine's job is to make that document
enforceable — data-quality gates before analysis, human approval
before execution, hashed findings behind every number, a manifest
that proves nothing was altered.

Six curated playbooks ship with the engine (see `playbooks/`). They
are archetypes: `universal_audit` runs on almost anything,
`segment_comparison` adds statistical inference, `churn_analysis`
adds a baseline model. Start by running one of those; write your own
when your team's standard differs from the archetype.

## The fastest path: one command

```bash
python run_project.py \
    --source data/claims_q3.csv \
    --goal "Q3 claims quality audit for the compliance review" \
    --playbook universal_audit \
    --rules my_rules.json \
    --approver "Your Name"
```

What happens, in order:

1. **Profile** — AnalystKit profiles every column (types, nulls,
   distincts, DAMA scores).
2. **Compatibility report** — which playbooks fit this dataset and
   why (written to your output directory; read it when unsure which
   playbook to pick).
3. **Plan + Human Gate 1** — the engine proposes the column
   classification; your `--approver` name is recorded against it.
4. **Pre-flight preview** — the terminal shows exactly what will run:
   stages, gates, columns, the pre-registered alpha. Press ENTER to
   proceed or `n` to stop (an audited stop — nothing executes).
   `--yes` skips the pause for automation.
5. **Governed execution** — DQ gates first; analysis stages only
   after they pass; every finding hashed.
6. **The sealed package** — `narrative_report.md` (every figure
   injected from hashed findings, with a Limitations section),
   `handoff_manifest.json` (per-team checks, signature lines),
   `manifest.json` (the hash tree — verify it, and you have verified
   everything), `audit_log.jsonl` (why every gate passed or failed).

Rules files are plain JSON — your data expectations, stated before
the run:

```json
[
  {"column": "claim_id", "rule": "unique"},
  {"column": "claim_id", "rule": "not_null"},
  {"column": "status", "rule": "allowed",
   "values": ["approved", "denied", "pending"]}
]
```

If a playbook validates and you pass no rules, the runner tells you
immediately — before any work runs — rather than failing later.

## Supported formats

Bring the extract you actually have. Every format enters through the
same reader — the one the data-quality gate itself uses — so what the
gate profiled is exactly what the analysis stages see:

| Format | Notes |
|---|---|
| `.csv` | RFC 4180 quoting; unparseable rows recorded, not silently dropped |
| `.parquet` | The warehouse-extract standard. Nested/semi-structured columns (`LIST`, `STRUCT`, `MAP`, and the Variant type that went official in February 2026) are **refused by name** — this engine analyzes tables and will not silently flatten your evidence |
| `.xlsx` | Read via DuckDB's official `excel` extension. Two documented behaviours are disclosed rules: the **first sheet** is read, and numeric cells arrive as `DOUBLE` (so an integer `1` reads as `1.0` in class labels — the statistics are identical, only the label spelling differs). Legacy `.xls` is refused: save as `.xlsx` |
| `.db` / `.sqlite` | Attached read-only; the file must contain **exactly one table**, otherwise the refusal names the tables it found. A column with no single type (SQLite lets one column mix integers and text) is refused rather than analyzed as raw bytes |

Two things worth knowing:

- **Timezones.** A Parquet timestamp *with* a timezone is an instant.
  It is read as UTC, so an event at midnight IST falls on the previous
  UTC day. The engine does not silently re-zone your data — it records
  the note inside the hashed findings so you see it before a reviewer
  does.
- **The fingerprint covers the file.** For a SQLite source that means
  the whole database file, not just the table you analyzed.

## Your first playbook in ten minutes: the generator

When no curated playbook matches your standard, generate a draft:

```bash
python generate_playbook.py \
    --source data/claims_q3.csv \
    --goal "monthly claims audit" \
    --name claims_audit \
    --include math,stats
```

(Omit any flag at a terminal and you will be asked interactively.)

The generator profiles your data and compiles a playbook
**deterministically** — no AI in the path; the same dataset and the
same answers produce the same file, byte for byte. It only offers
stages your data can support (asking for statistical inference
without a binary target column is a refusal, not a broken file), and
it drafts validation rules from the evidence: uniqueness for your id
column, allowed-value sets for low-cardinality columns, values in
their native types. The output lands in `playbooks/generated/`:

- `claims_audit.toml` — the DRAFT playbook, headed by a review notice
- `claims_audit.rules.json` — the evidence-drafted rules

**Then the part that matters: read both files.** The draft is a
proposal, not a decision — a pipeline must never approve its own
rules of engagement. When you have reviewed the stages and gates, run
it, stating so by name:

```bash
python run_project.py \
    --source data/claims_q3.csv \
    --goal "monthly claims audit" \
    --playbook claims_audit \
    --rules playbooks/generated/claims_audit.rules.json \
    --approver "Your Name" \
    --playbook-approved-by "Your Name"
```

Without `--playbook-approved-by`, the runner refuses to execute a
generated draft — that is the point, not an inconvenience. Generated
playbooks also never enter the automatic playbook-matching: they run
only when named explicitly.

## Editing a draft into your team's standard

The generated file is ordinary playbook TOML. Typical first edits:
raise `min_rows`, tighten an allowed-values rule, change the alpha in
`[stats]` (it is pre-registered — approved with the plan, fixed before
any p-value exists), or bump the version and move the file from
`generated/` into `playbooks/` once it has earned curated status.
Every edit is checked against the constitution (rules V1–V15 in
PLAYBOOK_SPEC.md) the moment the file loads — an invalid playbook
refuses to load with the rule number and the reason.

## Reading the package like a reviewer

- Start with `narrative_report.md` — the findings, then **Limitations
  & assumptions** (freshness, independence, detectable-effect sizes,
  possible leakage — read this section first if you read only one).
- `handoff_manifest.json` — what data engineering, QA, compliance,
  and the manager each need to check, with the hash of the evidence
  behind every check. Signatures start `null`; the engine never signs
  for a human.
- `manifest.json` — recompute any file's SHA-256 and compare; the
  `source_fingerprint` proves which exact input produced this
  package.
- `audit_log.jsonl` — the run's full story, including anything that
  was skipped, flagged, or stopped, with reasons.

## One warning worth repeating

If validation reports a mountain of exceptions, that is **evidence** —
of dirty data, or of wrong rules. Diagnose before overriding: a real
production run once "fixed" 1.5 million false exceptions by raising
the gate to 400%, when the true cause was a one-character rule bug
(fixed since — AnalystKit v2.0.2 compares each column type in its own
domain). The `--max-exception-rate` flag exists because judgment is
human; the loud warning it prints exists because silence is how
overrides become habits.
