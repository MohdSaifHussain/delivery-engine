# Findings Report

**Goal:** Run a rigorous data quality audit of supply chain orders
**Source:** `C:\Users\mohds\delivery-engine\data\DataCoSupplyChainDataset_utf8.csv`

Every number below was computed deterministically and injected from the hashed Findings Store.

## What was tested

The source contains 180,519 rows across 53 columns. 5 validation rules were evaluated against declared expectations.

## What was found

Total exceptions: 15,759.

- **`R04`** (Order Status, allowed): 15,759 exception(s). Sample: `SUSPECTED_FRAUD`, `SUSPECTED_FRAUD`

## Evidence trail

- dq_profile findings: `25cd00114eff27c8c52088d59c933dca5430f3d2f7e3ec543cd012f63273236f`
- dq_validate findings: `01e2f211f5264bd59c6d536451f6765d4da61e63d6cdcf741291140ecbae891d`

Re-run the same commands on the same source: matching hashes prove the findings; a mismatch proves the data changed.
