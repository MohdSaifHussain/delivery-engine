# PaySim fraud audit — 6.36M rows, sealed in 70 seconds

A real run of the Delivery Engine over the PaySim synthetic payment
dataset (6,362,620 rows, 493 MB), using the `churn_analysis` playbook.
The source is not included (it is a public Kaggle dataset); its SHA-256
is recorded in `manifest.json` under `source_fingerprint`.

## What happened

The first attempt was **declined at the pre-flight preview**: the plan
had selected `isFlaggedFraud` — a rule-derived flag that fires on 16 of
6.36M rows — as the model target, because it sorts before `isFraud` in
plan column order. The preview showed this before anything ran. The
source was corrected to exclude the flag column and the run re-planned.

The failure was visible before it became evidence. That is the point of
the engine.

## What the package says

- **5 validation rules, 0 exceptions** across 6,362,620 rows
- **Baseline model** on `isFraud`: ROC-AUC 0.989545, precision 0.913165,
  **recall 0.476376** — an honest result. Accuracy (0.999266) is
  meaningless here: predicting "never fraud" scores 99.87%.
- **Leakage sentinel: silent.** No feature had a near-perfect
  association with the target, so the AUC is earned, not leaked.
- **DAMA scores**: accuracy and timeliness `not scored` — never
  inferred from the dataset alone.

## How this run was produced

Everything here came from the engine's own entry points — no ad-hoc
analysis scripts:

1. **`discover_dataset.py data\Fraud.csv`** — profile, detected values
   for low-cardinality columns, compatibility report. It showed only
   1 of 8 playbooks qualified: no column met the `id_column` bar
   (`nameOrig` has 6,353,307 distinct values across 6,362,620 rows —
   nearly unique, not unique).
2. **A surrogate key added at ingestion** — one DuckDB statement
   (`row_number() OVER ()`), the standard move any pipeline makes.
   Re-running discovery: 6 of 8 playbooks qualified.
3. **`run_project.py`** with `--playbook churn_analysis` and an explicit
   rules file — declined at the preview, source corrected, re-run.
4. No `--max-exception-rate` override was used, and none was needed.

Stack: Python 3.12, DuckDB, scikit-learn (fixed-seed
`LogisticRegression`), pandas, AnalystKit v2.1.0 via MCP. Every
computational stage loads through one reader — the same one the
data-quality gate uses.

## How to verify

Recompute any file's SHA-256 and compare against `manifest.json`.
`audit_log.jsonl` records every stage, gate, and rationale with IST
timestamps. `execution_preview.md` is exactly what was approved.

## Authorship

Delivery Engine designed and governed by Mohd Saif Hussain;
implementation AI-directed (Claude), with every architectural and
statistical decision verified against primary sources before shipping.
This exercise followed the same model: the engineering — the Python
across `sources.py`, `generator.py`, `runner.py` and the stage modules
— was written with Claude under my specification and review, and the
analytical decisions here (declining the run, choosing the target,
excluding the rule-derived flag) were mine. The engine's purpose is
exactly that division: it supplies the evidence, the human supplies the
judgment.
