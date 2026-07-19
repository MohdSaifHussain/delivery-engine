# STEP 21 DECISIONS — The Deterministic Visual Report

**Date:** 19 July 2026 · **Charter:** amended to v0.17 · **Gates at
close:** 331 tests passed (+21), `ruff` clean, `mypy --strict` zero
errors.

## What this step is

The engine's generated `eda_notebook.ipynb` presents the hashed
findings as tables and prose. Step 21 adds a second, presentation-grade
artifact: a self-contained HTML **report** that draws those same hashed
findings as clean charts. New `generate_report.py` runs it against any
sealed package. Zero engine-core changes — a new read-only module plus
a thin CLI.

## The governing principle (not decoration)

Charts are **cognitive scaffolding, not conclusions**. A chart shows
the shape of the data so a reviewer decides *where to look*, never
*what to conclude*. This is the injected-numbers rule made visual: the
report DRAWS hashed findings; it never computes, estimates, or decides.
The lede and the footer say so in the reader's own words — "these
charts are a starting point for your own review" and "the report draws
the evidence, the reader supplies the judgement."

## Design positions

1. **Deterministic, pure function.** `build_report_html(findings…)` is
   a pure function: the same findings produce byte-identical HTML
   (proven by test). No randomness, no network, no AI at runtime. A
   reviewer can re-perform the report exactly and verify every drawn
   number against the store.

2. **Adaptive through the hashed profile, never through judgement.**
   Which charts appear and how tall they are follows the deterministic
   column profile the engine already produced (more columns → a taller
   completeness chart). The data shapes the report by CODE, not by an
   LLM reading the data. This is how the report is data-adaptive
   without violating the constitution.

3. **v1 draws only what is already in the store.** The DAMA scorecard,
   the validation results, and the per-column completeness/profile —
   every number of which already exists in `dq_profile` / `dq_validate`.
   No fraud-rate, class-balance, or correlation charts: those numbers
   are NOT in the store, and computing them to draw them would break
   the injected-numbers rule. Declared as a future extension requiring
   a deterministic aggregation stage to compute-and-hash them first.

4. **Honest colour, honest absence.** Bars are green at ≥99.9% and
   amber below — so a messy dataset renders amber automatically
   (proven: 90% completeness → amber bar, 1,000 exceptions → amber
   validation bar). `accuracy` and `timeliness`, which the engine
   reports as `not scored`, render as dashed "not scored" outlines,
   **never as a 0% bar** — absence of a score is not a score of zero.

5. **The report is a mirror, not a target.** It faithfully shows
   whatever state the data is in. The clean all-green look is what
   honesty looks like when the data is genuinely clean (PaySim,
   synthetic, 100%). A real messy dataset produces amber bars and
   exception counts — which is the report doing its job: surfacing the
   problem so a human fixes it, then re-runs to a greener report. The
   improvement is provable because both reports are deterministic and
   hash-stamped.

6. **Generation date outside the determinism contract.** A professional
   report shows when it was rendered, but a timestamp changes every run.
   Resolution: the date is display metadata in the footer, passed
   explicitly to `build_report_html` (default empty). With a fixed date
   the output is byte-identical; the CLI injects `date.today()`. The
   report's CONTENT stays a pure function of the findings while the
   render date is honest metadata — the "rendered deterministically"
   claim stays true because every number and chart is reproducible.

7. **Self-contained and offline.** One HTML file, inline SVG + CSS, no
   CDN, no external assets — any team opens it in a browser, plug and
   play. The typeface is a tuned professional system-font stack (Segoe
   UI / system sans, semibold headings, monospace for hashes and
   numeric columns): consistent and polished everywhere, with no web-
   font bloat and no network dependency.

8. **Craftsmanship = restraint + resolution.** Simple, legible charts,
   not a busy dashboard. A prose lede at the top (no numbers) and a
   provenance/verification footer at the bottom give the document
   bookends — it concludes rather than stops. The column-profile table
   is left uncoloured on purpose: the completeness chart above it
   carries the colour signal; colouring the table too would be "trying
   too hard."

## Loophole hunt — found and closed (with regressions)

- **H1 (verified safe):** a hostile column name (`<script>…`) is
  HTML-escaped and renders as text, never as a tag.
- **H2 (verified safe):** the source label (a filename/path) is
  escaped the same way — the hunt's first check was a false positive
  (it matched the *escaped* text); confirmed the angle brackets are
  neutralised, so no injection is possible. Regression pins it.
- **H3 (verified safe):** a profile with zero columns still renders a
  valid, complete document.
- **H4 (verified safe):** malformed DAMA scores (>1 or <0) never
  produce negative or overflowing bar widths — the display fraction is
  clamped to [0, 1] before scaling to pixels.
- **H5 (verified acceptable):** a partial `dama_scores` dict renders
  what it has without crashing.

The load-bearing test, `TestInjectedNumbers`, is the report's
equivalent of `verify_artifact_numbers`: it proves every number a
reader sees traces to the findings passed in (the only non-finding
tokens permitted are the two SHA-256 provenance digests, the rule IDs
which come from the findings, and the literal algorithm name
"SHA-256"). A computed or invented figure fails it.

## What was built

- `src/delivery_engine/report.py` — pure functions: findings → inline
  SVG → self-contained HTML; the DAMA, validation, and completeness
  charts; the profile table; escaping; the provenance footer.
- `generate_report.py` — thin CLI wrapper; injects the generation date.
- `tests/test_step21.py` — 21 tests: planted values, not-scored
  handling, all-pass and messy validation, determinism, the
  generation-date isolation, the injected-numbers proof (clean and
  messy), accessible SVG roles, colour-signals-state, package
  integration, clean errors, and the four hunt regressions.

## Accessibility (same standard family as the docs pass)

Charts are SVG with `role="img"` and a `<title>` so assistive tech
reads them (WCAG 1.1.1). Colour is never the only signal — every bar
pairs its colour with a text value label (WCAG 1.4.1).

## Open items (declared, not hidden)

- Richer target-based charts (class balance, rate by segment) await a
  deterministic aggregation stage that computes-and-hashes those
  numbers — see the Step 22/23 roadmap.
- **Step 22 (run lineage):** sequenced immutable `run_NNN` folders so
  the iterative messy→clean cleaning lifecycle is preserved as
  evidence, never overwritten. The anchor is the run sequence number,
  not the date. Includes the human-declared-final guardrail (the
  engine reports the green state as fact; a named human declares a run
  final — the engine never decides "done").
- **Step 23 (trend report):** a deterministic across-runs report
  showing exceptions per attempt and completeness climbing — the
  remediation journey as one picture. Depends on Step 22.
