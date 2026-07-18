# PROJECT CHARTER — Delivery Engine

**Version:** 0.16
**Date:** 9 July 2026 (v0.1 founding) · amended 11-18 July 2026 (v0.2 through v0.16)
### Amendment record (v0.16)

Build-sequence step 20 recorded as built:
source adapters, and with them THE SINGLE-READER PRINCIPLE - the
architectural heart of the step. Until now the computational stages
(model, stats, math) read their source with pandas.read_csv while the
kit stages read the same file through AnalystKit's DuckDB loader: two
parsers, one file, a divergence risk carried openly on the register
since the AnalystKit v2.0.x type-boundary bugs (where a mismatch
between two type systems produced 1.5M silent false failures on valid
data). delivery_engine.sources is now the ONLY loading path for the
computational stages, and it parses nothing itself: it delegates to
analystkit.engine.load_source, the very function the profile gate
uses. Whatever the gate saw, the stages see. The risk register item
retires. FORMATS, each rule traced to official documentation and
verified by probe before design (never assumed): .parquet via DuckDB
read_parquet - the Apache Parquet specification is hosted in the
apache/parquet-format repository with the Thrift IDL authoritative -
where nested and semi-structured columns (LIST, STRUCT, MAP, UNION and
the VARIANT type that went official in February 2026) are a LOUD
REFUSAL NAMING THE COLUMNS, never a silent flatten, because this
engine analyzes tables and says so; .xlsx via DuckDB's official excel
extension, whose documented defaults become disclosed rules (first
sheet; numeric cells inferred as DOUBLE), with a missing extension a
loud error naming the INSTALL remedy; .xls refused cleanly with the
remedy, as that extension documents it as unsupported; .db/.sqlite via
ATTACH with the existing single-user-table rule. FORMAT PARITY, the
step's crown-jewel test, is claimed HONESTLY AND SCOPED: the same
logical data in CSV, Parquet and SQLite produces byte-identical stats
and math findings digests, and all four containers agree on math; XLSX
is pinned at the VALUE level instead, because the excel extension's
documented DOUBLE inference makes an integer 1 arrive as 1.0 so the
disclosed class label reads '1.0' - every statistic identical, only
the label spelling differing. Normalizing that away would have hidden
a real, documented container difference; the suite tests what is
actually true instead. Constitutional change: parquet joins
KNOWN_SOURCE_TYPES, and the planner's _source_type gains a parquet
branch - a gap found during wiring, where a .parquet source fell
through to 'csv' and would have passed a CSV-only playbook's
requirement check silently; a requirement that says nothing is worse
than no requirement. The generator's rule-drafting now reads through
the single reader too (drafting rules against a different parser than
the one that validates them is exactly the divergence this step ends),
which makes drafting work for every format for free; universal_audit
and segment_comparison accept the new types. Step-20 hunt closed H1
(a Parquet TIMESTAMP WITH TIME ZONE is an instant rendered in UTC, so
an IST-midnight event lands on the previous UTC day - the instant is
correct but day-level findings would be silently shifted; the engine
does not re-zone anyone's data, it now DISCLOSES the UTC reading
inside the hashed findings) and H2 (SQLite's dynamic typing lets one
column mix integers and text and surfaces as raw bytes; analyzing
untyped bytes would be fabrication, so it is a refusal naming the
column and the CAST remedy), and verified H3 (a zero-row Parquet
loads; the stage's existing feasibility rules decide, with a written
reason) and H4 (a directory source dies in the engine's voice). Two
pre-existing test fixtures were corrected, not the code: they encoded
the OLD pandas view of a yes/no column as strings, while the profile
gate had ALWAYS reported that column BOOLEAN - the fixtures were
recording the divergence, and the swap exposed it. AnalystKit
v2.1.0 ships alongside (75 tests) carrying the same three format
rules at the doorstep. 310 tests.
### Amendment record (v0.15)

Build-sequence step 19 recorded as built:
the user journey - the deterministic playbook generator, the one
project runner, and the user-facing documentation. GENERATOR
(delivery_engine.generator + generate_playbook.py): compiles a DRAFT
playbook for the user's dataset and goal from the AnalystKit profile
and stated requirements - deterministic template assembly with no LLM
in the path (same profile + same answers -> byte-identical output,
proven by test); the constitution is the compiler's type-checker
(every generated file re-loads through load_playbook rules V1-V15; an
invalid draft is deleted, never left half-valid); feasibility gates
the stage menu (stats/model without a binary target is a refusal, not
a playbook that fails later); drafted validation rules are
evidence-typed (numerics as numbers, booleans as booleans - the
AnalystKit v2.0.2 per-dtype contract honored at the source); output
lands in playbooks/generated/, which the planner's non-recursive glob
makes INVISIBLE to the archetype lottery by construction. THE DRAFT
PRINCIPLE, the constitutional heart of the step: a pipeline must
never approve its own rules of engagement - generated playbooks
carry a DRAFT header and the runner refuses to execute them without
--playbook-approved-by <name>, the step-9 rules_draft pattern
(draft -> human approval -> execution) applied to the constitution
itself. RUNNER (delivery_engine.runner + run_project.py): ONE tested,
hardened runner replaces the per-project run_<name>.py copy-paste
pattern - the Python edition of the spreadsheet-drift failure mode
the error literature documents; flags with interactive fallback
(scriptable for CI, prompted at a terminal); the step-16 pre-flight
preview confirmed by default, --yes for automation; validate-bearing
playbooks without rules fail BEFORE any work with the remedy stated;
raising --max-exception-rate above the engine default prints an
unmissable override warning (the July 2026 fraud-run lesson: a 400%
override waved a tool bug into a stakeholder package). Docs:
USER_GUIDE.md (why playbooks - a team's analysis standard frozen as a
governed executable document; first playbook in ten minutes; reading
the package like a reviewer) and the README's "Who this is for"
section. Step-19 hunt closed L1 (hostile goal text - quotes,
newlines, backslashes - sanitized before entering TOML instead of
killing generation), L4 (a draft named after a curated playbook would
be silently SHADOWED at resolution - review one playbook, run
another; now a refusal naming the trap), L5 (path fragments smuggled
through name resolution - names must match a strict slug), and L7
(invalid rules JSON is a clean exit with the expected shape shown,
not a raw traceback). Zero engine-core changes: the entire step is
entry-point layer, which is itself a safety property. 291 tests.
### Amendment record (v0.14)

Build-sequence step 18 recorded as built:
the Analyst-Error Guardrails - six controls, each traceable to
published research on how analysts actually fail, several motivated by
failures observed first-hand in this engine's own production runs.
G1 LEAKAGE SENTINEL (model stage): per-feature association with the
target (Cramér's V for categoricals by the textbook Pearson formula,
absolute point-biserial for numerics); associations at or above a
fixed disclosed threshold are recorded as possible_target_leakage in
the hashed findings - motivated by the July 2026 fraud run where a
post-hoc label column (fraud_type) rode into the baseline and produced
ROC-AUC 1.0. The warning NEVER gates: near-perfect association can be
legitimate, so the judgment stays human; the engine's job is to make
the pattern impossible to miss. G2 PSEUDOREPLICATION DISCLOSURE (stats
stage): unaccounted non-independence of data points produces incorrect
p-values (Forstmeier, Wagenmakers & Parker 2017); a deterministic,
disclosed scan over the same hashed profile the human approved flags
high-cardinality grouping columns outside the analysis (many rows per
entity - the 500k-transactions-from-5k-cardholders pattern) and the
findings state plainly that p-values are not cluster-robust. G3
MINIMUM DETECTABLE EFFECT (stats stage): every two-group test carries
its MDE at the pre-registered alpha and a declared power constant -
Cohen's h closed form for proportions (Cohen, Statistical Power
Analysis, 1988), the normal-approximation rank-biserial form for
Mann-Whitney - so "not significant" can never again be silently read
as "no effect"; low-power analyses inflate both false negatives and
false positives. G4 ANALYST-BIAS CHECKLIST (handoff manifest): three
human-judgment questions (selection/survivorship, denominators, mixed
granularity) that no algorithm can answer from the data alone - the
spreadsheet-error literature (Panko; EuSpRIG) is unanimous that
self-checking does not catch what structured inspection does, with
field audits finding errors in the great majority of operational
spreadsheets and no error-rate difference between novices and
experienced developers. G5 SOURCE FINGERPRINT (manifest + audit): the
SHA-256 and byte size of the INPUT dataset, streamed in 64 KB chunks,
recorded before any stage runs - closing the lineage gap named among
critical 2026 governance risks (Info-Tech Data Priorities 2026; 2026
AI-governance literature on lineage); "the data changed" is now a
provable claim, and re-performability no longer assumes the same
source, it verifies it. G6 LIMITATIONS & ASSUMPTIONS SECTION
(narrative report): the 2026 anti-hallucination control - communicate
uncertainty and limitations instead of presenting outputs as absolute
facts; assembled with NO new computation from caveats already recorded
in hashed findings (DAMA timeliness below 1, unscored accuracy,
independence warnings, MDE presence, skip counts, Cochran validity
violations, leakage warnings), with the standing rule that absent
caveats are absent because nothing was recorded, never fabricated and
never suppressed. Step-18 hunt closed H5: a source file that vanishes
between Human Gate 1 and execution is an audited ExecutionStopped in
the engine's own voice, not a raw FileNotFoundError traceback. 272
tests.
### Amendment record (v0.13)

