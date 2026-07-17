#!/usr/bin/env python
"""Run any dataset through a Delivery Engine playbook.

    python run_project.py --source data/my.csv --goal "audit Q3 claims" \
        --playbook universal_audit --approver "Your Name"

All logic lives (typed, tested, gated) in delivery_engine.runner;
this file is deliberately three lines - write your own convenience
wrapper the same way instead of copy-pasting a runner per project.
"""
from delivery_engine.runner import main

if __name__ == "__main__":
    main()
