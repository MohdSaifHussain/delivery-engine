<div align="center">

# 📂 Examples

**Committed output packages from real engine runs — every number verifiable by hash.**

![Runs](https://img.shields.io/badge/runs-6-blue)
![Reproducible](https://img.shields.io/badge/reproducible-SHA--256-success)
![Largest run](https://img.shields.io/badge/largest%20run-6.36M%20rows-orange)

</div>

---

> [!NOTE]
> Each subdirectory is a **complete output package** the engine produced on a real dataset — checked in so you can read the results *before* running anything. Every package ships a `manifest.json` whose SHA-256 tree covers every file. Recompute a hash, compare it to the manifest, and you've proven the evidence is unaltered.

## 🚀 Quick start

From the repository root, after the install in [`QUICKSTART.md`](../QUICKSTART.md):

```bash
python examples/churn_analysis/run_example.py
```

Each folder's own `README` documents that example in full.

---

## 📊 The runs

### 🔍 `paysim_fraud/` &nbsp;·&nbsp; `churn_analysis`

> [!IMPORTANT]
> **A 6.36M-row PaySim run (Kaggle) where the engine caught a mistake before it became evidence.**
> The plan first selected the wrong target; the pre-flight preview surfaced it and the run was **declined**. The corrected re-run produced an honest baseline:

| Metric | Value |
|:--|:--|
| **ROC-AUC** | `0.989545` |
| **Recall** | `0.476376` |
| **Precision** | `0.913165` |
| **Leakage warnings** | ✅ none |

### 🏦 `transaction_monitoring/` &nbsp;·&nbsp; `transaction_monitoring_review`

**Compliance / AML.** 2,000-row card sample. The engine drafts **12 validation rules**, then stops at **Human Gate 2** for approval by SHA-256 before validating. Deliverables in **Word, PowerPoint, and Excel** — every figure injected from the hashed store.

### 📋 `audit_data_quality/` &nbsp;·&nbsp; `data_quality_review`

**Internal audit.** A 793-row audit-issues register with a planted null pattern, run as an **automated workpaper**: profile, rules approved by hash, evidence trail. Quarterly re-runs are hash-comparable — drift is caught by comparison, not memory.

### 📈 `churn_analysis/` &nbsp;·&nbsp; `churn_analysis`

**Business / product.** A planted signal (`churned` iff `tenure_months < 12`). The fixed-seed baseline hits **ROC-AUC 1.0 every run** — the point is *determinism*, not model performance. Produces an EDA notebook, narrative, and slide deck.

### 🧪 `segment_comparison/` &nbsp;·&nbsp; `segment_comparison`

**Statistical inference between segments** — Wilson intervals, effect sizes, BH-corrected tests, minimum detectable effect.

### 📐 `universal_audit/` &nbsp;·&nbsp; `universal_audit`

**Descriptive shape on any table** — distribution fits, MAD outliers, entropy, temporal structure.

---

## 🔐 How to verify any package

> [!TIP]
> Every package rests on one claim: **`manifest.json` is a hash tree, and matching hashes prove the files are the ones the run produced.**
> For `paysim_fraud`, whose 493 MB source isn't committed, the input's own SHA-256 is recorded under `source_fingerprint` — so even the data that produced it is pinned.

<div align="center">

**Re-run · recompute · compare.** &nbsp; Matching hashes prove the findings.

</div>
