# Playbook Compatibility Report

**Source:** `C:\Users\mohds\delivery-engine\examples\transaction_monitoring\transactions_sample.csv`
**Rows:** 2,000  |  **Columns:** 12

Deterministic pre-flight: for each playbook in the library, the exact requirement checks the planner will enforce, and their verdicts on this dataset. Nothing here is advisory prose - these are the same functions the planner runs, so this report cannot disagree with it.

## churn_analysis v1.2.0 — QUALIFIES

*Customer churn analysis: DQ-gated EDA, narrative, packaged as re-performable evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 2,000 rows |
| required kind 'binary_target' | PASS | found in: use_chip |
| required kind 'id_column' | PASS | found in: id, date |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## data_quality_review v1.0.0 — QUALIFIES

*Data quality review of any tabular source: profile, engine-drafted rules approved at Human Gate 2, validation, dedupe, packaged evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 1 | PASS | source has 2,000 rows |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## healthcare_claims_audit v1.0.0 — QUALIFIES

*Healthcare claims audit: age, BMI, ICU, claim amount profiling with financial and clinical risk checks*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 2,000 rows |
| required kind 'id_column' | PASS | found in: id, date |
| source type 'csv' accepted | PASS | playbook accepts: csv |

Deliverable formats: markdown

## ops_review v1.1.0 — QUALIFIES

*Operational review of incidents, transactions, tickets, or any time-series extract: volume trends, drivers, drill-down evidence, packaged*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 1 | PASS | source has 2,000 rows |
| required kind 'timestamp_column' | PASS | found in: date |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite |

Deliverable formats: markdown

## segment_comparison v1.0.0 — QUALIFIES

*Segment comparison with statistical significance inference: rates, group differences, effect sizes, FDR-corrected evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 2,000 rows |
| required kind 'binary_target' | PASS | found in: use_chip |
| required kind 'id_column' | PASS | found in: id, date |
| source type 'csv' accepted | PASS | playbook accepts: csv, parquet, excel, sqlite |

Deliverable formats: markdown

## supplychain_audit v1.0.0 — QUALIFIES

*Supply chain order audit: DQ-gated profiling, dedupe, narrative, packaged as evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 2,000 rows |
| required kind 'id_column' | PASS | found in: id, date |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## transaction_monitoring_review v1.1.0 — QUALIFIES

*Transaction monitoring feed review: completeness gated, engine-drafted rules approved at Human Gate 2, volume trends and drivers from OpsKit, dual narratives packaged as re-performable evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 2,000 rows |
| required kind 'id_column' | PASS | found in: id, date |
| required kind 'timestamp_column' | PASS | found in: date |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite |

Deliverable formats: markdown, docx, pptx, xlsx

## universal_audit v1.0.0 — QUALIFIES

*Universal descriptive audit of any dataset: distribution shape, outliers, entropy, temporal structure, quantitative profile for every approved column*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 2,000 rows |
| required kind 'id_column' | PASS | found in: id, date |
| source type 'csv' accepted | PASS | playbook accepts: csv, parquet, excel, sqlite |

Deliverable formats: markdown

## What the planner sees (classified column kinds)

| Column | Kind(s) |
|---|---|
| amount | numeric_column |
| card_id | numeric_column |
| client_id | numeric_column |
| date | id_column, timestamp_column |
| errors | categorical_column |
| id | id_column, numeric_column |
| mcc | numeric_column |
| merchant_city | (none) |
| merchant_id | numeric_column |
| merchant_state | (none) |
| use_chip | binary_target, categorical_column |
| zip | numeric_column |

## Verdict

8 of 8 playbook(s) qualify on this dataset: churn_analysis, data_quality_review, healthcare_claims_audit, ops_review, segment_comparison, supplychain_audit, transaction_monitoring_review, universal_audit.

State a goal and run the planner to select among the qualifying playbooks; a failed check above cannot be overridden by goal wording or by the LLM.
