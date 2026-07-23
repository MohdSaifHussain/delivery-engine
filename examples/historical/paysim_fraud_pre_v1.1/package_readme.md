# Delivery Package

**Goal:** detect fraud patterns and quantify risk drivers in payment transactions
**Source:** `data\fraud_model.csv`

Produced by the Delivery Engine: agent proposes, deterministic tools dispose, human governs, every claim traceable.

## Contents

- `eda_notebook`
- `narrative_report`
- `readme`
- `delivery_package`
- `audit_log`
- `manifest`

## Headline finding

5 rules evaluated, 0 total exceptions - reported, never dropped.

## How to verify this package

Open `manifest.json`. Recompute the SHA-256 of any file and compare. Matching hashes = unaltered evidence. `audit_log.jsonl` records every stage, decision, rationale, and timestamp (IST). Findings JSONs under `findings/` carry their own digests - re-run the same tools on the same source to re-perform any stage.
