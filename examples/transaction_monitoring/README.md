# Transaction monitoring feed review

**Audience:** compliance, AML, and transaction-monitoring analysts.
**The question answered:** does this transaction feed contain what it
should, and did its volume behave?

A silent volume drop or a coverage gap in a monitoring feed is the
classic completeness failure — the class of defect behind real
regulatory fines. This example runs the `transaction_monitoring_review`
archetype over a 2,000-row card-transaction sample (from a public
Kaggle dataset):

1. `compatibility_report.md` — which playbooks can run on this data
2. Deterministic profile gate (AnalystKit)
3. Engine drafts 12 validation rules → **Human Gate 2** stops the run;
   the analyst approves the exact draft by SHA-256
4. Validation, dedupe, OpsKit volume review
5. Dual narratives + **multi-format deliverables**: Word report,
   PowerPoint deck, Excel workpaper — every number injected from the
   hashed Findings Store and verified present after generation

Run it:

```bash
python examples/transaction_monitoring/run_example.py
```

The committed `output/` is a real run. `output/final/manifest.json` is
the hash tree; re-run and compare.
