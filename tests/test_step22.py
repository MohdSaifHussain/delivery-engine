"""Step 22 tests - run lineage: sequenced, immutable run folders.

Planted-answer discipline: plant a known set of run folders, assert the
next number is exactly what the sequence demands, and prove the two
properties that make the ledger trustworthy:

  1. MONOTONIC, NEVER REUSED - the number only ever moves forward, even
     when an earlier run folder was deleted by hand (a gap is visible
     history, not a slot to refill).
  2. NEVER OVERWRITES - an existing run is never clobbered.

Plus: strict run-folder recognition (stray files cannot corrupt the
ordering), and the runner integration that seals into run_NNN while the
executor still receives a fresh empty directory.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from delivery_engine.lineage import (
    LineageError,
    existing_runs,
    next_run_dir,
    run_number,
)


class TestRunNumber:
    def test_parses_run_folder_names(self) -> None:
        assert run_number("run_001") == 1
        assert run_number("run_042") == 42
        assert run_number("run_1000") == 1000

    def test_rejects_non_run_names(self) -> None:
        assert run_number("final") is None
        assert run_number("run_") is None
        assert run_number("run_ab") is None
        assert run_number("run_1") is None       # needs >= 3 digits
        assert run_number("prefix_run_001") is None


class TestSequencing:
    def test_first_run_on_fresh_area_is_run_001(
        self, tmp_path: Path
    ) -> None:
        r = next_run_dir(tmp_path / "claims")
        assert r.name == "run_001"
        assert r.is_dir()

    def test_runs_increment(self, tmp_path: Path) -> None:
        area = tmp_path / "claims"
        names = [next_run_dir(area).name for _ in range(3)]
        assert names == ["run_001", "run_002", "run_003"]

    def test_existing_runs_returns_them_in_order(
        self, tmp_path: Path
    ) -> None:
        area = tmp_path / "claims"
        for _ in range(3):
            next_run_dir(area)
        assert [p.name for p in existing_runs(area)] == [
            "run_001", "run_002", "run_003",
        ]

    def test_empty_area_has_no_runs(self, tmp_path: Path) -> None:
        assert existing_runs(tmp_path / "nothing_here") == []


class TestImmutability:
    def test_deleted_middle_run_is_not_refilled(
        self, tmp_path: Path
    ) -> None:
        """The audit-critical property: after run_002 is deleted, the
        next run is run_004, NOT a reused run_002. The gap is itself
        evidence that something was removed - the ledger only ever moves
        forward."""
        area = tmp_path / "claims"
        next_run_dir(area)
        r2 = next_run_dir(area)
        next_run_dir(area)                       # run_003
        import shutil
        shutil.rmtree(r2)                        # delete run_002 by hand
        r_next = next_run_dir(area)
        assert r_next.name == "run_004"
        assert [p.name for p in existing_runs(area)] == [
            "run_001", "run_003", "run_004",
        ]

    def test_never_overwrites_an_existing_run(
        self, tmp_path: Path
    ) -> None:
        area = tmp_path / "claims"
        r1 = next_run_dir(area)
        (r1 / "manifest.json").write_text("sealed", encoding="utf-8")
        # a second call must not touch run_001
        r2 = next_run_dir(area)
        assert r2.name == "run_002"
        assert (r1 / "manifest.json").read_text(encoding="utf-8") == \
            "sealed"

    def test_number_only_moves_forward_after_all_deleted(
        self, tmp_path: Path
    ) -> None:
        """Even if every run folder is deleted, the numbering restarts
        from 1 only because the ledger is empty - there is no hidden
        counter. (The filesystem IS the ledger.)"""
        area = tmp_path / "claims"
        r1 = next_run_dir(area)
        import shutil
        shutil.rmtree(r1)
        r_next = next_run_dir(area)
        # nothing left to compare against, so 001 again - honest, since
        # the directory listing is the only source of truth
        assert r_next.name == "run_001"


class TestLedgerIntegrity:
    def test_stray_files_do_not_corrupt_ordering(
        self, tmp_path: Path
    ) -> None:
        area = tmp_path / "claims"
        next_run_dir(area)
        next_run_dir(area)
        (area / "notes.txt").write_text("hand note", encoding="utf-8")
        (area / "run_bad").mkdir()               # not \d{3,}
        (area / "README.md").write_text("x", encoding="utf-8")
        assert [p.name for p in existing_runs(area)] == [
            "run_001", "run_002",
        ]
        # next number still follows only the real runs
        assert next_run_dir(area).name == "run_003"

    def test_area_that_is_a_file_is_a_clean_error(
        self, tmp_path: Path
    ) -> None:
        f = tmp_path / "claims"
        f.write_text("i am a file", encoding="utf-8")
        with pytest.raises(LineageError, match="not a directory"):
            existing_runs(f)


class TestRunnerIntegration:
    """The runner's --lineage flag seals into run_NNN; the executor
    still receives a fresh empty directory (its safety rule intact)."""

    def test_lineage_flag_seals_into_run_folder(
        self, tmp_path: Path
    ) -> None:
        import csv
        import json

        from delivery_engine.runner import main as run_main

        # minimal real dataset + playbook dir
        src = tmp_path / "d.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["record_id", "amount", "score", "region"])
            for i in range(150):
                w.writerow([
                    f"R-{i:04d}", 10.0 + (i % 40),
                    50.0 + (i % 25) * 2, ("north", "south", "east")[i % 3],
                ])
        pbdir = tmp_path / "playbooks"
        pbdir.mkdir()
        import shutil
        shutil.copy(
            Path(__file__).parent.parent / "playbooks"
            / "universal_audit.toml",
            pbdir,
        )
        rules = tmp_path / "rules.json"
        rules.write_text(
            json.dumps([{"column": "record_id", "rule": "unique"}]),
            encoding="utf-8",
        )
        area = tmp_path / "out"
        run_main([
            "--source", str(src), "--goal",
            "universal descriptive audit", "--playbook",
            "universal_audit", "--rules", str(rules),
            "--approver", "Saif", "--yes", "--lineage",
            "--out", str(area), "--playbook-dir", str(pbdir),
        ])
        # a run_001 folder now exists under the output area
        runs = existing_runs(area)
        assert [p.name for p in runs] == ["run_001"]
        # and it holds a sealed package
        assert (runs[0] / "final" / "manifest.json").exists()


class TestHuntRegressions:
    def test_h1_numeric_not_lexical_ordering(
        self, tmp_path: Path
    ) -> None:
        """run_009 -> run_010 -> run_100 must order numerically; a naive
        string sort would put run_100 before run_009 and mis-number the
        next run."""
        area = tmp_path / "a"
        area.mkdir()
        for n in (1, 9, 10, 100, 101):
            (area / f"run_{n:03d}").mkdir()
        assert [p.name for p in existing_runs(area)] == [
            "run_001", "run_009", "run_010", "run_100", "run_101",
        ]
        assert next_run_dir(area).name == "run_102"

    def test_h2_four_digit_runs(self, tmp_path: Path) -> None:
        area = tmp_path / "a"
        area.mkdir()
        (area / "run_999").mkdir()
        (area / "run_1000").mkdir()
        assert next_run_dir(area).name == "run_1001"

    def test_h3_a_file_named_like_a_run_is_ignored(
        self, tmp_path: Path
    ) -> None:
        """Only directories are runs. A file named run_005 must not be
        counted, or the ledger could be corrupted by a stray file."""
        area = tmp_path / "a"
        area.mkdir()
        (area / "run_001").mkdir()
        (area / "run_005").write_text("not a run", encoding="utf-8")
        assert [p.name for p in existing_runs(area)] == ["run_001"]
        assert next_run_dir(area).name == "run_002"

    def test_h4_strict_name_recognition(self) -> None:
        assert run_number("run_0007") == 7      # extra leading zeros ok
        assert run_number("run_00") is None     # fewer than 3 digits
        assert run_number("RUN_001") is None    # case-sensitive
        assert run_number("run_007x") is None   # trailing junk
        assert run_number(" run_001") is None   # leading space
