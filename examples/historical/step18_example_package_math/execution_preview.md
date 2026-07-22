PLAYBOOK EXECUTION PREVIEW
============================================================
Dataset: examples/universal_audit/orders.csv
Playbook: universal_audit v1.0.0 (universal_audit.toml)
Goal: universal descriptive audit: distribution shape outliers entropy temporal structure
Plan digest: 94389e90e69c14b43b80f81a5ce14ece53ebd453e35e41c653c66f42dcc36c74
Approved by: Saif

COLUMN CLASSIFICATION (approved at Human Gate 1):
  - amount: numeric_column
  - event_date: timestamp_column
  - record_id: id_column
  - region: categorical_column

REQUIREMENT CHECKS:
  - [PASS] min_rows >= 100: source has 300 rows
  - [PASS] required kind 'id_column': found in: record_id
  - [PASS] source type 'csv' accepted: playbook accepts: csv

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
