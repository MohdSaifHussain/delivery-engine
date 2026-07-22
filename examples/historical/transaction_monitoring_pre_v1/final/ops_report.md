# Operational Review Report

**Goal:** transaction monitoring completeness review of this feed
**Source:** `/home/claude/repo/delivery-engine/examples/transaction_monitoring/transactions_sample.csv`
**OpsKit playbook:** `weekly-review`
**Gate verdict:** pass

Every finding below was computed deterministically by OpsKit and is quoted verbatim from the hashed Findings Store. The AI wrote structure and prose only.

## What the engine assumed about this source

- [assumption] time column     : date
- [assumption] category columns: ['use_chip', 'errors']
- [assumption] numeric columns : ['id', 'client_id', 'card_id', 'amount', 'merchant_id', 'zip', 'mcc']
- PLAYBOOK: Weekly Operations Review
- The Monday-morning checklist, with the drill-down reflex built in.
- ================================================================
- Step 1/7 — How much data am I looking at?
-   why: Volume context frames everything; zero rows means stop.
-   · [INFO] 2,000 rows in scope.
- Step 2/7 — Is anything missing?
-   why: Gaps bias every downstream number; find them first.
-   ▲ [NOTABLE] Column 'merchant_state' has 250 nulls (12.5%).
-   ▲ [NOTABLE] Column 'zip' has 261 nulls (13.1%).
-   ▲ [NOTABLE] Column 'errors' has 1,967 nulls (98.4%).
- Step 3/7 — Is anything counted twice?
-   why: Duplicates inflate totals; dedupe before summing.
-   · [INFO] No exact duplicate rows found.
- Step 4/7 — What period does this cover?
-   why: A perfect analysis of stale data is a perfectly wrong answer.
-   ▲ [NOTABLE] Data spans 01 Jan 2010 to 05 Feb 2012 (newest record is 5272 day(s) old).
- Step 5/7 — Did volume move — and what drove it?
-   why: Never report a delta without its driver; the drill-down conditions on each winner and recurses.
-   · [INFO] Record count fell 0% window over window (19 → 19).
- Step 6/7 — Point spike or level shift?
-   why: Robust baselines keep one bad day from hiding itself; run-length separates spike from shift.
-   · [INFO] No day breached the robust baseline in the last 28 days.
- Step 7/7 — Is one category carrying the load?
-   why: 40%+ concentration is an ownership conversation.
-   ▲ [NOTABLE] 'Swipe Transaction' accounts for 88% of all records in 'use_chip' — a concentration worth an ownership conversation.
-   ▲ [NOTABLE] 'None' accounts for 98% of all records in 'errors' — a concentration worth an ownership conversation.
- Summary: ▲ Notable findings to remediate in the normal cycle: missing; time_coverage; concentration.

## Findings

11 finding(s): 0 critical, 7 notable, 4 informational. Operational criticals are insights recorded as evidence; they did not stop the pipeline (declared gate semantics).

### Notable

- **missing**: Column 'merchant_state' has 250 nulls (12.5%).
- **missing**: Column 'zip' has 261 nulls (13.1%).
- **missing**: Column 'errors' has 1,967 nulls (98.4%).
- **time_coverage**: Data spans 01 Jan 2010 to 05 Feb 2012 (newest record is 5272 day(s) old).
- **concentration**: 'Swipe Transaction' accounts for 88% of all records in 'use_chip' — a concentration worth an ownership conversation.
- **concentration**: 'None' accounts for 98% of all records in 'errors' — a concentration worth an ownership conversation.
- **recommendations**: Notable findings to remediate in the normal cycle: missing; time_coverage; concentration.

### Info

- **shape**: 2,000 rows in scope.
- **duplicates**: No exact duplicate rows found.
- **volume_change**: Record count fell 0% window over window (19 → 19).
- **anomaly_days**: No day breached the robust baseline in the last 28 days.

## Evidence trail

- ops_review findings: `aa5d2eb5f24f42767e9ac2d54e736d47b35d1a9267cfc45cfd62d179cc7bd2e5`
- source sha256: `f0a39e6710b294a9d442e5cc1c575189a46eb9c41006c47b185b807ac5e77598`

Re-run the same OpsKit playbook on the same source: matching hashes prove the findings; a mismatch proves the data changed.
