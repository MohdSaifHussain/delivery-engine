"""Step 23 tests - the deterministic across-runs trend report.

Planted-answer discipline: plant a lineage of runs with known,
improving findings and assert the trend shows exactly those per-run
values, in order, with the two properties that keep it honest:

  1. INJECTED NUMBERS ONLY - every number shown traces to some run's
     findings; nothing is computed.
  2. NO CROSS-RUN DELTA - the report never authors an improvement
     figure (a difference, a percentage-better). It draws the values;
     the reader reads the movement.

Plus determinism (same runs -> byte-identical HTML), not-scored
handling across runs, the single-run case, and the package-area
integration with clean errors.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from delivery_engine.trend import (
    TrendError,
    build_trend_html,
    trend_from_area,
)


def _run(number: int, completeness: float, validity: float,
         exceptions: int, rules: int = 5) -> dict[str, Any]:
    return {
        "run": f"run_{number:03d}",
        "number": number,
        "dama": {
            "accuracy": None, "completeness": completeness,
            "consistency": 1.0, "timeliness": None,
            "uniqueness": 1.0, "validity": validity,
        },
        "total_exceptions": exceptions,
        "rules_evaluated": rules,
        "profile_sha": f"prof{number:03d}abcdef",
        "validate_sha": f"val{number:03d}deadbeef99",
    }


def _journey() -> list[dict[str, Any]]:
    """messy -> better -> clean."""
    return [
        _run(1, 0.90, 0.88, 1312),
        _run(2, 0.97, 0.94, 312),
        _run(3, 1.0, 1.0, 0),
    ]


class TestPlantedValues:
    def test_each_run_exception_count_is_shown(self) -> None:
        html = build_trend_html(_journey(), "claims", "19 July 2026")
        assert "1,312 exceptions" in html
        assert "312 exceptions" in html
        assert "0 exceptions" in html

    def test_each_run_completeness_is_shown(self) -> None:
        html = build_trend_html(_journey(), "claims", "19 July 2026")
        assert "90.0%" in html
        assert "97.0%" in html
        assert "100.0%" in html

    def test_runs_labelled_in_order(self) -> None:
        html = build_trend_html(_journey(), "claims", "")
        i1 = html.find("run_001")
        i2 = html.find("run_002")
        i3 = html.find("run_003")
        assert -1 < i1 < i2 < i3

    def test_run_count_in_header(self) -> None:
        html = build_trend_html(_journey(), "claims", "")
        assert "3 run(s) sealed" in html

    def test_validate_digest_per_run_in_table(self) -> None:
        html = build_trend_html(_journey(), "claims", "")
        # first 12 chars of each digest appear (traceability)
        assert "val001deadb" in html


class TestNoComputedDelta:
    """The constitutional line: the report draws per-run values and
    never authors a cross-run improvement figure."""

    def test_no_exception_difference_is_shown(self) -> None:
        # 1312 - 312 = 1000 ; 312 - 0 = 312 (312 is a real value, ok);
        # 1000 must NOT appear as a computed delta
        html = build_trend_html(_journey(), "claims", "")
        assert "1,000" not in html
        assert "1000" not in html

    def test_no_completeness_delta_is_shown(self) -> None:
        # 100.0 - 90.0 = 10.0 ; a 10.0% "improvement" must not appear
        html = build_trend_html(_journey(), "claims", "")
        assert ">10.0%<" not in html
        assert "10.0% " not in html

    def test_every_shown_number_traces_to_a_run(self) -> None:
        runs = _journey()
        html = build_trend_html(runs, "claims", "19 July 2026")
        legit: set[str] = set()
        for r in runs:
            legit.add(str(r["total_exceptions"]))
            legit.add(f"{r['total_exceptions']:,}")
            legit.add(str(r["rules_evaluated"]))
            for v in r["dama"].values():
                if v is not None:
                    legit.add(f"{v * 100:.1f}")
            legit.update(re.findall(r"\d+", r["validate_sha"]))
            legit.update(re.findall(r"\d+", r["run"]))
        legit_bare = {t.replace(",", "") for t in legit}
        # fixed chart scaffolding + metadata that are not run data:
        # axis gridlines 0/50/100, the generation date, svg geometry
        allowed_non_data = {
            "0", "50", "100", "0.0", "50.0", "100.0",     # gridlines
            "2026", "19",                                  # date
            "640", "194", "150", "820", "56", "32", "80",  # geometry
            "1.9", "0.01", "3", "12", "2", "1",            # css/rem
        }
        text = re.sub(r"<style.*?</style>", "", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("SHA-256", " ")
        # match whole numbers only (a trailing dot is not part of the
        # number), so CSS fragments like -0.01em cannot leak in
        for tok in re.findall(r"\d[\d,]*(?:\.\d+)?%?", text):
            bare = tok.rstrip("%").replace(",", "")
            if bare in legit_bare or tok.rstrip("%") in legit:
                continue
            if bare in allowed_non_data or tok.rstrip("%") in \
                    allowed_non_data:
                continue
            raise AssertionError(
                f"number {tok!r} is neither a run value nor allowed "
                f"scaffolding - possible computed figure"
            )


class TestDeterminism:
    def test_byte_identical_on_repeat(self) -> None:
        a = build_trend_html(_journey(), "claims", "19 July 2026")
        b = build_trend_html(_journey(), "claims", "19 July 2026")
        assert a == b

    def test_only_the_date_varies(self) -> None:
        base = build_trend_html(_journey(), "claims", "01 January 2026")
        later = build_trend_html(_journey(), "claims", "31 December 2026")
        assert base != later
        assert base.replace("01 January 2026", "D") == \
            later.replace("31 December 2026", "D")


class TestEdgeCases:
    def test_single_run_renders_a_valid_document(self) -> None:
        html = build_trend_html([_run(1, 0.9, 0.88, 1312)], "claims", "")
        assert "1 run(s) sealed" in html
        assert "</html>" in html
        # the single-run lede sets expectations honestly
        assert "will take shape as further runs" in html

    def test_not_scored_dimension_is_not_drawn_as_zero(self) -> None:
        # accuracy/timeliness are None in every run; they must not
        # appear as 0.0% points
        html = build_trend_html(_journey(), "claims", "")
        # the completeness/validity/etc lines exist; accuracy does not
        assert "completeness" in html
        assert "accuracy" not in html.split("<footer>")[0].replace(
            "accuracy", "", 0)  # accuracy never plotted as a line label

    def test_empty_runs_is_a_clean_error(self) -> None:
        with pytest.raises(TrendError, match="No completed runs"):
            build_trend_html([], "claims", "")


class TestTrendFromArea:
    def _seal(self, area: Path, number: int, completeness: float,
              exceptions: int) -> None:
        rd = area / f"run_{number:03d}" / "final" / "findings"
        rd.mkdir(parents=True)
        (rd / "dq_profile.json").write_text(json.dumps({
            "findings": {"dama_scores": {
                "accuracy": None, "completeness": completeness,
                "consistency": 1.0, "timeliness": None,
                "uniqueness": 1.0, "validity": completeness,
            }, "columns": []},
            "sha256": f"prof{number}", "stage": "dq_profile",
        }), encoding="utf-8")
        (rd / "dq_validate.json").write_text(json.dumps({
            "findings": {"results": [], "rules_evaluated": 5,
                         "total_exceptions": exceptions},
            "sha256": f"val{number}abcdef012345", "stage": "dq_validate",
        }), encoding="utf-8")

    def test_reads_lineage_and_writes_trend_html(
        self, tmp_path: Path
    ) -> None:
        area = tmp_path / "claims"
        self._seal(area, 1, 0.90, 1312)
        self._seal(area, 2, 1.0, 0)
        out = trend_from_area(str(area))
        assert out.name == "trend.html"
        html = out.read_text(encoding="utf-8")
        assert "2 run(s) sealed" in html
        assert "1,312 exceptions" in html

    def test_no_runs_is_a_clean_error(self, tmp_path: Path) -> None:
        empty = tmp_path / "claims"
        empty.mkdir()
        with pytest.raises(TrendError, match="No run_NNN folders"):
            trend_from_area(str(empty))

    def test_incomplete_run_is_skipped_not_guessed(
        self, tmp_path: Path
    ) -> None:
        area = tmp_path / "claims"
        self._seal(area, 1, 0.90, 1312)
        # run_002 exists but has no findings (stopped run)
        (area / "run_002").mkdir()
        out = trend_from_area(str(area))
        html = out.read_text(encoding="utf-8")
        # only the one complete run is charted
        assert "1 run(s) sealed" in html

    def test_non_directory_is_a_clean_error(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(TrendError, match="Not a directory"):
            trend_from_area(str(tmp_path / "nope"))


class TestHuntRegressions:
    def test_h1_worsening_data_is_shown_honestly(self) -> None:
        """If exceptions rise across runs, the report shows it and never
        claims improvement. The trend is a mirror, not a cheerleader."""
        worse = [_run(1, 1.0, 1.0, 0), _run(2, 0.80, 0.80, 500)]
        html = build_trend_html(worse, "claims", "")
        assert "improvement" not in html.lower()
        assert "500 exceptions" in html

    def test_h2_all_dimensions_unscored_does_not_crash(self) -> None:
        none_run = {
            "run": "run_001", "number": 1,
            "dama": dict.fromkeys(("accuracy", "completeness", "consistency", "timeliness", "uniqueness", "validity")),
            "total_exceptions": 5, "rules_evaluated": 2,
            "profile_sha": "p", "validate_sha": "vabc123456789",
        }
        html = build_trend_html([none_run], "claims", "")
        assert "</html>" in html

    def test_h3_dataset_name_is_escaped(self) -> None:
        html = build_trend_html(
            [_run(1, 1.0, 1.0, 0)], "<script>alert(1)</script>", "")
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_h4_extreme_scale_stays_within_bounds(self) -> None:
        big = [_run(1, 0.5, 0.5, 9999999), _run(2, 1.0, 1.0, 0)]
        html = build_trend_html(big, "claims", "")
        widths = [int(w) for w in re.findall(r'width="(\d+)"', html)]
        assert all(0 <= w <= 640 for w in widths)
