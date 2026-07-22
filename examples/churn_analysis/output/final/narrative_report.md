# Findings Report

**Goal:** churn analysis for the retention team
**Source:** `C:\Users\mohds\delivery-engine\examples\churn_analysis\WA_Fn-UseC_-Telco-Customer-Churn.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 7,043 rows across 21 columns. 1 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Baseline model (deterministic reference point)

A fixed-seed logistic regression baseline on target `Churn` (stratified 5,282/1,761 split): accuracy 0.805224, precision 0.660622, recall 0.546039, f1 0.59789, roc_auc 0.845464. This is a reference point for human modeling work, not a delivered model.

## Limitations & assumptions

- Accuracy is unscored: it is never inferred from the dataset alone - reconciliation against an authoritative source is a separate, human-initiated step.

Every caveat above is read from the hashed findings - nothing is inferred at writing time, and absent caveats are absent because nothing was recorded, not because nothing was checked.

## Evidence trail

- dq_profile findings: `851b1ea2b88e9cd8c649a7f44e2e51bfd3511a93dfeb5c89707a91cb6f18f8c2`
- dq_validate findings: `b422f2ebd2aad9b20e122af7c3e7efeffc25e94cdbbd6105cf7d6386776396a3`
- baseline findings: `32a8b0ba55be097273b3a915bd394fb1b956f0090789f081232b81a8859b6529`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
