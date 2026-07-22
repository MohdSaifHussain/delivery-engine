# How the examples grew up

The [worked examples](../examples/) were not written all at once. They
are a record of the engine being tested against progressively harder
problems, and of what each run taught. Read in order, they show the
method maturing from proving the machinery works to applying it to real
data and catching real mistakes.

The [historical archive](../examples/historical/) preserves earlier
packages exactly as produced - the same discipline applied at each
stage as the engine matured. The current examples folder holds the
v1.0 runs on the current engine.

## Stage one - planted signals, to prove the mechanism

The earliest examples use datasets with a known, deliberately planted
answer, so that a correct engine must produce a specific, predictable
result. The point was never the result; it was proving the machinery is
sound and re-performable.

- **[audit_data_quality](../examples/audit_data_quality/)** - an
  audit-issues register with a planted defect: `owner_team` is null on
  roughly 8% of rows (exactly 66 of 793). A correct profile must find
  exactly that null pattern and state the count. The visual report
  renders it amber against clean columns in green. This proved the
  data-quality gate and the automated-workpaper flow.

## Stage two - real data, real deliverables

- **[transaction_monitoring](../examples/transaction_monitoring/)** - a
  2,000-row card-transaction sample. The engine drafts 12 validation
  rules, stops at Human Gate 2 for approval by SHA-256, and produces
  multi-format deliverables (Word, PowerPoint, Excel). Real feed issues
  found: missing state/zip data, data 5,280 days old, high category
  concentration. This proved the human-approval gate and the document
  builders on data the engine had not been tuned for.

## Stage three - a real run that caught a real mistake

- **[paysim_fraud](../examples/paysim_fraud/)** - the PaySim payment
  dataset, 6,362,620 rows. The plan first selected the wrong target
  column; the pre-flight preview surfaced it and the run was declined
  before anything executed. The corrected re-run produced an honest
  baseline: ROC-AUC 0.989545, and recall 0.476376 - the model catches
  under half the fraud, and the package says so plainly.

## Stage four - the full archetype suite (v1.0)

The v1.0 milestone extended the example set to cover the full range of
what analysts actually do day to day.

- **[churn_analysis](../examples/churn_analysis/)** - Kaggle Telco
  Customer Churn dataset, 7,043 rows. A real-world churn baseline:
  ROC-AUC 0.845, recall 0.546. Leakage sentinel clean. The runner
  guards against wrong-target selection (the PaySim lesson applied to
  churn). Earlier synthetic version preserved in historical/.

- **[segment_comparison](../examples/segment_comparison/)** - 300-row
  signup dataset. Wilson confidence intervals, Fisher/chi-square,
  Mann-Whitney U, Benjamini-Hochberg FDR correction. Real channel
  differences: organic 30% vs paid 60% vs referral 80% conversion,
  chi-square significant (Cramer's V=0.41). Alpha pre-registered before
  any p-value was computed (ASA Statement 2016, principle 5).

- **[universal_audit](../examples/universal_audit/)** - 300-row orders
  feed. Distribution fitting with Lilliefors correction, MAD outlier
  detection, Shannon entropy, temporal gap analysis. Three explicit
  refusals-to-overclaim: Weibull p-value omitted, temporal correlation
  reported undefined, best-fit labelled a selection rule not a
  significance claim.

- **[customer_profiling](../examples/customer_profiling/)** - 400-row
  synthetic customer table. Descriptive audit of spend, tenure, and
  plan mix. Both numeric columns fit normal distributions; plan_type
  entropy near-uniform. The binary churn flag is correctly excluded
  from the numeric suite (shape statistics on yes/no data are noise).

## Why the earlier examples are kept

They are not superseded and they are not hidden. Like the founding
architecture diagram in this folder, they are part of the record: each
one proved a specific property before that property was trusted on real
data. Keeping them is the same principle the engine runs on: show the
evidence, in order, and let it be re-performed.

The historical archive extends this principle to the output packages
themselves - preserving what the engine produced at each stage, not
just the code that produced it.
