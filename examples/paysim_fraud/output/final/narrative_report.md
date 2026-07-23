# Findings Report

**Goal:** churn analysis and binary classification baseline for fraud detection: predict isFraud using transaction features
**Source:** `C:\Users\mohds\delivery-engine\data\fraud_model.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 6,362,620 rows across 11 columns. 4 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Baseline model (deterministic reference point)

A fixed-seed logistic regression baseline on target `isFraud` (stratified 4,771,965/1,590,655 split): accuracy 0.999266, precision 0.913165, recall 0.476376, f1 0.62612, roc_auc 0.989545. This is a reference point for human modeling work, not a delivered model.

## Limitations & assumptions

- Accuracy is unscored: it is never inferred from the dataset alone - reconciliation against an authoritative source is a separate, human-initiated step.

Every caveat above is read from the hashed findings - nothing is inferred at writing time, and absent caveats are absent because nothing was recorded, not because nothing was checked.

## Evidence trail

- dq_profile findings: `4e9922d8774997e6c7ccd3e151cd9d82290e6e93213d2cc58a81f4386523c41e`
- dq_validate findings: `61f85ad8b78327eb7e9a19a0d87c7f491037b97558cbd224e582073d066aa853`
- baseline findings: `2abcfa8367583c954578bb8ad17110c1290ad05a9785de841e0b8aaa15c5c727`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
