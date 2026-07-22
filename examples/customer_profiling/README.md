# Customer profiling

**What does the shape of this customer base look like?** The
universal_audit archetype runs a deterministic descriptive suite
over every approved column: distribution shape, outliers, and entropy.
No model, no prediction - just an honest statistical profile of what
is there before any analysis begins.

## The data

customers.csv - customer_id, churned, tenure_months, plan_type,
monthly_spend - 400 rows. Two numeric columns (spend, tenure), one
categorical (plan type), and a binary churn flag. The binary flag is
correctly excluded from the numeric suite (shape statistics on yes/no
data are noise; the column still appears in the profile). No timestamp
column, so the temporal branch does not fire.

This dataset is synthetic and deliberately clean (no nulls, no
outliers detected) - it exercises the descriptive suite against a
well-behaved customer table. For a dataset with real messiness, see
the transaction_monitoring or audit_data_quality examples.

## Run it

From the repository root:

    python examples/customer_profiling/run_example.py

## What the engine found

The descriptive math is in output/final/findings/math.json and is
narrated in output/final/narrative_report.md. Key findings:

- monthly_spend: fits normal distribution best (KS distance 0.067);
  mean 285.75 with t-interval CI [280.8, 290.7]; zero outliers by
  MAD modified z-score; skewness exactly 0.0.
- tenure_months: also fits normal best; mean 30.4 months
  (CI [28.7, 32.1]); zero outliers; near-zero skewness.
- plan_type: Shannon entropy 1.585 bits, normalized 0.9999 - three
  plans in essentially uniform distribution.

The churned column (yes/no) is correctly excluded from the numeric
suite - the math stage's column_selection note explains why: shape
statistics on binary data are noise, and inference on them belongs
to the stats stage.

## About the visual report

output/final/report.html charts the data-quality scorecard,
validation, and column completeness. It does not yet visualize the
descriptive-math findings above (distribution fit, outliers, entropy);
that is a planned report enhancement. The math evidence is in
math.json and the narrative report as noted.

## How to verify this package

Open output/final/manifest.json. Recompute the SHA-256 of any file
and compare - matching hashes mean unaltered evidence. audit_log.jsonl
records every stage, decision, rationale, and timestamp. Each findings
file carries its own digest.
