#!/usr/bin/env python3
"""Generate the deterministic visual report for a sealed package.

Usage:
    python generate_report.py <package_dir>

Reads the package's hashed dq_profile and dq_validate findings and
writes report.html into the same directory. Deterministic: no AI, no
network, same findings -> byte-identical HTML. See STEP21_DECISIONS.md.
"""
from __future__ import annotations

import sys

from delivery_engine.report import ReportError, report_from_package


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] in ("-h", "--help"):
        print(__doc__)
        raise SystemExit(0 if args and args[0] in ("-h", "--help") else 2)
    try:
        out = report_from_package(args[0])
    except ReportError as exc:
        raise SystemExit(f"Could not build report: {exc}") from exc
    print(f"Report written: {out}")


if __name__ == "__main__":
    main()
