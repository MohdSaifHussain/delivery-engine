PLAYBOOK EXECUTION PREVIEW
============================================================
Dataset: C:\Users\mohds\delivery-engine\data\fraud_model.csv
Playbook: churn_analysis v1.2.0 (churn_analysis.toml)
Goal: churn analysis and binary classification baseline for fraud detection: predict isFraud using transaction features
Plan digest: 2ecef7a8c470e0f7e8f564e0fd3594d0c85ba6dce29c8db3c8724a616294108e
Approved by: Example Analyst

COLUMN CLASSIFICATION (approved at Human Gate 1):
  - amount: numeric_column
  - isFraud: binary_target
  - isFraud: numeric_column
  - newbalanceDest: numeric_column
  - newbalanceOrig: numeric_column
  - oldbalanceDest: numeric_column
  - oldbalanceOrg: numeric_column
  - row_id: id_column
  - row_id: numeric_column
  - step: numeric_column
  - type: categorical_column

REQUIREMENT CHECKS:
  - [PASS] min_rows >= 100: source has 6,362,620 rows
  - [PASS] required kind 'binary_target': found in: isFraud
  - [PASS] required kind 'id_column': found in: row_id
  - [PASS] source type 'csv' accepted: playbook accepts: csv, excel, sqlite, postgres, mysql

STAGES (10), in order:
  - dq_profile: KIT tool=analystkit_profile gate=must_pass
  - dq_validate: KIT tool=analystkit_validate gate=must_pass needs=['dq_profile']
  - dq_dedupe: KIT tool=analystkit_dedupe gate=advisory needs=['dq_profile']
  - plan_approval: HUMAN_GATE needs=['dq_profile', 'dq_validate']
  - baseline: MODEL gate=must_pass needs=['dq_profile', 'dq_validate', 'plan_approval']
  - eda: AI slot=eda_notebook needs=['plan_approval']
  - report: AI slot=narrative_report needs=['eda', 'baseline']
  - readme: AI slot=readme needs=['report']
  - presentation: AI slot=presentation needs=['baseline', 'report']
  - package: PACKAGE needs=['eda', 'report', 'readme', 'presentation']

GATES:
  - must_pass (can stop the run): ['dq_profile', 'dq_validate', 'baseline']
  - advisory (recorded, never stop): ['dq_dedupe']

DELIVERABLES: ['eda_notebook', 'narrative_report', 'readme', 'delivery_package', 'audit_log', 'manifest']
OUTPUT FORMATS: ['markdown']
============================================================
Proceed to execute exactly the above. Decline to stop with an audit entry and change the playbook or plan first.
