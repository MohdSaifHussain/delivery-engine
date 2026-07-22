# Churn analysis

**Will this customer leave?** The `churn_analysis` archetype runs a
deterministic, hash-verified baseline model before any custom modeling
begins. Profile the data, validate it, get plan approval at a human
gate, then train a fixed-seed LogisticRegression and seal the metrics
as evidence. Every number in the package traces to a SHA-256 verified
finding.

## The data

Kaggle Telco Customer Churn dataset - 7,043 rows, 21 columns, ~977KB.
Real-world data: 26.5% churn rate. `TotalCharges` is stored as VARCHAR
because 11 rows have blank values - the engine profiles this honestly.
`Churn` (Yes/No) is the target; six other binary columns are present
but the executor uses the first binary_target in column order (a
disclosed deterministic rule) which is `Churn`.

## Run it

From the repository root:

    python examples/churn_analysis/run_example.py

The runner prints the planner's target choice before proceeding and
stops loudly if `Churn` is not first - the lesson from a prior PaySim
run where the wrong target column was selected.

## Results

| Metric | Value |
|:--|:--|
| ROC-AUC | 0.845464 |
| Recall | 0.546039 |
| Precision | 0.660622 |
| Accuracy | 0.805224 |
| Leakage warnings | none |

5,282 training rows / 1,761 test rows. Stratified split, seed 42.
Features: tenure, MonthlyCharges, SeniorCitizen (numeric) and
Contract, InternetService, PaymentMethod and others (categorical).
Leakage sentinel checked every feature against the target; none
crossed the 0.95 threshold.

This is a reference point for human modeling work, not a delivered
model. The metrics are what they are - an honest imperfect baseline
on real data, not a tuned result.

## How to verify this package

Open `output/final/manifest.json`. Recompute the SHA-256 of any file
and compare - matching hashes mean unaltered evidence. `audit_log.jsonl`
records every stage, decision, rationale, and timestamp. The
`findings/baseline.json` carries its own digest and lists every
feature used, the target selection rule, and the leakage check.
