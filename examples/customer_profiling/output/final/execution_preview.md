PLAYBOOK EXECUTION PREVIEW
============================================================
Dataset: C:\Users\mohds\delivery-engine\examples\customer_profiling\customers.csv
Playbook: universal_audit v1.0.0 (universal_audit.toml)
Goal: descriptive profile of the customer base: distribution shape of spend and tenure, plan mix, outliers
Plan digest: 907b520581829411e932999b78e4437104962841282a9af50fbe92da9fa4eacd
Approved by: Example Analyst

COLUMN CLASSIFICATION (approved at Human Gate 1):
  - churned: binary_target
  - customer_id: id_column
  - monthly_spend: numeric_column
  - plan_type: categorical_column
  - tenure_months: numeric_column

REQUIREMENT CHECKS:
  - [PASS] min_rows >= 100: source has 400 rows
  - [PASS] required kind 'id_column': found in: customer_id
  - [PASS] source type 'csv' accepted: playbook accepts: csv, parquet, excel, sqlite

STAGES (7), in order:
  - dq_profile: KIT tool=analystkit_profile gate=must_pass
  - dq_validate: KIT tool=analystkit_validate gate=must_pass needs=['dq_profile']
  - plan_approval: HUMAN_GATE needs=['dq_profile', 'dq_validate']
  - math: MATH gate=must_pass needs=['dq_profile', 'dq_validate', 'plan_approval']
  - report: AI slot=narrative_report needs=['math']
  - readme: AI slot=readme needs=['report']
  - package: PACKAGE needs=['report', 'readme']

GATES:
  - must_pass (can stop the run): ['dq_profile', 'dq_validate', 'math']
  - advisory (recorded, never stop): none

DELIVERABLES: ['narrative_report', 'readme', 'delivery_package', 'audit_log', 'manifest']
OUTPUT FORMATS: ['markdown']
============================================================
Proceed to execute exactly the above. Decline to stop with an audit entry and change the playbook or plan first.
