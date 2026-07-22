PLAYBOOK EXECUTION PREVIEW
============================================================
Dataset: C:\Users\mohds\delivery-engine\examples\churn_analysis\WA_Fn-UseC_-Telco-Customer-Churn.csv
Playbook: churn_analysis v1.2.0 (churn_analysis.toml)
Goal: churn analysis for the retention team
Plan digest: 950b79b93b78ad9a93abef70cd5b8354acead1c4ce5030a5d55afe5ff1bb726a
Approved by: Example Analyst

COLUMN CLASSIFICATION (approved at Human Gate 1):
  - Churn: binary_target
  - Contract: categorical_column
  - Dependents: binary_target
  - DeviceProtection: categorical_column
  - InternetService: categorical_column
  - MonthlyCharges: numeric_column
  - MultipleLines: categorical_column
  - OnlineBackup: categorical_column
  - OnlineSecurity: categorical_column
  - PaperlessBilling: binary_target
  - Partner: binary_target
  - PaymentMethod: categorical_column
  - PhoneService: binary_target
  - SeniorCitizen: binary_target
  - SeniorCitizen: numeric_column
  - StreamingMovies: categorical_column
  - StreamingTV: categorical_column
  - TechSupport: categorical_column
  - customerID: id_column
  - gender: binary_target
  - gender: categorical_column
  - tenure: numeric_column

REQUIREMENT CHECKS:
  - [PASS] min_rows >= 100: source has 7,043 rows
  - [PASS] required kind 'binary_target': found in: gender, SeniorCitizen, Partner, Dependents, PhoneService, PaperlessBilling, Churn
  - [PASS] required kind 'id_column': found in: customerID
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
