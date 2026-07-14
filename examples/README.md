# Examples — three analysts, three runs, real output committed

Each folder is a complete, runnable, end-to-end example: source data,
one script, and the actual output package the engine produced —
committed so you can read the results before running anything.

| Example | Audience | What it shows |
|---|---|---|
| [`transaction_monitoring/`](transaction_monitoring/) | Compliance / AML / TM analysts | Feed completeness + volume review; engine-drafted rules approved by hash (Human Gate 2); **multi-format output** (Word, PowerPoint, Excel + markdown evidence) |
| [`churn_analysis/`](churn_analysis/) | Business / product / data analysts | Deterministic baseline model (planted signal → roc_auc 1.0), EDA notebook, board deck — every number injected from the hashed store |
| [`audit_data_quality/`](audit_data_quality/) | Internal audit / audit COO analysts | An audit-issues register reviewed as an **automated workpaper**: evidence, reviewer sign-off, re-performance |

Every example starts with the same front door: the **Playbook
Compatibility Report** (`output/compatibility_report.md`) — a
deterministic pre-flight that states, playbook by playbook, whether
your dataset qualifies and exactly why or why not.

Run any example from the repository root after the QUICKSTART install:

```bash
python examples/churn_analysis/run_example.py
```

Re-run it and compare hashes with the committed package: matching
hashes prove the findings; that is the whole idea.
