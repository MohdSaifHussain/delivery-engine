"""delivery_engine.lineage - sequenced, immutable run folders.

Step 22. Cleaning a messy dataset is iterative, never one-shot: you
profile, find issues, fix some, re-run, find the issues the first fix
exposed, fix those, re-run again. That lifecycle - messy to clean
across several attempts - is the most audit-relevant artifact the
engine produces. It must be preserved as evidence, never overwritten.

The executor already refuses a non-empty output directory, so stale
files cannot be hash-certified as a new run's evidence. That safety
rule and the need to keep history were in tension: overwriting to
re-run loses the lineage. This module resolves the tension by
SATISFYING the safety rule rather than changing it - each run gets its
own fresh, sequentially numbered folder, so the executor always sees an
empty directory and the history is preserved by construction.

THE ANCHOR IS THE RUN SEQUENCE NUMBER, NOT THE DATE. Two iterations can
happen the same afternoon or weeks apart; a date says WHEN, not WHICH
ATTEMPT. run_001, run_002, ... is the identity: monotonically
increasing, never reused, never renumbered. The generation date lives
inside each run's report as metadata (Step 21), not as the folder's
identity.

The directory listing IS the lineage: a dataset's output area holds
run_001 .. run_NNN in order, each a complete, hash-sealed package with
its own findings and report. A reviewer opens run_003 and run_005 side
by side and sees completeness climbing and exceptions shrinking - an
ordered, immutable breadcrumb trail that cannot lie. No database, no
magic; the filesystem is the ledger.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Final

__all__ = [
    "RUN_DIR_RE",
    "LineageError",
    "existing_runs",
    "next_run_dir",
    "run_number",
]

# A run folder is exactly run_ followed by a zero-padded number. The
# strict pattern is what lets the listing be trusted as the ledger:
# nothing else is mistaken for a run.
RUN_DIR_RE: Final = re.compile(r"^run_(\d{3,})$")
_PAD: Final = 3


class LineageError(Exception):
    """A lineage operation could not proceed, stated with the reason."""


def run_number(name: str) -> int | None:
    """The sequence number of a run folder name, or None if the name is
    not a run folder. run_007 -> 7; anything else -> None."""
    m = RUN_DIR_RE.match(name)
    return int(m.group(1)) if m else None


def existing_runs(dataset_area: Path) -> list[Path]:
    """Every run_NNN folder under a dataset's output area, in sequence
    order. Empty if the area does not exist yet - the first run creates
    it. Non-run entries are ignored, so a stray file never corrupts the
    ledger's ordering."""
    if not dataset_area.exists():
        return []
    if not dataset_area.is_dir():
        raise LineageError(
            f"Dataset output area {dataset_area} exists but is not a "
            f"directory. Run lineage needs a directory it owns."
        )
    runs = [
        p for p in dataset_area.iterdir()
        if p.is_dir() and run_number(p.name) is not None
    ]
    return sorted(runs, key=lambda p: run_number(p.name) or 0)


def next_run_dir(dataset_area: Path) -> Path:
    """Reserve and return the next run_NNN directory under a dataset's
    output area.

    The number is one greater than the highest existing run - never a
    reused or back-filled number, even if an earlier run folder was
    deleted by hand (the ledger only ever moves forward, so a missing
    run_004 is itself visible history, not a slot to refill). The
    directory is created empty and returned; the executor then seals
    the run into it and its non-empty-directory safety rule guards it
    from that point on.
    """
    runs = existing_runs(dataset_area)
    highest = max((run_number(p.name) or 0 for p in runs), default=0)
    nxt = highest + 1
    run_dir = dataset_area / f"run_{nxt:0{_PAD}d}"
    if run_dir.exists():
        # Only reachable if the folder was created between our scan and
        # now. Never overwrite - fail loudly so no run is silently lost.
        raise LineageError(
            f"Next run directory {run_dir} already exists. Runs are "
            f"never overwritten; resolve the conflict before re-running."
        )
    dataset_area.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir()
    return run_dir
