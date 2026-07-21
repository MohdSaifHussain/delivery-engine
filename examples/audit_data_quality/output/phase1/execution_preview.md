PLAYBOOK EXECUTION PREVIEW
============================================================
Dataset: C:\Users\mohds\delivery-engine\examples\audit_data_quality\audit_issues.csv
Playbook: data_quality_review v1.0.0 (data_quality_review.toml)
Goal: data quality review of this extract
Plan digest: 72ca76e3819d39a062507edb7b8c1e225169849771179657595436680067eac1
Approved by: Example Analyst

COLUMN CLASSIFICATION (approved at Human Gate 1):
  - business_line: categorical_column
  - days_open: numeric_column
  - issue_id: id_column
  - owner_team: categorical_column
  - raised_at: timestamp_column
  - severity: categorical_column
  - status: binary_target
  - status: categorical_column

REQUIREMENT CHECKS:
  - [PASS] min_rows >= 1: source has 793 rows
  - [PASS] source type 'csv' accepted: playbook accepts: csv, excel, sqlite, postgres, mysql

STAGES (7), in order:
  - dq_profile: KIT tool=analystkit_profile gate=must_pass
  - rules: AI slot=rules_draft (human approval by hash) needs=['dq_profile']
  - dq_validate: KIT tool=analystkit_validate gate=must_pass needs=['dq_profile', 'rules']
  - dq_dedupe: KIT tool=analystkit_dedupe gate=advisory needs=['dq_profile']
  - report: AI slot=narrative_report needs=['dq_validate']
  - readme: AI slot=readme needs=['report']
  - package: PACKAGE needs=['report', 'readme']

GATES:
  - must_pass (can stop the run): ['dq_profile', 'dq_validate']
  - advisory (recorded, never stop): ['dq_dedupe']

DELIVERABLES: ['rules_draft', 'narrative_report', 'readme', 'audit_log', 'manifest']
OUTPUT FORMATS: ['markdown']
============================================================
Proceed to execute exactly the above. Decline to stop with an audit entry and change the playbook or plan first.