Build-sequence step 17 recorded as built:
the universal descriptive math layer. A new stage kind `math`
(delivery_engine.mathkit) answers "what is the SHAPE of every column?"
- requiring no target, so it runs on any dataset the planner can
classify. Methods fixed and traced to primary sources: bias-adjusted
sample skewness G1 and excess kurtosis G2 (Joanes & Gill 1998, the
scipy bias=False estimators), t-intervals for the mean (NIST/SEMATECH
e-Handbook 7.2.2.1, 95% a declared constant, small-n noted), empirical
tail percentiles p95/p99 with the numpy linear method pinned (the
historical-simulation VaR levels in risk contexts - Jorion), robust
outliers by the MAD modified z-score with the 0.6745 scale and 3.5
threshold (Iglewicz & Hoban 1993; NIST) where MAD == 0 is a declared
skip rather than a division by zero, Shannon entropy in bits with
normalized entropy and a fixed disclosed 1% rare-category cutoff
(Shannon 1948), and temporal structure (max day gap; daily-count trend
via linregress). THE DESIGN FIX OF THE STEP: distribution fitting with
the estimated-parameter correction - a KS p-value is INVALID when the
tested distribution's parameters were estimated from the same sample
(Lilliefors 1967), so normality and lognormality carry proper
Lilliefors p-values (statsmodels), while the Weibull candidate reports
its fitted parameters and KS DISTANCE EXPLICITLY WITHOUT A P-VALUE,
reason recorded in the findings; best fit is the smallest KS distance,
a disclosed selection rule and not a significance claim.
CONSTITUTIONAL POSITIONS (new rule V15): math_checks is declared from
a fixed list (numeric_shape, outliers, distribution_fit,
categorical_entropy, temporal, all) - the engine never improvises a
method; every threshold is a fixed constant DISCLOSED INSIDE THE
HASHED FINDINGS, chosen in code and never after seeing results;
columns come from the plan approved at Human Gate 1, id columns
excluded; descriptive values never gate - feasibility does; skips
carry written reasons; an all-skipped stage is a feasibility failure;
6-decimal rounding (the step-10 contract). New archetype
universal_audit (requires only an id column); the narrative report
gains a Distribution & shape section (injected numbers only - the
claims scan caught the un-injected digits in the literal tokens "p95"
and "p99" before the end-to-end test could pass, the charter working
as designed); the handoff manifest's QA section gains a math
spot-check bound to the sealed digest. Step-17 hunt closed M2 (a
two-valued 0/1 column is a category wearing a number's clothes -
excluded from the numeric suite with the exclusion disclosed;
inference on it belongs to the stats stage), M4 (NaN accounting
extended to categorical and temporal findings), and M7 (a failed
Weibull MLE fit is a recorded absence pinned at the worst possible
distance so it can never be selected best fit, never a crash and never
silent). 256 tests.
### Amendment record (v0.12)

