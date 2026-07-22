PLAYBOOK EXECUTION PREVIEW
============================================================
Dataset: C:\Users\mohds\delivery-engine\examples\segment_comparison\signup_conversion.csv
Playbook: segment_comparison v1.0.0 (segment_comparison.toml)
Goal: segment comparison with statistical significance: does conversion rate differ by acquisition channel?
Plan digest: 2419c7ef749f422bd9aaed9ee57496c7d74dd97b5dcb82452a81d130433938b1
Approved by: Example Analyst

COLUMN CLASSIFICATION (approved at Human Gate 1):
  - channel: categorical_column
  - converted: binary_target
  - customer_id: id_column
  - days_active: numeric_column

REQUIREMENT CHECKS:
  - [PASS] min_rows >= 100: source has 300 rows
  - [PASS] required kind 'binary_target': found in: converted
  - [PASS] required kind 'id_column': found in: customer_id
  - [PASS] source type 'csv' accepted: playbook accepts: csv, parquet, excel, sqlite

STAGES (7), in order:
  - dq_profile: KIT tool=analystkit_profile gate=must_pass
  - dq_validate: KIT tool=analystkit_validate gate=must_pass needs=['dq_profile']
  - plan_approval: HUMAN_GATE needs=['dq_profile', 'dq_validate']
  - stats: STATS stat_test=full_inference gate=must_pass needs=['dq_profile', 'dq_validate', 'plan_approval']
  - report: AI slot=narrative_report needs=['stats']
  - readme: AI slot=readme needs=['report']
  - package: PACKAGE needs=['report', 'readme']

STATISTICS: pre-registered alpha = 0.05 (fixed now, before any p-value exists; significance never gates)

GATES:
  - must_pass (can stop the run): ['dq_profile', 'dq_validate', 'stats']
  - advisory (recorded, never stop): none

DELIVERABLES: ['narrative_report', 'readme', 'delivery_package', 'audit_log', 'manifest']
OUTPUT FORMATS: ['markdown']
============================================================
Proceed to execute exactly the above. Decline to stop with an audit entry and change the playbook or plan first.
