# Playbook Compatibility Report

**Source:** `data\fraud_model.csv`
**Rows:** 6,362,620  |  **Columns:** 11

Deterministic pre-flight: for each playbook in the library, the exact requirement checks the planner will enforce, and their verdicts on this dataset. Nothing here is advisory prose - these are the same functions the planner runs, so this report cannot disagree with it.

## churn_analysis v1.2.0 — QUALIFIES

*Customer churn analysis: DQ-gated EDA, narrative, packaged as re-performable evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 6,362,620 rows |
| required kind 'binary_target' | PASS | found in: isFraud |
| required kind 'id_column' | PASS | found in: row_id |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## data_quality_review v1.0.0 — QUALIFIES

*Data quality review of any tabular source: profile, engine-drafted rules approved at Human Gate 2, validation, dedupe, packaged evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 1 | PASS | source has 6,362,620 rows |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## healthcare_claims_audit v1.0.0 — QUALIFIES

*Healthcare claims audit: age, BMI, ICU, claim amount profiling with financial and clinical risk checks*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 6,362,620 rows |
| required kind 'id_column' | PASS | found in: row_id |
| source type 'csv' accepted | PASS | playbook accepts: csv |

Deliverable formats: markdown

## ops_review v1.1.0 — DOES NOT QUALIFY

*Operational review of incidents, transactions, tickets, or any time-series extract: volume trends, drivers, drill-down evidence, packaged*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 1 | PASS | source has 6,362,620 rows |
| required kind 'timestamp_column' | FAIL | no column qualifies |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite |

Deliverable formats: markdown

## segment_comparison v1.0.0 — QUALIFIES

*Segment comparison with statistical significance inference: rates, group differences, effect sizes, FDR-corrected evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 6,362,620 rows |
| required kind 'binary_target' | PASS | found in: isFraud |
| required kind 'id_column' | PASS | found in: row_id |
| source type 'csv' accepted | PASS | playbook accepts: csv, parquet, excel, sqlite |

Deliverable formats: markdown

## supplychain_audit v1.0.0 — QUALIFIES

*Supply chain order audit: DQ-gated profiling, dedupe, narrative, packaged as evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 6,362,620 rows |
| required kind 'id_column' | PASS | found in: row_id |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## transaction_monitoring_review v1.1.0 — DOES NOT QUALIFY

*Transaction monitoring feed review: completeness gated, engine-drafted rules approved at Human Gate 2, volume trends and drivers from OpsKit, dual narratives packaged as re-performable evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 6,362,620 rows |
| required kind 'id_column' | PASS | found in: row_id |
| required kind 'timestamp_column' | FAIL | no column qualifies |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite |

Deliverable formats: markdown, docx, pptx, xlsx

## universal_audit v1.0.0 — QUALIFIES

*Universal descriptive audit of any dataset: distribution shape, outliers, entropy, temporal structure, quantitative profile for every approved column*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 6,362,620 rows |
| required kind 'id_column' | PASS | found in: row_id |
| source type 'csv' accepted | PASS | playbook accepts: csv, parquet, excel, sqlite |

Deliverable formats: markdown

## What the planner sees (classified column kinds)

| Column | Kind(s) |
|---|---|
| amount | numeric_column |
| isFraud | binary_target, numeric_column |
| nameDest | (none) |
| nameOrig | (none) |
| newbalanceDest | numeric_column |
| newbalanceOrig | numeric_column |
| oldbalanceDest | numeric_column |
| oldbalanceOrg | numeric_column |
| row_id | id_column, numeric_column |
| step | numeric_column |
| type | categorical_column |

## Verdict

6 of 8 playbook(s) qualify on this dataset: churn_analysis, data_quality_review, healthcare_claims_audit, segment_comparison, supplychain_audit, universal_audit.

State a goal and run the planner to select among the qualifying playbooks; a failed check above cannot be overridden by goal wording or by the LLM.
