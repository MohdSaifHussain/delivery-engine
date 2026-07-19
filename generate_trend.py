#!/usr/bin/env python3
"""Generate the across-runs remediation trend report for a dataset.

Usage:
    python generate_trend.py <dataset_output_area>

Reads the run_001 .. run_NNN lineage under the given output area (built
by running the engine with --lineage) and writes trend.html into it.
Deterministic: no AI, no network, no computed cross-run figures - the
report reads each run's hashed findings and draws the values. See
STEP23_DECISIONS.md.
"""
from __future__ import annotations

import sys

from delivery_engine.trend import TrendError, trend_from_area


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] in ("-h", "--help"):
        print(__doc__)
        raise SystemExit(0 if args and args[0] in ("-h", "--help") else 2)
    try:
        out = trend_from_area(args[0])
    except TrendError as exc:
        raise SystemExit(f"Could not build trend report: {exc}") from exc
    print(f"Trend report written: {out}")


if __name__ == "__main__":
    main()
