# Findings Report

**Goal:** universal descriptive audit: distribution shape outliers entropy temporal structure
**Source:** `examples/universal_audit/orders.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 300 rows across 4 columns. 1 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Distribution & shape (deterministic descriptive math)

Suite `all` over the plan-approved columns. Every threshold is a fixed constant disclosed in the hashed findings; distribution fits use the Lilliefors correction (a plain KS p-value is invalid when parameters are estimated from the sample).

- `amount`: mean 153.125, median 146.1, skewness 6.534637, excess kurtosis 63.771777, mean CI [142.857564, 163.392436], tail `p95` 232.2 / `p99` 240.4
- `amount` outliers (MAD modified z, fixed threshold): 2 flagged (0.006667 of values)
- `amount` best-fitting candidate: `lognormal` (KS distance 0.091293, Lilliefors p 0.001)
- `region`: 5 categories, entropy 2.321928 bits (normalized 1.0), 0 rare below the fixed frequency threshold
- `event_date`: 75 distinct days, max gap 21 day(s), trend 0.0 rows/day (correlation undefined: constant daily counts)

Descriptive values informed, and never gated, this pipeline: shape is evidence for human judgment, not a stopping rule.

## Evidence trail

- dq_profile findings: `1ed426a2984404dc90b5d8434c44979fd5b7b0993faddc287aa8a7eb71b1e4a3`
- dq_validate findings: `6fcc04565dab76168bec4cc2f695fdfa43cd4e8fe34c9165d13b060a4cdf05c0`
- math findings: `cfc93b23736a4af03b6f0c259670146ce5feca3935ac0d30d7400d682c25fb15`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
