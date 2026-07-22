# Findings Report

**Goal:** descriptive profile of the customer base: distribution shape of spend and tenure, plan mix, outliers
**Source:** `C:\Users\mohds\delivery-engine\examples\customer_profiling\customers.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 400 rows across 5 columns. 1 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Distribution & shape (deterministic descriptive math)

Suite `all` over the plan-approved columns. Every threshold is a fixed constant disclosed in the hashed findings; distribution fits use the Lilliefors correction (a plain KS p-value is invalid when parameters are estimated from the sample).

- `monthly_spend`: mean 285.75, median 285.75, skewness 0.0, excess kurtosis -1.200957, mean CI [280.779025, 290.720975], tail `p95` 364.5 / `p99` 371.5
- `tenure_months`: mean 30.4, median 30.0, skewness 0.012253, excess kurtosis -1.19623, mean CI [28.695779, 32.104221], tail `p95` 57.05 / `p99` 60.0
- `monthly_spend` outliers (MAD modified z, fixed threshold): 0 flagged (0.0 of values)
- `tenure_months` outliers (MAD modified z, fixed threshold): 0 flagged (0.0 of values)
- `monthly_spend` best-fitting candidate: `normal` (KS distance 0.066957, Lilliefors p 0.001)
- `tenure_months` best-fitting candidate: `normal` (KS distance 0.065295, Lilliefors p 0.001)
- `plan_type`: 3 categories, entropy 1.584953 bits (normalized 0.999994), 0 rare below the fixed frequency threshold

Descriptive values informed, and never gated, this pipeline: shape is evidence for human judgment, not a stopping rule.

## Limitations & assumptions

- Accuracy is unscored: it is never inferred from the dataset alone - reconciliation against an authoritative source is a separate, human-initiated step.

Every caveat above is read from the hashed findings - nothing is inferred at writing time, and absent caveats are absent because nothing was recorded, not because nothing was checked.

## Evidence trail

- dq_profile findings: `4fcc9974835b83c035bfda05c99af8712a1b73681cff725e5c963ee8e862897d`
- dq_validate findings: `ade7b1f24789740aa19355c00c832f5b7cc44235f9800ea0cc70790905c2fe83`
- math findings: `047a37def98c2d5e655e8b97f5f115cee522f24ab3f95c49e6120e667edbaa6c`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
