# Playbook Compatibility Report

**Source:** `C:\Users\mohds\delivery-engine\data\DataCoSupplyChainDataset_utf8.csv`
**Rows:** 180,519  |  **Columns:** 53

Deterministic pre-flight: for each playbook in the library, the exact requirement checks the planner will enforce, and their verdicts on this dataset. Nothing here is advisory prose - these are the same functions the planner runs, so this report cannot disagree with it.

## churn_analysis v1.2.0 — QUALIFIES

*Customer churn analysis: DQ-gated EDA, narrative, packaged as re-performable evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 180,519 rows |
| required kind 'binary_target' | PASS | found in: Late_delivery_risk, Customer Country |
| required kind 'id_column' | PASS | found in: Order Item Id |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## data_quality_review v1.0.0 — QUALIFIES

*Data quality review of any tabular source: profile, engine-drafted rules approved at Human Gate 2, validation, dedupe, packaged evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 1 | PASS | source has 180,519 rows |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## ops_review v1.1.0 — DOES NOT QUALIFY

*Operational review of incidents, transactions, tickets, or any time-series extract: volume trends, drivers, drill-down evidence, packaged*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 1 | PASS | source has 180,519 rows |
| required kind 'timestamp_column' | FAIL | no column qualifies |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite |

Deliverable formats: markdown

## supplychain_audit v1.0.0 — QUALIFIES

*Supply chain order audit: DQ-gated profiling, dedupe, narrative, packaged as evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 180,519 rows |
| required kind 'id_column' | PASS | found in: Order Item Id |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite, postgres, mysql |

Deliverable formats: markdown

## transaction_monitoring_review v1.1.0 — DOES NOT QUALIFY

*Transaction monitoring feed review: completeness gated, engine-drafted rules approved at Human Gate 2, volume trends and drivers from OpsKit, dual narratives packaged as re-performable evidence*

| Check | Result | Detail |
|---|---|---|
| min_rows >= 100 | PASS | source has 180,519 rows |
| required kind 'id_column' | PASS | found in: Order Item Id |
| required kind 'timestamp_column' | FAIL | no column qualifies |
| source type 'csv' accepted | PASS | playbook accepts: csv, excel, sqlite |

Deliverable formats: markdown, docx, pptx, xlsx

## What the planner sees (classified column kinds)

| Column | Kind(s) |
|---|---|
| Benefit per order | numeric_column |
| Category Id | numeric_column |
| Category Name | (none) |
| Customer City | (none) |
| Customer Country | binary_target, categorical_column |
| Customer Email | categorical_column |
| Customer Fname | (none) |
| Customer Id | numeric_column |
| Customer Lname | (none) |
| Customer Password | categorical_column |
| Customer Segment | categorical_column |
| Customer State | (none) |
| Customer Street | (none) |
| Customer Zipcode | numeric_column |
| Days for shipment (scheduled) | numeric_column |
| Days for shipping (real) | numeric_column |
| Delivery Status | categorical_column |
| Department Id | numeric_column |
| Department Name | categorical_column |
| Late_delivery_risk | binary_target, numeric_column |
| Latitude | numeric_column |
| Longitude | numeric_column |
| Market | categorical_column |
| Order City | (none) |
| Order Country | (none) |
| Order Customer Id | numeric_column |
| Order Id | numeric_column |
| Order Item Cardprod Id | numeric_column |
| Order Item Discount | numeric_column |
| Order Item Discount Rate | numeric_column |
| Order Item Id | id_column, numeric_column |
| Order Item Product Price | numeric_column |
| Order Item Profit Ratio | numeric_column |
| Order Item Quantity | numeric_column |
| Order Item Total | numeric_column |
| Order Profit Per Order | numeric_column |
| Order Region | (none) |
| Order State | (none) |
| Order Status | categorical_column |
| Order Zipcode | numeric_column |
| Product Card Id | numeric_column |
| Product Category Id | numeric_column |
| Product Description | (none) |
| Product Image | (none) |
| Product Name | (none) |
| Product Price | numeric_column |
| Product Status | numeric_column |
| Sales | numeric_column |
| Sales per customer | numeric_column |
| Shipping Mode | categorical_column |
| Type | categorical_column |
| order date (DateOrders) | (none) |
| shipping date (DateOrders) | (none) |

## Verdict

3 of 5 playbook(s) qualify on this dataset: churn_analysis, data_quality_review, supplychain_audit.

State a goal and run the planner to select among the qualifying playbooks; a failed check above cannot be overridden by goal wording or by the LLM.
