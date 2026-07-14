# Churn analysis with a deterministic baseline model

**Audience:** business, product, and data analysts.
**The question answered:** what does the data say about churn, and what
would a defensible baseline model score — reproducibly?

The dataset carries a planted signal: `churned = yes` exactly when
`tenure_months < 12`. The fixed-seed baseline (scikit-learn logistic
regression, seeds recorded in the findings) therefore lands at
**roc_auc 1.0** — and because training is deterministic, it lands there
every single run. That is the point: metrics you can re-perform, not
metrics you have to trust.

The run produces the EDA notebook, a narrative report with the baseline
section, a README, and a 7-slide deck. The AI slots write prose and
structure only; every number is injected from the hashed store.

Run it:

```bash
python examples/churn_analysis/run_example.py
```
