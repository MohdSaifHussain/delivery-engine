# Findings Report

**Goal:** segment comparison with statistical significance for the growth team
**Source:** `examples/segment_comparison/signup_conversion.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 300 rows across 4 columns. 1 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Statistical evidence (deterministic inference)

Inference suite `full_inference` on target `converted` (positive class `yes`), pre-registered alpha 0.05 approved at Human Gate 1. Significance flags use Benjamini-Hochberg-adjusted p-values across all 2 test(s); effect sizes accompany every p-value (the ASA statement on p-values).

- Rate `overall`: 0.566667 (n=300, Wilson 0.95 CI [0.510099, 0.621549])
- Rate `channel=organic`: 0.3 (n=100, Wilson 0.95 CI [0.218949, 0.395849])
- Rate `channel=paid`: 0.6 (n=100, Wilson 0.95 CI [0.502003, 0.690599])
- Rate `channel=referral`: 0.8 (n=100, Wilson 0.95 CI [0.711171, 0.866633])
- `converted` x `channel` (`pearson_chi2_no_correction`): p_adj 0.0 - significant at pre-registered alpha; Cramer's V 0.414663
- `converted` x `days_active` (`mann_whitney_u_two_sided_auto`): p_adj 0.0 - significant at pre-registered alpha; rank-biserial r 1.0

A reported p of `0.0` means below the `6`-decimal rounding contract's resolution (p < `1e-06`), not literally zero. Statistical significance informed, and never gated, this pipeline: p-values are evidence for human judgment, not a stopping rule.

## Evidence trail

- dq_profile findings: `b8a253a436c31641f7b4dc4163fbcf17c72028fdc024dd3dd725e5d5e0639772`
- dq_validate findings: `ade7b1f24789740aa19355c00c832f5b7cc44235f9800ea0cc70790905c2fe83`
- stats findings: `f2e6c8e9c15112b17fe2bc9ddfbc8f5e22cc57070bfa2daf9a627e3af26ab64b`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
