# Findings Report

**Goal:** churn analysis for the retention team
**Source:** `/tmp/telecom_churn.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 1,200 rows across 5 columns. 4 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 13.

- **`R03`** (tenure_months, range): 13 exception(s). Sample: `-1`, `-1`

## Evidence trail

- dq_profile findings: `9414a98a2edea0b601c6a95070b5dc2ebde647de885080ad97adc7777a3d768b`
- dq_validate findings: `8170ce34b5338b20fdbb7f520ffaf3594c77e4d6fb52040a43f8886655eb094b`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
