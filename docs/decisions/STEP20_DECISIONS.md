# STEP 20 DECISIONS — Source Adapters & the Single-Reader Principle

**Date:** 18 July 2026 · **Charter:** amended to v0.16 · **Gates at
close:** 310 tests passed, `ruff` clean, `mypy --strict` zero errors.
AnalystKit v2.1.0 ships alongside: 75 tests, its own three gates green.

## What this step is

Two things at once, and the second is the important one:

1. The computational stages (model, stats, math) accepted CSV only — a
   declared v1 line recorded in STEP15/STEP17 "Open items". They now
   accept Parquet, `.xlsx` and SQLite.
2. **The Single-Reader Principle.** Those stages used to read with
   `pandas.read_csv` while the kit stages read the same file through
   AnalystKit's DuckDB loader. Two parsers, one file — the divergence
   risk carried openly on the register since the AnalystKit v2.0.x
   type-boundary bugs, where a mismatch between two type systems
   produced 1.5M silent false failures on valid data.
   `delivery_engine.sources` is now the only loading path for the
   computational stages, and it **parses nothing itself**: it delegates
   to `analystkit.engine.load_source`, the very function the profile
   gate uses. Whatever the gate saw, the stages see. The register item
   retires.

## Phase A — verified before designing (never assumed)

| Probe | Result |
|---|---|
| Does AnalystKit accept these formats today? | `.csv`, `.xlsx`, `.db` yes; **`.parquet` refused**. So the gate would have refused what the stages accepted → AnalystKit v2.1.0 was required, not optional. |
| How did AnalystKit read `.xlsx`? | **via pandas** — the divergence living inside the kit itself. Now DuckDB's `excel` extension. |
| `read_xlsx` type inference | `record_id VARCHAR`, `amount **DOUBLE**`, `tier VARCHAR` — numerics are DOUBLE, exactly as the extension documents. |
| Nested Parquet through `DESCRIBE` | `INTEGER[]`, `STRUCT(a INTEGER, b VARCHAR)` — detectable by type string; refusal is feasible and precise. |
| Parquet timestamps | `TIMESTAMP` and `TIMESTAMP WITH TIME ZONE` both preserved. |
| SQLite mixed-type column | surfaces as **`BLOB`** with byte values (`bytearray(b'txt')`). |
| CSV renamed `.parquet` | `InvalidInputException: No magic bytes found` — needs wrapping in our voice. |

## The formats and their rules

| Format | Rule | Source |
|---|---|---|
| `.csv` | DuckDB `read_csv`, RFC 4180 quoting, `strict_mode=false` | unchanged |
| `.parquet` | DuckDB `read_parquet`; **nested/semi-structured columns (LIST, STRUCT, MAP, UNION, VARIANT) refused by name** | spec hosted in `apache/parquet-format`, Thrift IDL authoritative (parquet.apache.org/docs); Variant went official **February 2026** |
| `.xlsx` | DuckDB `excel` extension; **first sheet** and **numerics→DOUBLE** are disclosed rules; missing extension = loud error naming `INSTALL excel;` | duckdb.org excel extension docs |
| `.xls` | clean refusal + remedy | the same docs state `.xls` is **not** supported |
| `.db`/`.sqlite` | `ATTACH ... (TYPE sqlite)`; exactly one user table in v1 | duckdb.org sqlite extension docs |

## Format parity — claimed honestly, and scoped

The crown-jewel test. The same logical table in four containers:

- **CSV = Parquet = SQLite:** byte-identical stats **and** math
  findings digests.
- **All four agree on math** (it is value-based throughout).
- **XLSX stats digests differ — and the suite says so rather than
  hiding it.** Root-caused, not guessed: the excel extension's
  documented DOUBLE inference makes integer `1` arrive as `1.0`, so
  the disclosed class label reads `"1.0"` where CSV reads `"1"`. A
  line-by-line diff showed *only* that: every proportion, CI, p-value,
  BH adjustment and effect size identical. The test therefore pins
  **value-level identity plus the label difference** as the honest
  claim. Normalizing the labels away would have hidden a real,
  documented container property — evidence tools do not do that.

## Constitutional changes