Build-sequence step 16 recorded as built:
the pre-flight preview and the multi-team handoff manifest. PREVIEW
(delivery_engine.preview): before any stage runs, the executor renders
a human-readable summary of exactly what is about to execute - stages
in order, gates split by mode, the approved column classification,
requirement checks, the pre-registered alpha where a stats stage
exists, deliverables and formats - as a PURE FUNCTION of the loaded
playbook and the approved plan, the same two documents the executor
runs from; there is no third source of truth to drift. The engine core
stays NON-INTERACTIVE by design (a library that blocks on stdin hangs
every test, CI job, and scheduled run): interactivity is a callback -
run(..., preview_confirm=...) - supplied only by entry points with a
human at the terminal (delivery_engine.preview.prompt_confirmation).
Declining stops the run with an audit entry before anything executes;
the rendered preview is written to execution_preview.md either way and
hashed by the manifest, so what the human was shown is itself
evidence. HANDOFF (delivery_engine.handoff): at package time the
engine writes handoff_manifest.json - a structured receipt with
per-team checks (data engineering, QA, compliance, manager) generated
from what the pipeline ACTUALLY ran, each check carrying the SHA-256
of the sealed findings it references; signature fields start null and
the engine never signs for a human; the file is written before
manifest.json so the package manifest hashes it and a forged signature
fails verification. Step-16 hunt: H1 (real bug, fixed) - the
data-engineering row-count check initially read a findings key that
does not exist and would have said "matches None"; the engine never
fabricates a check around a number it does not have - the count now
comes from the per-column totals in the hashed profile, and when those
disagree or are absent no row-count check is written. H4: a declined
run keeps its preview and audit entry (stopped runs keep their
evidence, the step-9 rule), so the decline message directs the human
to a fresh output directory and the stale-files refusal enforces it.
H8: the interactive helper is itself under test via monkeypatched
stdin. 227 tests.
### Amendment record (v0.11)

