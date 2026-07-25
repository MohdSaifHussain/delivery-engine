## Summary

<!-- What does this PR do? One paragraph. -->

## Type of change

- [ ] Bug fix
- [ ] New feature (new playbook or engine capability)
- [ ] Documentation update
- [ ] Test improvement
- [ ] Refactor (no behaviour change)

## Charter alignment

<!-- Which charter principle(s) does this touch? -->
<!-- e.g. "Does not violate §4.1 (injected-numbers rule)" -->
<!-- e.g. "New playbook per §4.5 — no executor changes" -->

- [ ] I have read PROJECT_CHARTER.md and CLAUDE.md
- [ ] This change does not bypass or weaken a human gate
- [ ] This change does not allow numbers into deliverables outside the
      Findings Store (Charter §4.1)
- [ ] If adding an archetype, it is a new TOML playbook, not executor code
      (Charter §4.5)

## The four gates

```
python -m pytest -q
python -m mypy src/ --strict
python -m ruff check src/ tests/
python -m ruff format --check src/ tests/
```

- [ ] All four gates pass locally

## The loophole hunt

<!-- What is the sneakiest way this change could produce a wrong result
     and not fail a test? How did you guard against it? -->

## Test coverage

<!-- What tests were added or modified? -->

## Related issues

<!-- Closes #XX -->
