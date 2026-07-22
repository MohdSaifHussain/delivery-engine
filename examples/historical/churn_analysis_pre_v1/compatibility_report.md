# Playbook Compatibility Report

**Source:** `/home/claude/repo/delivery-engine/examples/churn_analysis/customers.csv`
**Rows:** 400  |  **Columns:** 5

Deterministic pre-flight: for each playbook in the library, the exact requirement checks the planner will enforce, and their verdicts on this dataset. Nothing here is advisory prose - these are the same functions the planner runs, so this report cannot disagree with it.

## churn_analysis v1.2.0 — QUALIFIES

*Customer churn analysis: DQ-gated EDA, narrative, packaged as re-performable evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 400 rows |
| required kind 'binary_target' | PASS | found in: churned |
| required kind 'id_column' | PASS | found in: customer_id |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## data_quality_review v1.0.0 — QUALIFIES

*Data quality review of any tabular source: profile, engine-drafted rules approved at Human Gate 2, validation, dedupe, packaged evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 1 | PASS | source has 400 rows |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## ops_review v1.1.0 — DOES NOT QUALIFY

*Operational review of incidents, transactions, tickets, or any time-series extract: volume trends, drivers, drill-down evidence, packaged*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 1 | PASS | source has 400 rows |
| required kind 'timestamp_column' | FAIL | no column qualifies |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite |

Deliverable formats: markdown

## transaction_monitoring_review v1.0.0 — DOES NOT QUALIFY

*Transaction monitoring feed review: completeness gated, engine-drafted rules approved at Human Gate 2, volume trends and drivers from OpsKit, dual narratives packaged as re-performable evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 400 rows |
| required kind 'id_column' | PASS | found in: customer_id |
| required kind 'timestamp_column' | FAIL | no column qualifies |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite |

Deliverable formats: markdown

## What the planner sees (classified column kinds)

| Column | Kind(s) |
|---|---|
| churned | binary_target |
| customer_id | id_column |
| monthly_spend | numeric_column |
| plan_type | categorical_column |
| tenure_months | numeric_column |

## Verdict

2 of 4 playbook(s) qualify on this dataset: churn_analysis, data_quality_review.

State a goal and run the planner to select among the qualifying playbooks; a failed check above cannot be overridden by goal wording or by the LLM.
