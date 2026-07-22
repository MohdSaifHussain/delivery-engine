PLAYBOOK EXECUTION PREVIEW
============================================================
Dataset: C:\Users\mohds\delivery-engine\examples\transaction_monitoring\transactions_sample.csv
Playbook: transaction_monitoring_review v1.1.0 (transaction_monitoring_review.toml)
Goal: transaction monitoring completeness review of this feed
Plan digest: 8bf0456af8d415bcfe47f666d786add88833dd45537c607b524afa2cd65f8146
Approved by: Example Analyst

COLUMN CLASSIFICATION (approved at Human Gate 1):
  - amount: numeric_column
  - card_id: numeric_column
  - client_id: numeric_column
  - date: id_column
  - date: timestamp_column
  - errors: categorical_column
  - id: id_column
  - id: numeric_column
  - mcc: numeric_column
  - merchant_id: numeric_column
  - use_chip: binary_target
  - use_chip: categorical_column
  - zip: numeric_column

REQUIREMENT CHECKS:
  - [PASS] min_rows >= 100: source has 2,000 rows
  - [PASS] required kind 'id_column': found in: id, date
  - [PASS] required kind 'timestamp_column': found in: date
  - [PASS] source type 'csv' accepted: playbook accepts: csv, excel, sqlite

STAGES (9), in order:
  - dq_profile: KIT tool=analystkit_profile gate=must_pass
  - rules: AI slot=rules_draft (human approval by hash) needs=['dq_profile']
  - dq_validate: KIT tool=analystkit_validate gate=must_pass needs=['dq_profile', 'rules']
  - dq_dedupe: KIT tool=analystkit_dedupe gate=advisory needs=['dq_profile']
  - ops_review: KIT tool=opskit_run_playbook gate=must_pass needs=['dq_profile']
  - report: AI slot=narrative_report needs=['dq_validate']
  - ops_report: AI slot=ops_report needs=['ops_review']
  - readme: AI slot=readme needs=['report', 'ops_report']
  - package: PACKAGE needs=['report', 'ops_report', 'readme']

GATES:
  - must_pass (can stop the run): ['dq_profile', 'dq_validate', 'ops_review']
  - advisory (recorded, never stop): ['dq_dedupe']

DELIVERABLES: ['rules_draft', 'narrative_report', 'ops_report', 'readme', 'audit_log', 'manifest']
OUTPUT FORMATS: ['markdown', 'docx', 'pptx', 'xlsx']
============================================================
Proceed to execute exactly the above. Decline to stop with an audit entry and change the playbook or plan first.
