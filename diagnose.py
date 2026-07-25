"""diagnose.py - write an environment diagnostic for a bug report.

Run this when something is wrong and you are opening a GitHub issue:

    python diagnose.py

It writes delivery-engine-diagnostic.json in the current directory,
describing the Python environment, installed package versions, and
whether Node is on PATH - the reproduction context a maintainer needs
and cannot guess from a traceback alone.

The record contains no usernames, hostnames, absolute paths,
environment variables, or dataset content. Read it before attaching it;
attaching it is your decision.

The runner writes the same record automatically when a run fails with
an unexpected error, so you usually do not need to run this by hand.
"""
from __future__ import annotations

import sys
from pathlib import Path

from delivery_engine.diagnostics import write_diagnostic


def main(argv: list[str] | None = None) -> Path:
    show = "--show" in (argv or [])

    path = write_diagnostic()
    if path is None:
        print(
            "Could not write the diagnostic file (permission or disk "
            "problem in the current directory). Try running from a "
            "directory you can write to."
        )
        raise SystemExit(1)

    print(f"Diagnostic written: {path}")
    print()
    print("This record contains no usernames, hostnames, absolute paths,")
    print("environment variables, or dataset content.")
    print()
    print("Read it, then attach it to your GitHub issue:")
    print("  https://github.com/MohdSaifHussain/delivery-engine/issues/new")

    if show:
        print()
        print("-" * 60)
        print(path.read_text(encoding="utf-8"))

    return path


if __name__ == "__main__":
    main(sys.argv[1:])
