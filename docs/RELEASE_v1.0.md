# Delivery Engine v1.0.0 — Release Notes

**Released:** 2026-07-22
**Branch:** `release/v1.0` → merged to `main`
**Tag:** `v1.0.0`
**Built by:** Mohd Saif Hussain, directing Claude as AI collaborator
**Build record:** `PROJECT_CHARTER.md` (Steps 1–23, v0.1 through v0.19)

---

## What this is

The Delivery Engine is a governance-first analytical workflow system.
It encodes professional data-analysis patterns as governed, auditable,
hash-verified workflows: the agent proposes, deterministic tools dispose,
the human governs, and every claim traces to a SHA-256 verified computation.

**This is a portfolio-grade, fully-tested, reproducible tool.** It is not
an enterprise-SLA product. "Production-ready" here means: every capability
is tested, every claim is traceable, the test suite passes in a clean Docker
container, and the build record is public and re-performable.

## How this was built — the AI-collaboration story

This project was built by **Mohd Saif Hussain** — a data annotation and
operations specialist, not a software engineer — directing Claude as an AI
collaborator across 23 documented build steps. The AI wrote code. The human
governed it: setting the scope, approving each step, declining wrong runs
before they became evidence, and holding the governance line throughout.

The build record is public. Every step is timestamped in `PROJECT_CHARTER.md`.
Every capability was proposed, reviewed, tested, and approved by a human
director before it shipped. This is what "agent proposes, human governs" looks
like applied to the build itself, not just the engine's output.

Anyone can replicate this process. The project demonstrates that deep domain
expertise + disciplined AI direction + governance principles produces
professional-grade software — without requiring traditional software engineering
credentials.

## What shipped in v1.0.0

### 7 verified examples covering the analyst's full workday

Every example is a complete, committed output package — open `report.html`
in any browser to see the deterministic visual report, no setup required.

| Example | Dataset | Key result |
|:--|:--|:--|
| `audit_data_quality` | 793-row audit register | Planted null found: owner_team 8.3% (66/793), rendered amber |
| `churn_analysis` | Kaggle Telco, 7,043 rows | ROC-AUC 0.845, recall 0.546, leakage sentinel clean |
| `customer_profiling` | 400-row customer table | Normal fits on spend/tenure, plan entropy 1.585 bits |
| `paysim_fraud` | PaySim, 6,362,620 rows | ROC-AUC 0.989, recall 0.476; wrong-target run declined |
| `segment_comparison` | 300-row signup data | Organic 30% vs paid 60% vs referral 80%, chi2 significant |
| `transaction_monitoring` | 2,000-row card feed | 89.7% completeness amber; real nulls, stale data, concentration found |
| `universal_audit` | 300-row orders feed | Lognormal fit, MAD outliers, entropy; 3 honest refusals-to-overclaim |

### Historical archive

`examples/historical/` preserves earlier packages as the project's growth
record, indexed by a W3C PROV-aligned README. `historical/` at the root
preserves development scripts — not deleted, just organized.

### Docker container

```bash
docker build -t delivery-engine .
docker run --rm delivery-engine   # runs 367/368 tests in a clean container
```

Mirrors CI exactly: Python 3.12 + Node 24. The 1 skipped test requires the
493 MB PaySim source file, which is not committed (by design).

### Test suite

367 tests pass in a clean container. 368 pass locally with the PaySim source
present. CI has been green since Step 4.

## What you need to know to run this

**The goal string is everything.** When you call `make_plan()`, the goal you
pass determines which playbook the engine selects and how it classifies
columns. Be specific: state the analysis type, the audience, and the question.
`"churn analysis for the retention team"` works.
`"analyze my data"` does not.

**The compatibility report is your starting point on a new dataset.**
Run `build_compatibility_report()` first to see which playbooks fit your data.
It tells you which archetypes match before you commit to a run.

**The engine refuses to run into a non-empty output directory.** This is
by design — stale files from a previous run would be certified as this run's
evidence, breaking the hash guarantee. If you see this error, clear the output
folder first (`rmdir /s /q output\final` on Windows) and re-run.

**Human Gate 2 is a content decision, not a technical step.** When the engine
stops at Gate 2, it has drafted validation rules and is waiting for you to read
and approve them. Open `output/phase1/rules_draft.json`, verify the rules make
sense for your domain, and re-run with the SHA-256 hash of the approved draft.
The examples auto-approve for demo purposes — real use requires a human read.

**On Windows:** the engine runs correctly but a few integration quirks apply.
Notepad corrupts Markdown files (use the download-and-copy method). CMD `type`
misrenders UTF-8 em-dashes (use PowerShell for verification). LF/CRLF warnings
on `git add` are benign. Docker Desktop must be running before `docker build`.

**The PaySim example requires the source CSV on your machine.** The 493 MB
file is not committed. Download it from Kaggle
(`blastchar/telco-customer-churn` for Telco; the PaySim source separately)
and place it in `data/`. The engine will find it via the path in the runner.

## Known limitations and v1.1 roadmap

These are deliberate scope decisions, not oversights:

- **Step 21 report visualizes DQ only.** The descriptive math findings
  (distribution fit, outliers, entropy, temporal) from the `universal_audit`
  and `customer_profiling` examples are in `findings/math.json` and the
  narrative report, but not yet charted. Planned for v1.1.
- **Node.js document generation.** The docx/pptx/xlsx stage uses Node
  (pptxgenjs, docx). A pure-Python migration (python-docx, python-pptx,
  openpyxl) is planned for v1.1 — it will simplify the Docker image but
  requires re-proving the determinism guarantee.
- **Timeliness metric.** Shows 0.0% on some examples where "not scored"
  may be more honest. Under investigation.
- **G2/G3 guardrails** (pseudoreplication, minimum detectable effect) do
  not run for model-only playbooks. Planned fix.
- **Human-declared-final.** The engine reports a green state as fact; a
  named human declaring a run final (distinct from approving rules) is a
  planned small feature.

## Verification

Every claim in this release is traceable:

- **Test suite:** `python -m pytest -q` — 367/368 pass in the container
- **Examples:** every `manifest.json` is a SHA-256 hash tree; recompute
  any hash and compare to verify the evidence is unaltered
- **Build record:** `PROJECT_CHARTER.md` — every step timestamped, every
  decision recorded, every amendment numbered
- **Container:** `docker run --rm delivery-engine` — clean environment,
  no local dependencies

The project's thesis is that governance and traceability should be built in,
not added later. This release document is itself an instance of that principle:
every claim above has a verifiable source.