Build-sequence step 15 recorded as built:
the statistical evidence layer. A new stage kind `stats`
(delivery_engine.stats) upgrades the engine's findings from DESCRIPTIVE
(counts, rates) to INFERENTIAL (is a difference real; how uncertain is
a rate) - deterministically, hashed, narrated-never-computed by AI.
Methods fixed and traced to primary sources: Wilson score intervals
(Brown, Cai & DasGupta 2001; NIST/SEMATECH e-Handbook 7.2.4.1;
statsmodels), Fisher exact for 2x2 tables (scipy), Pearson chi-square
correction=False for r x c with Cochran's-rule validity flags
(NIST/SEMATECH), Mann-Whitney U for numeric two-group comparison with
the parametric t-test REFUSED in v1 (normality is an assumption the
engine cannot certify - the OpsKit Simpson's-paradox refusal posture),
effect sizes ALWAYS alongside p-values (ASA Statement on p-values 2016,
principle 5: Cramer's V, rank-biserial r), and Benjamini-Hochberg FDR
control across every test a stage runs (Benjamini & Hochberg 1995).
CONSTITUTIONAL POSITIONS (new rule V14): stat_test is declared from a
fixed list - the engine never improvises a method; alpha is
PRE-REGISTERED in the playbook's [stats] table, approved at Human Gate
1 before any p-value exists, range-checked, and refused when declared
with no stats stage to apply it to. SIGNIFICANCE NEVER GATES - the
step-10 principle extended: feasibility failures stop a must_pass
stage; p-values never do, because a pipeline that stops or proceeds on
significance is p-hacking machinery. Skips are recorded with reasons,
never silent; an all-skipped stage is a feasibility failure. Findings
rounded to 6 decimals (the step-10 contract). New archetype
segment_comparison; narrative report gains a Statistical evidence
section (injected numbers only). Step-15 loophole hunt closed L4
(target-as-its-own-feature crashed deep in pandas - now a clean
refusal, with duplicate-feature refusal alongside), and verified: alpha
is live not decorative, NaN drops are counted, Wilson bounds hold in
[0,1] at k=0 extremes where Wald fails, findings are row-order
invariant, significance flags mirror BH-adjusted values at the
boundary. 212 tests.
### Amendment record (v0.10)

Build-sequence step 14 recorded as built:
the developer-experience layer, positioned from a real-world job
description (Senior Analyst, GBM Audit COO, Scotiabank). Three parts:
(1) the Playbook Compatibility Report — a deterministic pre-flight
module (delivery_engine.compatibility) that REUSES the planner's own
classify_columns and check_requirements, so the report can never
disagree with the planner; it informs, never gates. (2) /examples/ —
three complete end-to-end runs with committed real output, one per
audience: transaction monitoring (compliance), churn with baseline
(business analytics; planted signal reproduces roc_auc 1.0), audit
data quality (internal audit — the workpaper-discipline story).
transaction_monitoring_review bumped to v1.1.0 declaring formats
(pdf deliberately excluded from defaults: it hard-requires LibreOffice
and a must-produce format stops the pipeline when its tool is absent).
(3) QUICKSTART.md — the SOP for engineers and non-engineers: install,
first run, your-own-data, write-your-own-playbook, and the explicit
AI-level contract (zero-AI is a first-class mode; narrative-AI never
writes numbers; no third level by design). POSITIONING made explicit in
the docs: a first-level accelerator and cognitive assistant with
workpaper discipline — not a replacement for enterprise tooling.
### Amendment record (v0.9)

Build-sequence step 13 recorded as built:
deterministic multi-format deliverables (Word, PowerPoint, Excel, PDF)
declared per-playbook via [deliverables] formats (schema rule V13,
backward-compatible — absent key defaults to markdown). CRITICAL DESIGN
DECISION documented: the Anthropic document skills are used as
best-practice recipes for their underlying deterministic libraries
(pptxgenjs, docx-js, openpyxl, LibreOffice), NOT via the Claude API's
authoring mode — because API authoring would let AI write numbers,
violating charter 4.1. Every figure in every format remains injected from
the hashed Findings Store. New content-verification stage: a HARD gate
re-reads each produced document and stops the pipeline if any
store-sourced number is missing; a SOFT check warns on absent prose
sections. Format-aware verification: detail formats (docx/xlsx/pdf) carry
full column detail; decks (pptx) carry summary numbers — a correct
professional distinction. The .json/.md evidence layer is preserved
underneath; documents are additive.
### Amendment record (v0.8)

Build-sequence step 12 recorded as built:
GitHub Actions CI (ruff + mypy strict + pytest) mirroring the local gates
exactly, plus a root README with CI badge. This closes the LAST open item
in Section 10's definition of done — the v0.1 thin slice is now complete
by its own stated criteria. CI does MORE than the local run, not less:
markitdown is installed so the one PPT content-scan test executes instead
of skipping (156 passed, 0 skipped from a clean checkout). The workflow
was validated in a fresh-venv clean-checkout simulation before being
committed, not merely written.
### Amendment record (v0.7)

Build-sequence step 11 recorded as built:
the deterministic PPT builder. CONSCIOUS DESIGN DECISION: the slot is
named PRESENTATION under the AI stage kind, but it generates NO AI
content. Every number on every slide is a Python literal from the
Findings Store. The generator script is the auditable artifact; its
SHA-256 (computed on a path-normalised form) is the integrity seal in
the audit trail. pptxgenjs embeds a creation timestamp in the OOXML
package so the binary .pptx bytes legitimately differ across runs, but
the script hash proves content identity — a tool limitation, not an
engine failure. Section 11's artifact box is now complete.
### Amendment record (v0.6)

Build-sequence step 10 recorded as built: the
deterministic baseline model stage. CONSCIOUS AMENDMENT of the original
architecture: the diagram placed "Baseline Model" under bounded AI slots
("code generated, run deterministically"); v1 goes further - NO code is
generated. Training a baseline over planner-classified columns is a
deterministic problem wearing an AI costume (the 4.6 lesson, applied
again), and the strongest sandbox is executing no generated code at all.
Section 11's sandboxing question is answered by deferral: custom
AI-authored training code, if ever needed, arrives behind Human Gate 2.
Declared stage semantics: metric values never gate; training feasibility
does. Target selection is disclosed deterministic (first binary candidate
in the plan order approved at Human Gate 1, all candidates recorded in
hashed findings).
### Amendment record (v0.5)

Build-sequence step 9 recorded as built: the
transaction_monitoring_review archetype, the first playbook composing the
full system (both kits, Human Gate 2, dual narratives) with ZERO engine
changes - the playbooks-not-code principle (4.5) demonstrated at full
scale. Design lesson recorded: the planner's tie-break is lexical, so
archetype descriptions are part of the routing contract; descriptions
must be lexically differentiated, and routing regression tests pin the
contract.
### Amendment record (v0.4)

Build-sequence step 8 recorded as built: the
ops_report AI slot renders OpsKit findings into a narrative under the
injected-numbers rule. The rule was extended, not weakened: the injector
gained inject_from_findings, which proves a quoted string exists verbatim
inside the stage's hashed findings before registering its numeric tokens -
provenance by construction. Section 8's deferred list updated accordingly.
### Amendment record (v0.3)

Build-sequence step 7 recorded as built:
OpsKit wired into the engine as a kit stage (tool `opskit_run_playbook`,
schema rule V11, archetype ops_review), with envelope seal verification
and declared insight-vs-unfitness gate semantics. Section 8's deferred
list updated: OpsKit engine wiring is done; ops narrative artifacts
(report/readme built from OpsKit findings) are the named next deferral.
### Amendment record (v0.2)

Build-sequence steps 5 and 6 recorded as built.
Section 8's deferred list updated: OpsKit integration has begun via
opskit-mcp; engine-stage wiring is the explicitly remaining deferred piece.
Section 9 updated with the as-built sequence. Section 4.9 added: the
layered-defense observation from the step 5 loophole hunt, recorded as
charter-level evidence that the architecture composes.
**Owner:** Mohd Saif Hussain — designer, specifier, governor
**Status:** Approved architecture, pre-build
**Companion artifact:** delivery-engine-architecture.png (the one-page system diagram)

This document is the constitution of the Delivery Engine project. Any session,
any tool, any collaborator working on this project starts here. Where a future
decision conflicts with this charter, the charter is either consciously amended
(with a version bump and a dated note) or the decision is wrong.

---

## 1. Problem statement

Anyone who has to deliver a data project — analyst, data scientist, consultant,
freelancer, student, internal ops professional — spends the first 60–70% of the
project lifecycle on repeatable scaffolding: understanding the dataset,
validating quality, exploring, documenting, building a baseline, packaging the
deliverables. This work follows recognizable professional patterns, yet is
redone manually from scratch on every project.

Meanwhile, 2026's agentic AI tools chain LLM agents to generate these artifacts
fast — but unverifiably. They fabricate numbers, cannot produce evidence for
their claims, and their output cannot be re-performed. Fast and untrustworthy.

The gap in the market: nobody is building the version where the delivered
project **proves itself** — where every number traces to a deterministic
computation, every AI decision is logged with its rationale, and a reviewer
who was never in the room can re-perform any stage and get the same result.

## 2. The one-line thesis

**Encode professional project patterns as executable, governed workflows:
agent proposes, deterministic tools dispose, human governs, every claim
traceable.**

The Delivery Engine takes a dataset plus a plain-English goal and produces a
complete, professional project package — notebook, report, presentation,
workpaper, README, repo structure — where every artifact meets an evidence
standard, not just a plausibility standard.

## 3. Lineage — what this builds on

This project is the third level of one consistent idea across the owner's
portfolio:

- **AnalystKit** (v2.0, live on GitHub) encoded the data quality pattern:
  DAMA six dimensions, planted-answer testing, workpaper discipline, the
  deterministic-findings → SHA-256 → AI-narrative audit boundary.
- **OpsKit** (v4.1) encoded the operational analysis pattern — and invented
  the mechanism this project scales up: **domain patterns declared as TOML
  playbooks, executed by a small, tested, unchanging engine.**
- **The Delivery Engine** encodes the pattern of patterns: how a professional
  turns a dataset and a goal into a finished deliverable.

Don't automate tasks. Automate the workflow that connects tasks into a
deliverable.

## 4. Non-negotiable architecture principles

These are not preferences. Each is stated with its rationale. Violating any of
them means the build has failed regardless of how well it demos.

### 4.1 The injected-numbers rule
The AI never computes, estimates, or writes a number. Every figure in every
generated artifact is injected from the Findings Store and carries its hash.
AI writes prose, structure, and code — never facts.
*Rationale:* a report where the AI wrote "churn is 23.4%" and nobody verified
it is worse than no report, because it looks professional. This rule must be
architecturally enforced (the artifact templating layer only accepts numbers
from the store), not enforced by prompt instruction.

### 4.2 Deterministic quality gates
AnalystKit and OpsKit run as must-pass gates. A failed gate stops the
pipeline. No AI stage may override, soften, or route around a failed gate.
*Rationale:* a control that cannot fail is not a control.

### 4.3 The Findings Store is the audit boundary
All deterministic outputs land in canonical JSON (sort_keys), SHA-256 hashed.
These are the only numbers any AI stage may consume. Same findings → same
hash → re-performable evidence.
*Rationale:* pattern proven at small scale in AnalystKit v2.0's --ai flag.
This project scales it up; it does not reinvent it.

### 4.4 Two human gates, architecturally placed
- **Human Gate 1:** the Planner's selected playbook and execution plan are
  shown for approval before anything executes.
- **Human Gate 2:** any AI-authored content that would feed back into the
  deterministic layer (generated validation rules, feature definitions, model
  choices) requires explicit human approval before use.
*Rationale:* Gate 2 exists because AI-authored rules feeding the deterministic
layer is the one place the audit boundary could be poisoned. This is the
single highest-risk point in the architecture.

### 4.5 Playbooks, not code
Project archetypes are declared as TOML playbooks. Adding a new project type
means writing a new playbook — never modifying the engine. The engine stays
small, tested, gated; the pattern library grows.
*Rationale:* the OpsKit v4 principle. Also the quiet biggest idea: users can
encode THEIR OWN professional patterns as playbooks. The product is not just
our patterns — it is a format for professionals to encode theirs.

### 4.6 The planner is 80% deterministic, 20% LLM
Project-type classification (tabular? binary target? timestamps? which
archetype's requirements are met?) is decided by rules over the AnalystKit
profile output. The LLM resolves only genuine ambiguity in goal wording, and
its decision plus rationale is logged. The LLM never overrides a failed
requirements check.
*Rationale:* "decide the project type" is a deterministic problem wearing an
AI costume. Rules are cheaper, reliable, and testable.

### 4.7 The stage contract (every stage, no exceptions)
1. Declared inputs (from the playbook)
2. Execution (kit command or bounded AI slot)
3. Output hashed
4. Gate evaluated (pass / stop / human)
5. Audit entry written (append-only, IST-timestamped)
6. Next stage

### 4.8 The success test (the definition of done for the whole system)
A reviewer who was never in the room can re-perform any stage from the
delivery package alone and get the same hashes. If they can, it is evidence.
If they cannot, it is just output.

### 4.9 Layered defense, observed (recorded v0.2)
During the step 5 loophole hunt, a source swapped AFTER Human Gate 2
approval was caught by the step 4 TOCTOU control (fresh profile compared
against the plan's classified kinds) at the first gate. A control built for
one surface covered the next. This is recorded as evidence that the
architecture composes: gates and seals designed independently protect each
other's blind spots. Future stages preserve this property by sealing
declared inputs before execution; the opskit-mcp wrapper applies the same
ordering, taking the source hash before the engine opens the file.

## 5. What this is NOT (anti-scope)

- **Not an assignment-submission machine.** Positioning is: "accelerates
  project creation while exposing every step, every decision, every rationale."
  Students can learn from it; it is not optimized for submitting work without
  understanding it. This is both an ethical position and an adoption
  requirement (institutions increasingly reject opaque AI submissions).
- **Not a replacement for professional judgment.** It automates the first
  60–70% of the lifecycle (setup, understanding, validation, exploration,
  documentation, baseline, packaging). The remaining 30–40% — iterative
  experimentation, domain feature engineering, business judgment — is
  explicitly the human's.
- **Not image / audio / deep-learning territory in v1.** The deterministic
  kits are built for structured/tabular data. That is the lane.
- **Not a pile of chained agents.** Anyone can chain twelve agents; LangChain
  tutorials do it. The differentiator is the evidence standard. If a build
  decision trades evidence for demo-speed, the decision is wrong.

## 6. Standards register — official sources only

Every component is designed against a primary source, fetched and verified at
build time (the AnalystKit v2.0 discipline). No generic blog posts.

| Component | Governing source |
|---|---|
| Tool exposure (kits as agent tools) | Model Context Protocol (MCP) specification — modelcontextprotocol.io |
| Agent orchestration patterns | Anthropic official agent design documentation / docs.claude.com |
| AI API usage | Official Anthropic Python SDK documentation |
| Data quality gates | DAMA-DMBOK six dimensions (as implemented in AnalystKit) |
| Deterministic engine | DuckDB official documentation (identifiers, prepared statements, READ_ONLY attach, secrets warnings) |
| Packaging & layout | PyPA Python Packaging User Guide (src layout, PEP 621) |
| Python stdlib behaviors | docs.python.org only |
| Project lifecycle language | PMBOK (charter, deliverables, gates) — used for vocabulary, not bureaucracy |
| Typing / language standards | Python 3.12+, PEP 695, mypy --strict, ruff |

Rule: if a component's design cannot cite its source, it does not ship.

## 7. Engineering standards (inherited, non-negotiable)

The AnalystKit v2.0 bar applies to every component:
- mypy --strict, zero errors; py.typed marker
- ruff clean (E, F, W, I, N, UP, B, C4, SIM, RUF)
- pytest on the planted-answer principle: fixtures contain known issues,
  tests verify exactly those are found
- Adversarial loophole hunts before any version ships; every fix lands with
  a regression test proving the old failure
- Frozen slots dataclasses, StrEnum, timezone-aware IST, atomic writes,
  no side effects on import, clean AnalystKitError-style errors (a user
  mistake never earns a raw traceback)
- src layout; CLI/dispatch layers contain zero logic
- GitHub Actions CI (ruff + mypy strict + pytest) green from first commit
- Development framing: designed, specified, and governed by Mohd Saif
  Hussain; implementation AI-directed; every architectural and security
  decision human-made and source-verified

## 8. Scope of the thin slice (v0.1) — the first build

One vertical slice, end to end, every gate real:

1. **One archetype:** churn_analysis (most universally understood)
2. **Planner:** deterministic matching over AnalystKit profile + requirements
   check against the playbook; LLM only for goal-wording ambiguity; Human
   Gate 1 approval
3. **Deterministic gates:** AnalystKit profile + validate (must_pass);
   findings → Findings Store (canonical JSON + SHA-256)
4. **One AI stage:** EDA notebook generation under the injected-numbers rule
5. **Documentation stage:** README + short report, narrative from findings
   JSON only
6. **Packaging stage:** professional repo structure + audit log + manifest
   (hash tree of the entire package)

**Explicitly deferred past v0.1:** model training stage, PPT generation,
OpsKit integration, feature-engineering agent, dashboard agent, multiple
archetypes, user-authored playbook validation tooling.

*(v0.2 status of this list: a second archetype and the rules_draft slot with
Human Gate 2 landed in step 5. OpsKit integration began in step 6 with
opskit-mcp, exposing OpsKit v4.1 as the second MCP server with hashed
envelopes, completed its engine wiring in step 7 (the ops_review
archetype), and gained narrative artifacts in step 8 (the ops_report
slot). The OpsKit integration track is complete; opskit_drill engine
wiring remains available as a future enhancement when an artifact
consumes its structured output. Model training, PPT
generation, feature-engineering agent, dashboard agent, and user-authored
playbook validation tooling remain deferred.)*

## 9. Build sequence

1. **MCP wrappers first.** Expose AnalystKit (and later OpsKit) commands as
   MCP servers per the official specification. Small build, standards-based,
   independently useful, and the foundation the engine calls through.
2. **Playbook schema.** The TOML format is the constitution of the runtime
   system — designed with charter-level rigor before the engine exists.
3. **Planner** (deterministic core + logged LLM ambiguity resolution +
   Human Gate 1).
4. **Thin slice** (Section 8) working end to end with the audit trail.
5. **Expansion:** one stage or one playbook at a time, each with its own
   tests and its own loophole hunt. Never two half-built stages at once.

**As built (v0.2):**

| Step | Delivered | Gates at completion |
|---|---|---|
| 1 | analystkit-mcp: AnalystKit tools via MCP, hashed findings envelope | green |
| 2 | Playbook schema: constitutional rules V1-V10, churn archetype | green |
| 3 | Planner: 80/20 deterministic/LLM, Human Gate 1 | green |
| 4 | Executor: stage contract, Findings Store, audit log, first package | green |
| 5 | rules_draft slot with content-bound Human Gate 2 (approval quotes the draft's SHA-256), second archetype; a genuine AnalystKit bug (BOOLEAN sniffing) found by integration, fixed upstream | 95/95 tests, mypy strict, ruff |
| 6 | opskit-mcp: OpsKit v4.1 as the second MCP server; four tools, hashed envelopes, stdout isolation per MCP stdio spec, explicit-only config with hashing, source sealed before execution, structured Simpson's refusal, eager metric validation; two loopholes found and fixed with regression tests; live protocol test against the official MCP client | 29/29 tests, mypy strict, ruff |

| 7 | OpsKit engine wiring: `opskit_run_playbook` kit tool with schema rule V11 (`ops_playbook` key), the ops_review archetype, envelope seal verification (schema check, hash recomputation, post-seal shape validation), declared insight-vs-unfitness gate semantics; two loopholes found and fixed with regression tests | 69/69 runnable tests, mypy strict, ruff; full-suite certification on the private repo |

| 8 | ops_report AI slot: OpsKit findings rendered under the injected-numbers rule via inject_from_findings (verbatim provenance proven before token registration); ops_review archetype to v1.1.0; two loopholes found and fixed with regression tests | 119/119, mypy strict, ruff |

| 9 | transaction_monitoring_review archetype: both kits + Human Gate 2 + dual narratives composed in one playbook, zero engine changes; lexical routing collision found during build, fixed in the archetype description, pinned with regression tests | 127/127, mypy strict, ruff |

| 10 | Deterministic baseline model stage: StageKind.MODEL + V12, fixed-seed sklearn pipeline per official controlling-randomness guidance, metrics hashed into the store, optional report section, churn archetype v1.1.0, [ml] extra; three loopholes found (null crash, id leakage, silent target pick) - two fixed fail-closed, one fixed as disclosed deterministic selection after the refusal design was rejected as over-engineering | 145/145, mypy strict, ruff |

| 11 | Deterministic PPT builder: PRESENTATION slot, pptxgenjs 4.0.1, 7-slide deck (title, overview, profile, validation, ops, baseline, evidence trail), path-normalised script hash as integrity seal; three loopholes found — unused import (ruff fix), f-string leak into JS (clean rewrite), output-path in hash (content-hash sentinel); plus the byte-reproducibility finding recorded honestly as a tool limitation | 156/156, mypy strict, ruff |

| 12 | GitHub Actions CI (ruff + mypy strict + pytest) mirroring local gates; root README with CI badge; validated in a clean-checkout fresh-venv simulation before commit — 156 passed 0 skipped (markitdown enabled in CI) | 156/156, mypy strict, ruff, CI green |

**v0.1 thin slice: COMPLETE by Section 10's definition of done (v0.8).**
Every original box on the architecture diagram has real, tested,
re-performable code behind it, and CI proves it from a clean checkout.
Further work is expansion (new archetypes = new TOML, no engine change),
not foundational build.

Standing archetype-authoring rule (from step 9): a new playbook's
description is a routing surface. Before adding an archetype, check its
description tokens against the library for collisions, and land it with
routing regression tests for its own goal AND the goals of its nearest
lexical neighbors.

## 10. Success criteria for v0.1

- The re-performability test (4.8) passes on the churn slice: a second run
  on the same inputs reproduces the same finding hashes, and the manifest
  verifies.
- Zero numbers in any generated artifact that do not trace to the Findings
  Store (verified by test, not by inspection).
- A failed AnalystKit gate stops the pipeline (verified by planted bad data).
- Human Gates 1 and 2 cannot be bypassed by any input (verified by test).
- All three quality gates green (ruff, mypy strict, pytest) with CI.
  ✅ SATISFIED (v0.8, step 12): GitHub Actions runs all three on every
  push and pull request, mirroring the local gates and validated from a
  clean checkout.
- The audit log alone is sufficient to reconstruct what happened and why.

## 11. Open questions (decided later, consciously)

- Engine runtime: single Python package vs. orchestrator framework.
  Bias: own small engine (playbook executor), calling kits via MCP —
  consistent with "the engine stays small."
- Notebook generation format: .ipynb JSON directly vs. jupytext .py.
  Decide against official Jupyter format documentation.
- Where model-training code executes in later versions (sandboxing question).
- Naming. Working title: Delivery Engine. Candidates preserved: AI Project
  Workflow Engine. Decide before first public commit.
- Licensing (MIT default per portfolio precedent; revisit if this becomes
  a product rather than a portfolio piece).

## 12. How to resume this project in any new session

Upload two files: **PROJECT_CHARTER.md** (this document) and
**delivery-engine-architecture.png**. State which build-sequence step is
active. That is the complete context package. Any decision made in a session
that amends this charter gets written back into it with a version bump.

---

*A stage that cannot fail is not a gate. A number without a hash does not
enter a deliverable. A project that cannot be re-performed is just output.*
