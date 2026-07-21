# Universal descriptive audit

**What is the shape of this data?** The `universal_audit` archetype runs
on any table with an id column. It profiles every column, validates,
waits for plan approval at a human gate, then runs a deterministic
descriptive suite over the approved columns: distribution shape,
outliers, entropy, and temporal structure.

## The data

A small orders feed - `record_id`, `amount`, `region`, `event_date`:
one numeric, one categorical, one temporal column, so the audit
exercises all three branches of the descriptive suite.

## Run it

From the repository root:

```
python examples/universal_audit/run_example.py
```

## What the engine found

The descriptive math is the point of this example, and it is worth
opening directly. The full results live in
[`output/final/findings/math.json`](output/final/findings/math.json)
and are narrated in
[`output/final/narrative_report.md`](output/final/narrative_report.md).
A few of the findings:

- **`amount`** - fitted to a lognormal distribution (chosen by smallest
  KS distance, a disclosed selection rule, not a significance claim);
  mean reported with a t-interval confidence interval; two outliers
  flagged by the MAD modified z-score.
- **`region`** - Shannon entropy across its categories.
- **`event_date`** - span, distinct days, and the largest gap between
  observations.

The engine also declines to overclaim where the math does not support
a statement: it omits a p-value for the Weibull fit (invalid when
parameters are estimated from the same sample), and reports the
temporal trend's correlation as undefined rather than inventing one
when daily counts are constant. These refusals are part of the
evidence.

## About the visual report

`output/final/report.html` is the deterministic Step 21 visual report.
It charts the data-quality scorecard, validation results, and column
completeness - the profile-level view. It does **not** yet visualize
the descriptive-math findings above; charting the distribution,
outlier, entropy, and temporal results is a planned report
enhancement. Until then, the math evidence is in `math.json` and the
narrative report, as noted above.

## How to verify this package

Open `output/final/manifest.json`. Recompute the SHA-256 of any file
and compare - matching hashes mean unaltered evidence. `audit_log.jsonl`
records every stage, decision, rationale, and timestamp. Each findings
file under `findings/` carries its own digest; re-run the same tools on
the same source to re-perform any stage.
