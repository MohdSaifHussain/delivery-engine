---
name: Bug report
about: Something is broken or producing wrong output
labels: bug
---

## What happened

<!-- Describe the bug clearly. What did you expect vs what actually happened? -->

## Steps to reproduce

```bash
# Exact commands you ran
```

## Environment

- OS:
- Python version: (`python --version`)
- Delivery Engine version: (git tag or `pip show delivery-engine`)
- analystkit version: (`pip show analystkit`)

## Output

<!-- Paste the error message or unexpected output here -->

```
paste here
```

## Package artifacts (if relevant)

<!-- If the bug is in a generated package, paste or attach:
     - the relevant lines from audit_log.jsonl
     - the error from manifest.json verification (if applicable) -->

## Diagnostic record

<!-- Run `python diagnose.py` and attach or paste
     delivery-engine-diagnostic.json here. It records the environment
     and package versions needed to reproduce, and contains no
     usernames, paths, or dataset content. If the run failed
     unexpectedly, the file was already written for you. -->

```json
paste here
```

## Charter section (if known)

<!-- Which principle might be violated? e.g. "§4.1 injected-numbers rule" -->
<!-- Leave blank if unsure -->
