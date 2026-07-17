"""Step 20 tests - source adapters and the single-reader principle.

The constitutional positions under test:

- ONE READER. Every computational stage loads through
  delivery_engine.sources, which delegates to the same AnalystKit
  DuckDB loader the profile gate uses. Whatever the gate saw, the
  stages see. (The 291 pre-existing tests are themselves the
  regression harness for this swap; two of their fixtures encoded the
  OLD pandas view of a yes/no column and were corrected with the
  reason recorded - see STEP20_DECISIONS.md.)
- FORMAT PARITY, HONESTLY SCOPED. The same logical data in CSV,
  Parquet and SQLite produces byte-identical findings digests through
  the stats and math stages. XLSX is tested at the VALUE level, not
  the digest level, because DuckDB's excel extension documents that
  numeric cells are inferred as DOUBLE - so an integer 1 arrives as
  1.0 and the disclosed class label reads "1.0" rather than "1". The
  statistics are identical; only the label spelling differs. Claiming
  digest parity for xlsx would require normalizing away a real,
  documented container difference - this suite refuses to hide it and
  tests what is actually true instead.
- REFUSALS ARE LOUD AND SPECIFIC, in the engine's voice, naming the
  columns/tables/remedy: nested Parquet (including the 2026 VARIANT
  type), .xls, multi-table SQLite, a renamed CSV, an unsupported
  suffix.
- DETERMINISM PER FORMAT: same file twice -> same digest.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

import duckdb
import pytest
from analystkit.ai import findings_digest
from analystkit_mcp.tools import tool_profile

from delivery_engine import approve_plan, load_playbook, make_plan, run
from delivery_engine.mathkit import MathError, run_math
from delivery_engine.sources import (
    SUPPORTED_SUFFIXES,
    SourceError,
    load_dataframe,
)
from delivery_engine.stats import StatsError, run_inference

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
UNIVERSAL = PLAYBOOKS / "universal_audit.toml"
APPROVALS: dict[str, Any] = {"plan_approval": "Saif"}


# ── fixtures: one logical dataset, four containers ───────────────────────────


def _write_csv(path: Path, rows: int = 200) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["record_id", "converted", "segment", "spend"])
        for i in range(rows):
            seg = "a" if i % 2 == 0 else "b"
            conv = 1 if (i % 10) < (8 if seg == "a" else 1) else 0
            w.writerow([f"C-{i:05d}", conv, seg, round(100.0 + i * 1.5, 2)])
    return path


def _all_formats(tmp_path: Path) -> dict[str, Path]:
    """The SAME logical table written four ways."""
    csv_p = _write_csv(tmp_path / "p.csv")
    con = duckdb.connect()
    con.execute("INSTALL excel; LOAD excel")
    pq = tmp_path / "p.parquet"
    xl = tmp_path / "p.xlsx"
    con.execute(
        f"COPY (SELECT * FROM read_csv('{csv_p}')) TO '{pq}' "
        f"(FORMAT parquet)"
    )
    con.execute(
        f"COPY (SELECT * FROM read_csv('{csv_p}')) TO '{xl}' "
        f"(FORMAT xlsx, HEADER true)"
    )
    rows = con.execute(f"SELECT * FROM read_csv('{csv_p}')").fetchall()
    con.close()
    db = tmp_path / "p.db"
    sc = sqlite3.connect(db)
    sc.execute(
        "CREATE TABLE t (record_id TEXT, converted INTEGER, "
        "segment TEXT, spend REAL)"
    )
    sc.executemany("INSERT INTO t VALUES (?,?,?,?)", rows)
    sc.commit()
    sc.close()
    return {"csv": csv_p, "parquet": pq, "xlsx": xl, "sqlite": db}


# ── the crown jewel: format parity ───────────────────────────────────────────


class TestFormatParity:
    def test_stats_digests_identical_across_csv_parquet_sqlite(
        self, tmp_path: Path
    ) -> None:
        f = _all_formats(tmp_path)
        digests = {
            name: findings_digest(run_inference(
                str(f[name]), "full_inference", "converted",
                ["segment"], ["spend"], 0.05,
            ))
            for name in ("csv", "parquet", "sqlite")
        }
        assert len(set(digests.values())) == 1, digests

    def test_math_digests_identical_across_all_four_formats(
        self, tmp_path: Path
    ) -> None:
        """Descriptive math is value-based throughout, so even the
        xlsx DOUBLE inference cannot move it: all four agree."""
        f = _all_formats(tmp_path)
        digests = {
            name: findings_digest(run_math(
                str(p), "all", ["spend"], ["segment"], [],
            ))
            for name, p in f.items()
        }
        assert len(set(digests.values())) == 1, digests

    def test_xlsx_statistics_identical_only_labels_differ(
        self, tmp_path: Path
    ) -> None:
        """The honest xlsx claim: DuckDB's excel extension documents
        numeric inference as DOUBLE, so the disclosed class label reads
        '1.0' where CSV reads '1'. Every NUMBER must still match
        exactly - this test pins that, rather than normalizing a real
        container difference away."""
        f = _all_formats(tmp_path)
        a = run_inference(str(f["csv"]), "full_inference", "converted",
                          ["segment"], ["spend"], 0.05)
        b = run_inference(str(f["xlsx"]), "full_inference", "converted",
                          ["segment"], ["spend"], 0.05)
        assert a["positive_class"] == "1"
        assert b["positive_class"] == "1.0"   # the documented DOUBLE
        # every statistic identical
        pa = {p["scope"]: p for p in a["proportions"]}
        pb = {p["scope"]: p for p in b["proportions"]}
        assert set(pa) == set(pb)
        for scope, entry in pa.items():
            for key in ("n", "count_positive", "rate", "ci_low",
                        "ci_high"):
                assert entry[key] == pb[scope][key], (scope, key)
        for ta, tb in zip(a["tests"], b["tests"], strict=True):
            assert ta.get("p_value") == tb.get("p_value")
            assert ta.get("p_adjusted_bh") == tb.get("p_adjusted_bh")
            assert (ta.get("effect_size_cramers_v")
                    == tb.get("effect_size_cramers_v"))

    def test_determinism_per_format(self, tmp_path: Path) -> None:
        for p in _all_formats(tmp_path).values():
            d1 = findings_digest(run_math(str(p), "all", ["spend"],
                                          ["segment"], []))
            d2 = findings_digest(run_math(str(p), "all", ["spend"],
                                          ["segment"], []))
            assert d1 == d2, p.name


# ── refusals, surfaced through the engine's own voice ────────────────────────


class TestRefusals:
    def test_nested_parquet_refused_naming_columns(
        self, tmp_path: Path
    ) -> None:
        pq = tmp_path / "nested.parquet"
        duckdb.execute(
            f"COPY (SELECT 1 AS id, [1, 2] AS tags, "
            f"{{'k': 1}} AS meta) TO '{pq}' (FORMAT parquet)"
        )
        with pytest.raises(SourceError) as exc:
            load_dataframe(str(pq))
        msg = str(exc.value)
        assert "tags" in msg and "meta" in msg
        assert "silent flatten" in msg

    def test_nested_parquet_surfaces_through_the_math_stage(
        self, tmp_path: Path
    ) -> None:
        """The stage speaks its own exception type - no raw DuckDB or
        kit traceback reaches the caller."""
        pq = tmp_path / "nested.parquet"
        duckdb.execute(
            f"COPY (SELECT 1 AS id, [1, 2] AS tags) TO '{pq}' "
            f"(FORMAT parquet)"
        )
        with pytest.raises(MathError, match="tags"):
            run_math(str(pq), "all", [], [], [])

    def test_xls_refused_with_remedy(self, tmp_path: Path) -> None:
        xls = tmp_path / "legacy.xls"
        xls.write_bytes(b"\xd0\xcf\x11\xe0 not really")
        with pytest.raises(SourceError, match=r"\.xlsx"):
            load_dataframe(str(xls))

    def test_multi_table_sqlite_refused_naming_tables(
        self, tmp_path: Path
    ) -> None:
        db = tmp_path / "multi.db"
        sc = sqlite3.connect(db)
        sc.execute("CREATE TABLE orders (id INTEGER)")
        sc.execute("CREATE TABLE customers (id INTEGER)")
        sc.commit()
        sc.close()
        with pytest.raises(SourceError) as exc:
            load_dataframe(str(db))
        msg = str(exc.value)
        assert "orders" in msg and "customers" in msg

    def test_renamed_csv_wearing_parquet_dies_cleanly(
        self, tmp_path: Path
    ) -> None:
        fake = tmp_path / "fake.parquet"
        fake.write_bytes(_write_csv(tmp_path / "real.csv").read_bytes())
        with pytest.raises(SourceError, match="renamed CSV"):
            load_dataframe(str(fake))

    def test_unsupported_suffix_lists_what_is_supported(
        self, tmp_path: Path
    ) -> None:
        j = tmp_path / "data.json"
        j.write_text("[]", encoding="utf-8")
        with pytest.raises(SourceError, match="Supported"):
            load_dataframe(str(j))

    def test_missing_source_is_a_clean_error(self, tmp_path: Path) -> None:
        with pytest.raises(StatsError, match="not found"):
            run_inference(str(tmp_path / "ghost.parquet"),
                          "full_inference", "t", [], [], 0.05)

    def test_supported_suffixes_are_declared_once(self) -> None:
        assert ".parquet" in SUPPORTED_SUFFIXES
        assert ".xlsx" in SUPPORTED_SUFFIXES
        assert ".csv" in SUPPORTED_SUFFIXES


# ── the reader agrees with the gate ──────────────────────────────────────────


class TestSingleReader:
    def test_stage_dtypes_match_the_profile_gate(
        self, tmp_path: Path
    ) -> None:
        """The divergence this step closes: the profile gate always
        typed a yes/no column BOOLEAN while the stages (pandas) read
        strings. Now both come from one reader."""
        src = tmp_path / "yn.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "flag"])
            for i in range(20):
                w.writerow([i, "yes" if i % 2 else "no"])
        gate = {c["name"]: c["dtype"]
                for c in json.loads(tool_profile(str(src), None))
                ["findings"]["columns"]}
        df = load_dataframe(str(src))
        assert gate["flag"] == "BOOLEAN"
        assert str(df["flag"].dtype) == "bool"

    def test_parquet_values_equal_csv_values(
        self, tmp_path: Path
    ) -> None:
        f = _all_formats(tmp_path)
        a = load_dataframe(str(f["csv"]))
        b = load_dataframe(str(f["parquet"]))
        assert a["spend"].tolist() == b["spend"].tolist()
        assert a["converted"].tolist() == b["converted"].tolist()


# ── end to end: a Parquet source through the whole engine ────────────────────


class TestEndToEndParquet:
    def test_universal_audit_on_parquet_seals_a_package(
        self, tmp_path: Path
    ) -> None:
        # A repeating spend keeps the numeric column out of the
        # planner's id_column classification (200 distinct values in
        # 200 rows would classify as an id, leaving the math stage
        # with nothing numeric - engine logic working as designed).
        src = tmp_path / "e2e.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["record_id", "segment", "spend"])
            for i in range(200):
                w.writerow([f"C-{i:05d}", ("a", "b", "c")[i % 3],
                            round(50.0 + (i % 25) * 4.0, 2)])
        pq = tmp_path / "e2e.parquet"
        duckdb.execute(
            f"COPY (SELECT * FROM read_csv('{src}')) TO '{pq}' "
            f"(FORMAT parquet)"
        )
        findings = json.loads(tool_profile(str(pq), None))["findings"]
        plan = approve_plan(make_plan(
            "universal descriptive audit: distribution shape outliers "
            "entropy temporal structure", str(pq), findings, PLAYBOOKS,
        ), "Saif")
        out = tmp_path / "pkg"
        final = run(plan, load_playbook(UNIVERSAL),
                    [{"column": "record_id", "rule": "unique"}],
                    out, approvals=APPROVALS)
        manifest = json.loads(
            (final / "manifest.json").read_text(encoding="utf-8")
        )
        # the step-18 fingerprint covers a Parquet source unchanged
        assert manifest["source_fingerprint"]["sha256"]
        assert manifest["source_fingerprint"]["bytes"] == pq.stat().st_size
        math_findings = json.loads(
            (final / "findings" / "math.json").read_text(encoding="utf-8")
        )["findings"]
        assert math_findings["numeric"]["spend"]["mean"] > 0


# ── hunt regressions ─────────────────────────────────────────────────────────


class TestHuntRegressions:
    def test_h1_timezone_aware_parquet_discloses_utc_reading(
        self, tmp_path: Path
    ) -> None:
        """Parquet preserves TIMESTAMP WITH TIME ZONE (an instant).
        The reader renders it in UTC, so an IST-midnight event falls on
        the previous UTC day. The instant is right and the engine does
        not silently re-zone anyone's data - it DISCLOSES the reading
        inside the hashed findings."""
        pq = tmp_path / "tz.parquet"
        duckdb.execute(
            f"COPY (SELECT i AS id, (TIMESTAMPTZ "
            f"'2026-01-01 00:00:00+05:30' + INTERVAL (i % 60) DAY) AS ts "
            f"FROM range(200) t(i)) TO '{pq}' (FORMAT parquet)"
        )
        f = run_math(str(pq), "temporal", [], [], ["ts"])
        assert "source_timezone_note" in f
        assert "UTC" in f["source_timezone_note"]
        assert "ts" in f["source_timezone_note"]
        # and a naive-timestamp source carries no such note
        plain = tmp_path / "plain.parquet"
        duckdb.execute(
            f"COPY (SELECT i AS id, (TIMESTAMP '2026-01-01 00:00:00' + "
            f"INTERVAL (i % 60) DAY) AS ts FROM range(200) t(i)) "
            f"TO '{plain}' (FORMAT parquet)"
        )
        assert "source_timezone_note" not in run_math(
            str(plain), "temporal", [], [], ["ts"]
        )

    def test_h2_untypeable_sqlite_column_is_refused(
        self, tmp_path: Path
    ) -> None:
        """SQLite's dynamic typing lets one column mix ints and text;
        the reader surfaces it as raw bytes. Analyzing untyped bytes
        would be fabrication - so it is a refusal naming the column."""
        db = tmp_path / "mixed.db"
        sc = sqlite3.connect(db)
        sc.execute("CREATE TABLE t (id INTEGER, v)")
        sc.executemany(
            "INSERT INTO t VALUES (?,?)",
            [(i, i if i % 2 else "txt") for i in range(30)],
        )
        sc.commit()
        sc.close()
        with pytest.raises(SourceError) as exc:
            load_dataframe(str(db))
        msg = str(exc.value)
        assert "v" in msg and "CAST" in msg
        # a cleanly typed sqlite column still loads
        clean = tmp_path / "clean.db"
        sc = sqlite3.connect(clean)
        sc.execute("CREATE TABLE t (id INTEGER, v TEXT)")
        sc.executemany("INSERT INTO t VALUES (?,?)",
                       [(i, "a") for i in range(30)])
        sc.commit()
        sc.close()
        assert len(load_dataframe(str(clean))) == 30

    def test_h3_empty_parquet_reaches_the_stage_as_feasibility(
        self, tmp_path: Path
    ) -> None:
        """A zero-row Parquet loads (it is a valid file); the stage's
        existing feasibility rules - not the reader - decide it cannot
        be analyzed, with a written reason."""
        pq = tmp_path / "empty.parquet"
        duckdb.execute(
            f"COPY (SELECT 1 AS a WHERE false) TO '{pq}' (FORMAT parquet)"
        )
        assert len(load_dataframe(str(pq))) == 0
        with pytest.raises(MathError, match=r"feasibility|drift"):
            run_math(str(pq), "all", ["a"], [], [])

    def test_h4_directory_source_dies_in_our_voice(
        self, tmp_path: Path
    ) -> None:
        """Parquet 'datasets' are often directories; v1 reads single
        files, and a directory is a clean SourceError, not a traceback."""
        (tmp_path / "dataset.parquet").mkdir()
        with pytest.raises(SourceError, match="valid Parquet"):
            load_dataframe(str(tmp_path / "dataset.parquet"))
