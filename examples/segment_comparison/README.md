# Segment comparison

**Does conversion rate differ by acquisition channel - and is that
difference real or noise?** The segment_comparison archetype gates on
data quality, then runs a deterministic inference suite: Wilson
confidence intervals per segment, Fisher/chi-square independence test,
Mann-Whitney U on numeric columns, all Benjamini-Hochberg FDR
corrected. Significance never gates the pipeline; the evidence is
reported and the human decides.

## The data

signup_conversion.csv - customer_id, converted (yes/no), channel
(organic/paid/referral), days_active - 300 rows. A binary conversion
outcome across three acquisition channels, with a numeric activity
column.

## Run it

From the repository root:

    python examples/segment_comparison/run_example.py

## What the engine found

The full inference results are in
output/final/findings/stats.json and narrated in
output/final/narrative_report.md. Key findings:

- organic: 30% conversion rate, Wilson CI [21.9%, 39.6%]
- paid: 60% conversion rate, Wilson CI [50.2%, 69.1%]
- referral: 80% conversion rate, Wilson CI [71.1%, 86.7%]
- Chi-square test: significant at alpha 0.05 (chi2=51.58,
  Cramer's V=0.41, p_adjusted_bh below 1e-06 resolution)
- Mann-Whitney on days_active: median 16 days for non-converters
  vs 53 days for converters; rank-biserial effect size 1.0;
  significant at alpha 0.05

Alpha was pre-registered in the playbook before any p-value was
computed. BH FDR correction applied across the full family of tests.
Effect sizes reported alongside every p-value (ASA Statement 2016,
principle 5). A reported p of 0.0 means below 1e-06 resolution,
not literally zero.

## About the visual report

output/final/report.html charts the data-quality scorecard,
validation, and column completeness. It does not yet visualize the
statistical inference findings above (Wilson CIs, significance tests,
effect sizes); that is a planned report enhancement. The inference
evidence is in stats.json and the narrative report as noted.

## How to verify this package

Open output/final/manifest.json. Recompute the SHA-256 of any file
and compare - matching hashes mean unaltered evidence. audit_log.jsonl
records every stage, decision, rationale, and timestamp. Each findings
file carries its own digest.
