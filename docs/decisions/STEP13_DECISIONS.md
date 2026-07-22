# STEP 13 DECISIONS — deterministic multi-format deliverables

**Date:** 13 July 2026 · **Scope:** Word / PowerPoint / Excel / PDF output
declared per-playbook, content-verification stage, charter amendment v0.9.

## 1. The central architecture decision (charter-critical)

The Anthropic document skills (docx, pptx, xlsx, pdf) operate in two modes:

1. **Via the Claude API** — Claude AUTHORS the document content in a
   sandbox. This requires an API key and, decisively, lets the AI write
   numbers. That directly violates charter 4.1 (the injected-numbers
   rule). FORBIDDEN in this engine.
2. **As best-practice recipes** — the SKILL.md files document how to use
   the underlying deterministic libraries (pptxgenjs, docx-js, openpyxl,
   LibreOffice PDF conversion) correctly. The engine uses THIS.

The value taken from the skills is their encoded best-practice knowledge,
not their authoring behaviour. A deterministic document builder applying
skill-grade technique is fully charter-aligned; an API call that lets
Claude write the figures is the one thing the project exists to prevent.
Researched against official Anthropic docs (platform.claude.com Agent
Skills overview, quickstart, and the anthropics/skills repository).

## 2. What was built

- `delivery_engine/documents.py`: one deterministic builder per format,
  each a pure function of the store snapshot. Generator scripts (JS for
  docx/pptx, Python for xlsx) are the auditable artifacts; their SHA-256
  is recorded.
- Schema V13: `[deliverables] formats = [...]`, per-playbook (Saif's
  decision). Backward-compatible — absent key defaults to markdown, so
  every pre-Step-13 playbook keeps its exact meaning. All four shipped
  archetypes verified unchanged.
- Executor: documents build at package time from the full store
  snapshot, verified, then hashed into the manifest as package evidence.

## 3. The verification stage (Saif's decision: hard on numbers, soft on prose)

After each document is produced, it is re-read with the format-appropriate
tool (pandoc for docx, pdftotext for pdf, openpyxl for xlsx, python-pptx
for pptx — the same readers the skills use) and checked:

- HARD gate: every store-sourced number in the expected set must appear.
  A missing number means the deliverable dropped a finding — the pipeline
  STOPS. Proven by test (removing a number fails verification).
- SOFT check: declared prose sections that are absent are logged, not
  fatal.
- Format-aware expected set: detail formats (docx/xlsx/pdf) require every
  per-column null count; decks (pptx) require summary numbers only. A
  board deck listing every null count would be a worse deck — this is a
  correct professional distinction, verified as such.

## 4. Honest boundaries

- PDF requires LibreOffice (docx->pdf); the builder fails loudly with a
  clear message if soffice is absent, and suggests docx instead.
- xlsx recalc (cached formula values) is best-effort via LibreOffice;
  the workbook is valid without it. Formulas (not hardcoded totals) are
  used per the xlsx skill.
- The .json/.md evidence layer is never replaced. Documents are additive
  consumable deliverables sitting on top of the re-performable evidence.

## 5. Gates

171 tests (156 prior + 15 new: per-format build+verify, the verification
gate catching a removed number, format-aware pptx scope, V13 schema
validation, and a full formats-enabled end-to-end run), ruff clean, mypy
strict zero errors across 11 source files. Demonstrated end-to-end on the
real 10k-row transaction dataset producing all five formats, each
verified.

## 6. Changed files

- src/delivery_engine/documents.py (new)
- src/delivery_engine/playbook.py (V13: output_formats)
- src/delivery_engine/executor.py (document build + verification stage)
- tests/test_step13.py (new)
- pyproject.toml (python-pptx, markitdown for verification)
- PROJECT_CHARTER.md (v0.9)
