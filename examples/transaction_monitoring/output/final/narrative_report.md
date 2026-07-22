# Findings Report

**Goal:** transaction monitoring completeness review of this feed
**Source:** `C:\Users\mohds\delivery-engine\examples\transaction_monitoring\transactions_sample.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 2,000 rows across 12 columns. 12 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Limitations & assumptions

- Data freshness: the DAMA timeliness score is 0.0 - the source's currency is not established; confirm the extract date before relying on time-sensitive conclusions.
- Accuracy is unscored: it is never inferred from the dataset alone - reconciliation against an authoritative source is a separate, human-initiated step.

Every caveat above is read from the hashed findings - nothing is inferred at writing time, and absent caveats are absent because nothing was recorded, not because nothing was checked.

## Evidence trail

- dq_profile findings: `a4102b3062665b939af807b981c999201fae4fe25eb4cb0db3256cf726881d1e`
- dq_validate findings: `04f02808a4e7231e6a6412424c8058a176c8f2ea0210ffa64154d599524f7cf5`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
