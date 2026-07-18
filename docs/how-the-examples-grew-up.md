# How the examples grew up

The [worked examples](../examples/) were not written all at once. They
are a record of the engine being tested against progressively harder
problems, and of what each run taught. Read in order, they show the
method maturing from *proving the machinery works* to *applying it to
real data and catching a real mistake*.

## Stage one — planted signals, to prove the mechanism

The earliest examples use datasets with a **known, deliberately planted
answer**, so that a correct engine must produce a specific, predictable
result. The point was never the result; it was proving the machinery is
sound and re-performable.

- **[audit_data_quality](../examples/audit_data_quality/)** — an
  audit-issues register with a planted defect: `owner_team` is null on
  roughly 8% of rows. A correct profile must find exactly that null
  pattern and state the count. This proved the data-quality gate and
  the automated-workpaper flow.
- **[churn_analysis](../examples/churn_analysis/)** — a dataset with a
  planted signal (`churned = yes` exactly when `tenure_months < 12`).
  The fixed-seed baseline reaches ROC-AUC 1.0 on every run. The lesson
  being demonstrated is **determinism, not model quality**: the same
  inputs produce the same hashes, every time.

## Stage two — real data, real deliverables

- **[transaction_monitoring](../examples/transaction_monitoring/)** — a
  2,000-row card-transaction sample from a public Kaggle dataset. Here
  the engine drafts validation rules, stops at Human Gate 2 for
  approval by SHA-256, and produces multi-format deliverables (Word,
  PowerPoint, Excel). This proved the human-approval gate and the
  document builders on data the engine had not been tuned for.

## Stage three — a real run that caught a real mistake

- **[paysim_fraud](../examples/paysim_fraud/)** — the PaySim payment
  dataset, 6,362,620 rows. This is where the earlier discipline paid
  off. The plan first selected the wrong target column; the pre-flight
  preview surfaced it and the run was **declined** before anything
  executed. The corrected re-run produced an honest baseline: ROC-AUC
  0.989545, and **recall 0.476376** — the model catches under half the
  fraud, and the package says so plainly.

The contrast between stage one and stage three is the whole story. A
planted signal was designed to score 1.0 to prove determinism. Real
data scored 0.476 on recall and the engine reported it without
flinching — and, one step earlier, stopped a wrong-target run from
becoming evidence at all. The machinery proven on planted answers is
what made the honest real-data result trustworthy.

## Why the earlier examples are kept

They are not superseded and they are not hidden. Like the
[founding architecture diagram](delivery-engine-architecture.png) in
this folder, they are part of the record: each one proved a specific
property — the DQ gate, determinism, the human gate, the document
builders — before that property was trusted on real data. Keeping them
is the same principle the engine runs on: show the evidence, in order,
and let it be re-performed.
