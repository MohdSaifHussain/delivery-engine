# Findings Report

**Goal:** churn analysis for the retention team
**Source:** `/home/claude/repo/delivery-engine/examples/churn_analysis/customers.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 400 rows across 5 columns. 1 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Baseline model (deterministic reference point)

A fixed-seed logistic regression baseline on target `churned` (stratified 300/100 split): accuracy 1.0, precision 1.0, recall 1.0, f1 1.0, roc_auc 1.0. This is a reference point for human modeling work, not a delivered model.

## Evidence trail

- dq_profile findings: `4fcc9974835b83c035bfda05c99af8712a1b73681cff725e5c963ee8e862897d`
- dq_validate findings: `ade7b1f24789740aa19355c00c832f5b7cc44235f9800ea0cc70790905c2fe83`
- baseline findings: `2e7a710a26705b3b75b04bc5ab96636830a4c7e08ca127db88e824598dd6b67b`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
