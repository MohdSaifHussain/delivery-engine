# Audit-universe data quality review (automated workpaper)

**Audience:** internal audit and audit COO analysts — the 3rd Line of
Defence, whose profession is built on evidence a reviewer can
re-perform.

The dataset is an audit-issues register: 793 issues across business
lines with severity, status, and owning team. It carries a planted data
quality defect: `owner_team` is null on roughly 8% of rows — exactly
the kind of inconsistency an analyst is asked to "investigate and
report in a meaningful way."

The run is an automated workpaper: deterministic profile (finds the
null pattern and states the exact count), engine-drafted validation
rules approved by hash (the reviewer sign-off), validation, dedupe, and
a packaged evidence trail. Quarterly re-runs on fresh extracts are
hash-comparable — drift is detected by comparison, not by memory.

Run it:

```bash
python examples/audit_data_quality/run_example.py
```
