# Historical — development scripts

This folder preserves scripts written during the development of the
Delivery Engine that are not part of the shipped, gated surface.

These scripts were useful during the build — for exploring datasets,
generating playbooks, running experiments — but they were never put
through the full gate discipline (tests, ruff, mypy strict, loophole
hunt) that shipped code carries. Keeping them here rather than deleting
them is the same principle the engine runs on: preserve the evidence,
in order, and let it be re-performed.

## Contents

- discover_dataset.py — dataset exploration utility
- dump_code.py — code dump utility used during development
- generate_playbook.py — local playbook generator experiment
- project_dump.txt — project state snapshot from development
- run_fraud.py — local fraud dataset runner (PaySim experiments)
- run_insurance.py — local insurance dataset runner
- run_supplychain.py — local supply chain dataset runner
- scale_test.py — scale testing script

## Note

The shipped runners live in the examples/ folder — one per example,
each run through the full gate discipline. The scripts here are the
earlier, ungated equivalents. For the canonical way to run the engine,
see QUICKSTART.md and the examples/ folder.