- `parquet` joins `KNOWN_SOURCE_TYPES` (V-rule vocabulary).
- **A real gap found during wiring:** `planner._source_type` had no
  parquet branch, so a `.parquet` source fell through to `"csv"` and
  would have passed a CSV-only playbook's requirement check silently.
  A requirement that says nothing is worse than no requirement. Fixed.
- `universal_audit` and `segment_comparison` accept the new types; the
  generator emits the extended `source_types` (a draft should not be
  narrower than the engine it runs on) and **drafts its rules through
  the single reader** — drafting rules against a different parser than
  the one that validates them is precisely the divergence this step
  ends. Verified end-to-end: a generated draft run against a Parquet
  source produced **5 rules, 0 exceptions**, with `days_late` values
  drafted as native integers (the v2.0.2 per-dtype contract holding
  across formats).

## Two test fixtures corrected — and why that is the fix working

`test_step15` asserted `positive_class == "yes"`; `test_step18` keyed
groups by `"no"`/`"yes"`. Both broke on the swap. Investigation (not
assumption): DuckDB's CSV sniffer types a yes/no column **BOOLEAN**,
and the profile gate had **always** reported it BOOLEAN — while the
pandas-reading stages saw strings and silently disagreed with the gate.
The fixtures were recording the divergence. The code is right; the
fixtures now record the single-reader truth, with the reason in the
test body. No statistical method, hash, rounding rule, gate semantic or
V-rule meaning changed anywhere in this step.

## Loophole hunt — found and closed

- **H1 (real disclosure gap, fixed):** a Parquet `TIMESTAMP WITH TIME
  ZONE` is an instant; the reader renders it in UTC, so an event at
  midnight IST lands on the **previous UTC day**. The instant is
  correct, but day-level findings (gaps, daily counts, trends) would be
  silently timezone-shifted. The engine does not re-zone anyone's data
  — it now **discloses** the UTC reading inside the hashed findings
  (`source_timezone_note`), and a naive-timestamp source carries no
  note. Regression pins both directions.
- **H2 (real gap, fixed):** SQLite's dynamic typing lets one column mix
  integers and text; DuckDB surfaces it as `BLOB` raw bytes. A stage
  would have profiled bytearrays as categories — fabrication. Now a
  refusal naming the column and the `CAST` remedy; a cleanly typed
  SQLite column still loads.
- **H3 (verified, no change):** a zero-row Parquet loads (it is a valid
  file); the stage's existing feasibility rules decide, with a written
  reason. The reader should not invent policy the stages already own.
- **H4 (verified, no change):** a directory named `*.parquet` (the
  dataset-directory convention) dies as a clean `SourceError` in the
  engine's voice. Directory datasets are a declared future extension.

## What was built

- `src/delivery_engine/sources.py` — the single reader:
  `SUPPORTED_SUFFIXES`, `SourceError`, `load_dataframe`, the BLOB
  refusal, the timezone disclosure.
- `model.py`, `stats.py`, `mathkit.py` — swapped to the shared loader;
  their CSV-only refusals retired; math surfaces the timezone note.
- `playbook.py` (`parquet` in `KNOWN_SOURCE_TYPES`), `planner.py`
  (`_source_type` parquet branch), `generator.py` (single-reader rule
  drafting, extended `source_types`), the two computational playbooks.
- `tests/test_step20.py` — 19 tests: parity (3), determinism,
  refusals (8), single-reader agreement with the gate, e2e Parquet
  package, and the four hunt regressions.
- AnalystKit **v2.1.0**: parquet + nested refusal, `.xlsx` via the
  excel extension (replacing pandas), `.xls` refusal, updated
  unsupported-source message, `TestSourceAdapters` (5 tests), README
  changelog including the honest behaviour note that `.xlsx` numeric
  columns now report `DOUBLE`.

## Open items (declared, not hidden)

- Multi-sheet `.xlsx` addressing and multi-table SQLite selection
  (v1 rules are first-sheet and single-table by design).
- Parquet dataset **directories** and partitioned globs.
- Postgres/MySQL live connections (`KNOWN_SOURCE_TYPES` names them;
  the single reader does not implement them yet).
- The DuckDB version range is still unpinned in `pyproject.toml` —
  cheap insurance against sniffer drift, recorded since step 18.
