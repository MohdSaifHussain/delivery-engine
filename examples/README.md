<div align="center">

# Examples

**Committed output packages from real engine runs - every number verifiable by hash.**

![Runs](https://img.shields.io/badge/runs-7-blue)
![Reproducible](https://img.shields.io/badge/reproducible-SHA--256-success)
![Largest run](https://img.shields.io/badge/largest%20run-6.36M%20rows-orange)

</div>

---

> [!TIP]
> New here? See [how these examples grew up](../docs/how-the-examples-grew-up.md) - the
> learning arc from early-step demos to a real 6.36M-row fraud run.

> [!NOTE]
> Each subdirectory is a **complete output package** the engine produced on a real dataset -
> checked in so you can read the results *before* running anything. Every package ships a
> `manifest.json` whose SHA-256 tree covers every file. Recompute a hash, compare it to the
> manifest, and you have proven the evidence is unaltered.

## Quick start

From the repository root, after the install in [`QUICKSTART.md`](../QUICKSTART.md):

```bash
python examples/audit_data_quality/run_example.py
```

Each folder's own `README` documents that example in full. Open `output/final/report.html`
in any browser to see the deterministic visual report for that run.

---

## The runs

### `paysim_fraud/` - fraud model

> [!IMPORTANT]
> **A 6.36M-row PaySim run (Kaggle) where the engine caught a mistake before it became evidence.**
> The plan first selected the wrong target; the pre-flight preview surfaced it and the run was
> **declined**. The corrected re-run produced an honest baseline:

| Metric | Value |
|:--|:--|
| **ROC-AUC** | `0.989545` |
| **Recall** | `0.476376` |
| **Precision** | `0.913165` |
| **Leakage warnings** | none |

### `churn_analysis/` - churn model

**Business / product.** Kaggle Telco Customer Churn dataset (7,043 rows, 21 columns).
Real-world data: 26.5% churn rate, leakage sentinel clean. Fixed-seed LogisticRegression baseline:

| Metric | Value |
|:--|:--|
| **ROC-AUC** | `0.845464` |
| **Recall** | `0.546039` |
| **Precision** | `0.660622` |
| **Leakage warnings** | none |

Target selection: `Churn` is the first binary_target in column order - a disclosed
deterministic rule. Produces an EDA notebook, narrative report, and slide deck.

### `transaction_monitoring/` - compliance / AML

2,000-row card sample. The engine drafts **12 validation rules**, then stops at **Human Gate 2**
for approval by SHA-256 before validating. Real feed issues found: missing state/zip data,
data 5,280 days old, high category concentration. Deliverables in **Word, PowerPoint, and Excel**
- every figure injected from the hashed store.

### `audit_data_quality/` - internal audit

A 793-row audit-issues register with a planted null pattern (`owner_team` null on 8.3% of rows),
run as an **automated workpaper**: profile, rules approved by hash, evidence trail. The visual
report renders the planted null amber against clean columns in green.

### `segment_comparison/` - statistical inference

300-row signup dataset. **Wilson intervals, Fisher/chi-square, Mann-Whitney, BH FDR correction.**
Real channel differences found: organic 30% vs paid 60% vs referral 80% conversion.
Chi-square significant (Cramer's V=0.41). Alpha pre-registered before any p-value was computed.

### `universal_audit/` - descriptive shape

300-row orders feed. **Distribution fitting, MAD outliers, Shannon entropy, temporal structure**
on any table with an id column. Includes three explicit refusals-to-overclaim: Weibull p-value
omitted (Lilliefors 1967), temporal correlation reported undefined (zero variance in y),
best-fit labelled a selection rule not a significance claim. See `findings/math.json` for the
full evidence.

### `customer_profiling/` - customer descriptive audit

400-row synthetic customer table. Descriptive audit of spend, tenure, and plan mix via the
universal_audit archetype. `monthly_spend` and `tenure_months` both fit normal distributions;
`plan_type` Shannon entropy 1.585 bits (near-uniform). Binary `churned` column correctly
excluded from the numeric suite. See `findings/math.json` for the full evidence.

---

## Historical archive

`historical/` preserves earlier packages as the project's growth record - the same
discipline applied at each stage as the engine matured. See
[`historical/README.md`](historical/README.md) for the full provenance index.

---

## How to verify any package

> [!TIP]
> Every package rests on one claim: **`manifest.json` is a hash tree, and matching hashes
> prove the files are the ones the run produced.**
>
> For `paysim_fraud`, whose 493 MB source is not committed, the input's own SHA-256 is
> recorded under `source_fingerprint` - so even the data that produced it is pinned.

<div align="center">

**Re-run, recompute, compare.** Matching hashes prove the findings.

</div>
