# QUICKSTART — from zero to a verified delivery package

**What this is:** a first-level accelerator and cognitive assistant for
analysts. The engine takes a dataset and a goal, runs deterministic
quality gates, drafts what needs human approval, and produces a
re-performable evidence package — reports, decks, and workpapers where
every number traces to a hash-verified computation. It does **not**
replace your enterprise tooling (your TMS, your PowerBI, your GRC
platform); it hands you a verified, board-ready starting package in
minutes instead of days, with an evidence trail an auditor would
recognise as workpaper discipline.

Works for engineers and non-engineers alike. The SOP below is exact —
copy, paste, run.

---

## 1. Install (once)

Prerequisites: **Python 3.12+**, **Node.js 20+** (for Word/PowerPoint
output), and git. Optional: **LibreOffice** (only for PDF output).

From a terminal (CMD on Windows, any shell on macOS/Linux):

```bash
git clone https://github.com/MohdSaifHussain/delivery-engine.git
cd delivery-engine

# Python packages — one command; analystkit installs automatically
pip install -e ./analystkit-mcp -e ./opskit-mcp -e ".[dev,ml,docs,stats]"

# Node packages — for the docx/pptx builders
npm install pptxgenjs docx
```

Verify the install by running the gates the project itself lives by:

```bash
python -m pytest -q          # expect: all tests pass (pdf may skip
                             # without LibreOffice — that is correct)
```

## 2. See it work (60 seconds)

```bash
python examples/churn_analysis/run_example.py
```

Open `examples/churn_analysis/output/final/` — the narrative report,
the deck, the findings JSON, the audit log, and `manifest.json` (the
hash tree). Re-run the command: the finding hashes match. That is
re-performability, the property everything else here serves.

Three examples ship, one per audience — see
[`examples/README.md`](examples/README.md).

## 3. Run it on YOUR data

Step 1 — profile and check compatibility (the front door):

```python
import json
from pathlib import Path
from analystkit_mcp.tools import tool_profile
from delivery_engine.compatibility import build_compatibility_report

findings = json.loads(tool_profile("path/to/your.csv", None))["findings"]
report = build_compatibility_report(findings, Path("playbooks"),
                                    "path/to/your.csv")
Path("compatibility_report.md").write_text(report)
```

Open `compatibility_report.md`. It states, playbook by playbook, whether
your dataset qualifies and exactly why or why not — the same checks the
planner enforces, so it cannot disagree with what happens next.

Step 2 — plan, approve, run. Copy any example's `run_example.py`,
change the source path and the goal sentence, run it. The goal wording
routes to an archetype; a failed requirement can never be overridden by
wording.

## 4. Make it YOURS — write a playbook

**A new project type is a new TOML file, never engine code.** This is
the core design promise, and it is what makes the engine adaptable to
your team's actual work — audit coverage reviews, regulatory extracts,
clinical data checks, whatever your domain's checklist is.

```bash
# Windows
copy playbooks\data_quality_review.toml playbooks\my_review.toml
# macOS/Linux
cp playbooks/data_quality_review.toml playbooks/my_review.toml
```

Then edit `my_review.toml`:

1. **`[playbook]`** — set `name` (letters/underscores), `version`,
   and a `description`. The description is a **routing surface**: the
   planner matches goal wording against it, so use the words your
   analysts would actually type, and avoid word-for-word overlap with
   other playbooks' descriptions.
2. **`[requirements]`** — what your data must have: `min_rows`,
   `required_kinds` (e.g. `["id_column", "timestamp_column"]`),
   `source_types`. These are enforced, not advisory.
3. **`[[stages]]`** — the workflow, one block per stage, in order.
   Deterministic gates first (`kind = "kit"` with `gate = "must_pass"`),
   AI slots after (`kind = "ai"`), package last. The full schema with
   every rule (V1–V13) is in [`PLAYBOOK_SPEC.md`](PLAYBOOK_SPEC.md).
4. **`[deliverables]`** — pick your output formats:
   `formats = ["markdown", "docx", "pptx", "xlsx"]` (add `"pdf"` if
   LibreOffice is installed). Omit the key for markdown-only.

Validation is automatic and strict: if your TOML violates any
constitutional rule, loading fails with a message naming the rule and
the fix. You cannot ship a malformed playbook by accident.

## 5. Choosing your AI level

The engine is honest about where AI sits, and you control it:

| Level | How | What you get |
|---|---|---|
| **Zero AI** | No `ANTHROPIC_API_KEY` set (the default) | Fully deterministic run. Reports use clean structured templates; every number injected from the store. Nothing degrades silently — this is a first-class mode, and it is how the test suite runs. |
| **Narrative AI** | Set `ANTHROPIC_API_KEY` | AI slots write richer prose in reports and READMEs. The injected-numbers rule still holds: AI **never** computes, estimates, or writes a figure — artifacts are verified after generation and the pipeline stops if a number lacks provenance. |

There is no third level by design. AI authoring numbers, code, or
documents end-to-end is the exact failure mode this engine exists to
prevent.

## 6. The two human gates (you stay the governor)

- **Human Gate 1** — the plan. Nothing executes until a named person
  approves the plan the planner rendered.
- **Human Gate 2** — drafted content. When the engine drafts validation
  rules, the run STOPS and prints a SHA-256. You read the draft, then
  approve that exact hash. Approving a stale or edited draft is refused.
  This is reviewer sign-off, made cryptographic.

## 7. Where things live

| Path | What |
|---|---|
| `playbooks/` | The archetypes — add yours here |
| `examples/` | Three complete runs with committed output |
| `PLAYBOOK_SPEC.md` | The playbook schema and rules V1–V13 |
| `PROJECT_CHARTER.md` | Every design decision, dated and versioned |
| `output/final/manifest.json` (per run) | The hash tree — the proof |

## 8. Troubleshooting

- **`pip install -e .` fails on analystkit** — you are offline or
  GitHub is unreachable; analystkit installs from its public repo.
- **docx/pptx build fails** — run `npm install pptxgenjs docx` in the
  repository root.
- **pdf fails with a LibreOffice message** — install LibreOffice or
  remove `"pdf"` from the playbook's `formats`.
- **"Multiple playbooks qualify equally"** — your goal wording ties two
  descriptions. Reword the goal, or lexically differentiate your
  playbook's description (they are routing surfaces).
