# Findings Report

**Goal:** data quality review of vendor extract
**Source:** `/tmp/vendor_extract.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 300 rows across 4 columns. 7 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 0.


## Evidence trail

- dq_profile findings: `f17ac2082116b2ac587a1d62f652ee060fbd1874f77cca2b789055c9635d2c68`
- dq_validate findings: `212073bf5f6c5f3141c0d8d8c3582fc783034448b2424c77f0dd242422dbd015`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
