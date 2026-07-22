# Findings Report

**Goal:** data quality review of this extract
**Source:** `C:\Users\mohds\delivery-engine\examples\audit_data_quality\audit_issues.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 793 rows across 7 columns. 8 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Limitations & assumptions

- Data freshness: the DAMA timeliness score is 0.7666666666666666 - the source's currency is not established; confirm the extract date before relying on time-sensitive conclusions.
- Accuracy is unscored: it is never inferred from the dataset alone - reconciliation against an authoritative source is a separate, human-initiated step.

Every caveat above is read from the hashed findings - nothing is inferred at writing time, and absent caveats are absent because nothing was recorded, not because nothing was checked.

## Evidence trail

- dq_profile findings: `0ce27a87632a7e77bd5a649354e28c3bed79225a37638d8893b3ecee76849765`
- dq_validate findings: `5e9577e803d37cc40a14eb8838fbf7774f702f798d6138e59bc8d92b4890cd64`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
