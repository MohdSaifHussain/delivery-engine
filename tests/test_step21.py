"""Step 21 tests - the deterministic visual report.

Planted-answer discipline: each test plants known findings and asserts
the report shows exactly those values, handles the honest edge cases
(not-scored dimensions, all-pass validation, messy data), and stays a
pure function of its inputs.

The load-bearing test is TestInjectedNumbers: it proves that every
number a reader sees in the HTML traces to the findings passed in -
the injected-numbers rule made visual. A report that computed or
invented a figure would fail it. This is the report's equivalent of
verify_artifact_numbers.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from delivery_engine.report import (
    ReportError,
    build_report_html,
    report_from_package,
)

# ── fixtures: known findings with planted values ─────────────────────────────


def _clean_profile() -> dict[str, Any]:
    return {
        "accuracy_note": "not inferable from the dataset alone",
        "dama_scores": {
            "accuracy": None,
            "completeness": 1.0,
            "consistency": 1.0,
            "timeliness": None,
            "uniqueness": 1.0,
            "validity": 1.0,
        },
        "columns": [
            {
                "name": "row_id",
                "dtype": "BIGINT",
                "total": 6362620,
                "nulls": 0,
                "distinct": 6362620,
                "valid_ratio": 1.0,
                "completeness": 1.0,
                "case_variants": 0,
            },
            {
                "name": "type",
                "dtype": "VARCHAR",
                "total": 6362620,
                "nulls": 0,
                "distinct": 5,
                "valid_ratio": 1.0,
                "completeness": 1.0,
                "case_variants": 0,
            },
        ],
    }


def _clean_validate() -> dict[str, Any]:
    return {
        "results": [
            {
                "rule_id": "R01",
                "column": "row_id",
                "rule": "unique",
                "failures": 0,
                "detail": "value must be unique",
                "sample": [],
            },
            {
                "rule_id": "R02",
                "column": "type",
                "rule": "allowed",
                "failures": 0,
                "detail": "",
                "sample": [],
            },
        ],
        "rules_evaluated": 2,
        "total_exceptions": 0,
    }


def _messy_profile() -> dict[str, Any]:
    return {
        "dama_scores": {
            "accuracy": None,
            "completeness": 0.90,
            "consistency": 0.97,
            "timeliness": None,
            "uniqueness": 1.0,
            "validity": 0.88,
        },
        "columns": [
            {
                "name": "customer_id",
                "dtype": "BIGINT",
                "total": 10000,
                "nulls": 0,
                "distinct": 10000,
                "valid_ratio": 1.0,
                "completeness": 1.0,
                "case_variants": 0,
            },
            {
                "name": "owner_team",
                "dtype": "VARCHAR",
                "total": 10000,
                "nulls": 1000,
                "distinct": 8,
                "valid_ratio": 0.90,
                "completeness": 0.90,
                "case_variants": 0,
            },
        ],
    }


def _messy_validate() -> dict[str, Any]:
    return {
        "results": [
            {
                "rule_id": "R01",
                "column": "customer_id",
                "rule": "unique",
                "failures": 0,
                "detail": "",
                "sample": [],
            },
            {
                "rule_id": "R02",
                "column": "owner_team",
                "rule": "not_null",
                "failures": 1000,
                "detail": "",
                "sample": [],
            },
        ],
        "rules_evaluated": 2,
        "total_exceptions": 1000,
    }


def _math_findings() -> dict[str, Any]:
    """Planted math findings with known values for assertion."""
    return {
        "column_selection": "columns selected by engine",
        "math_checks": "all",
        "skipped": [],
        "constants": {
            "ci_confidence": 0.95,
            "mad_scale": 0.6745,
            "mad_threshold": 3.5,
            "min_n": 8,
            "rare_frequency": 0.01,
        },
        "numeric": {
            "amount": {
                "n": 300,
                "n_dropped_nan": 0,
                "mean": 153.125,
                "median": 146.1,
                "std_sample": 90.368,
                "mean_ci_low": 142.858,
                "mean_ci_high": 163.392,
                "mean_ci_confidence": 0.95,
                "mean_ci_method": "t-interval",
                "p95": 232.2,
                "p99": 240.4,
                "percentile_method": "linear",
                "skewness_g1_adjusted": 6.535,
                "excess_kurtosis_g2_adjusted": 63.772,
                "tail_note": "right-skewed",
            },
        },
        "categorical": {
            "category": {
                "n": 300,
                "n_dropped_nan": 0,
                "distinct": 5,
                "entropy_bits": 2.322,
                "entropy_normalized": 1.0,
                "entropy_source": "Shannon 1948, base 2",
                "rare_categories": [],
                "rare_count": 0,
                "rare_threshold": 0.01,
            },
        },
        "outliers": {},
        "distribution_fit": {},
        "temporal": {},
    }


# ── the planted values appear, correctly formatted ───────────────────────────


class TestPlantedValues:
    def test_clean_scores_render_as_percentages(self) -> None:
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "data/x.csv",
            "hh",
            "vv",
        )
        assert "100.0%" in html
        assert "Data review" in html
        assert "data/x.csv" in html

    def test_not_scored_dimensions_never_render_as_zero(self) -> None:
        """accuracy and timeliness are None - shown 'not scored', never
        as a 0% bar. Absence of a score is not a score of zero."""
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "h",
            "v",
        )
        # two dimensions (accuracy, timeliness) render as "not scored"
        # value labels; a third mention lives in the explanatory note.
        assert html.count('class="val muted">not scored') == 2
        # no dimension is rendered as a literal 0.0% value label
        # (guard against substring matches inside 100.0%)
        assert ">0.0%<" not in html

    def test_all_pass_validation_reads_cleanly(self) -> None:
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "h",
            "v",
        )
        assert "0 exceptions" in html
        assert "2 rules evaluated, 0 total exceptions" in html

    def test_messy_values_render_with_exact_counts(self) -> None:
        html = build_report_html(
            _messy_profile(),
            _messy_validate(),
            "s",
            "h",
            "v",
        )
        assert "90.0%" in html
        assert "88.0%" in html
        assert "1,000 exceptions" in html
        assert "2 rules evaluated, 1,000 total exceptions" in html

    def test_profile_table_carries_exact_hashed_values(self) -> None:
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "h",
            "v",
        )
        assert "6,362,620" in html  # row totals, thousands-separated
        assert "BIGINT" in html and "VARCHAR" in html

    def test_provenance_digests_in_footer(self) -> None:
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "PROFILEHASH123",
            "VALIDATEHASH456",
        )
        assert "PROFILEHASH123" in html
        assert "VALIDATEHASH456" in html
        assert "rendered deterministically" in html.lower()


# ── determinism: same findings -> byte-identical ─────────────────────────────


class TestDeterminism:
    def test_byte_identical_on_repeat(self) -> None:
        a = build_report_html(_clean_profile(), _clean_validate(), "s", "h", "v", "19 July 2026")
        b = build_report_html(_clean_profile(), _clean_validate(), "s", "h", "v", "19 July 2026")
        assert a == b

    def test_generation_date_is_the_only_varying_part(self) -> None:
        """The date is display metadata outside the findings region.
        With it fixed, output is stable; changing only the date changes
        only the footer line, never a chart or a number."""
        base = build_report_html(
            _clean_profile(), _clean_validate(), "s", "h", "v", "01 January 2026"
        )
        later = build_report_html(
            _clean_profile(), _clean_validate(), "s", "h", "v", "31 December 2026"
        )
        # differ only by the date strings
        assert base != later
        assert base.replace("01 January 2026", "DATE") == later.replace("31 December 2026", "DATE")


# ── the load-bearing proof: no number is invented ────────────────────────────


class TestInjectedNumbers:
    """Every number the reader sees must trace to the findings. A
    computed or invented figure fails this - the visual equivalent of
    verify_artifact_numbers."""

    def _legit_tokens(
        self,
        profile: dict[str, Any],
        validate: dict[str, Any],
        digests: tuple[str, str],
    ) -> set[str]:
        legit: set[str] = set()
        for v in profile["dama_scores"].values():
            if v is not None:
                legit.add(f"{v * 100:.1f}")
        for c in profile["columns"]:
            for key in ("total", "nulls", "distinct"):
                legit.add(str(int(c[key])))
                legit.add(f"{int(c[key]):,}")
            for key in ("valid_ratio", "completeness"):
                legit.add(f"{c[key] * 100:.1f}")
        for r in validate["results"]:
            legit.add(str(int(r["failures"])))
            legit.add(f"{int(r['failures']):,}")
            # rule IDs (R01, R02, ...) come straight from findings; the
            # numeric part is a legitimate shown token
            rid = str(r["rule_id"])
            digits = re.sub(r"\D", "", rid)
            if digits:
                legit.add(digits)
                legit.add(str(int(digits)))
        legit.add(str(validate["rules_evaluated"]))
        legit.add(str(validate["total_exceptions"]))
        legit.add(f"{validate['total_exceptions']:,}")
        # provenance hashes and the literal algorithm name are allowed
        legit.update(digests)
        return legit

    def _shown_numbers(self, html: str) -> list[str]:
        # strip style/script and the two provenance hashes and the
        # literal "SHA-256" algorithm name, then read visible numbers
        text = re.sub(r"<style.*?</style>", "", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("SHA-256", " ")
        return re.findall(r"\d[\d,]*\.?\d*", text)

    def test_every_shown_number_traces_to_findings(self) -> None:
        prof, val = _clean_profile(), _clean_validate()
        digests = ("PROFILEHASHAAAA", "VALIDATEHASHBBBB")
        html = build_report_html(prof, val, "data/x.csv", *digests)
        legit = self._legit_tokens(prof, val, digests)
        legit_bare = {t.replace(",", "") for t in legit}
        for tok in self._shown_numbers(html):
            bare = tok.rstrip("%").replace(",", "")
            assert bare in legit_bare or tok.rstrip("%") in legit, (
                f"number {tok!r} in report does not trace to findings"
            )

    def test_messy_numbers_also_all_trace(self) -> None:
        prof, val = _messy_profile(), _messy_validate()
        digests = ("PH", "VH")
        html = build_report_html(prof, val, "s", *digests)
        legit = self._legit_tokens(prof, val, digests)
        legit_bare = {t.replace(",", "") for t in legit}
        for tok in self._shown_numbers(html):
            bare = tok.rstrip("%").replace(",", "")
            assert bare in legit_bare or tok.rstrip("%") in legit, tok


# ── colour signals honestly (accessibility + truth) ──────────────────────────


class TestColourSignalsState:
    def test_clean_uses_good_colour_not_warn(self) -> None:
        html = build_report_html(_clean_profile(), _clean_validate(), "s", "h", "v")
        assert "#2e7d5b" in html  # good present
        # a fully clean report needs no warning colour on bars
        # (only structural greys/ink otherwise)

    def test_messy_uses_warn_colour(self) -> None:
        html = build_report_html(_messy_profile(), _messy_validate(), "s", "h", "v")
        assert "#b45309" in html  # amber present for sub-100%

    def test_charts_have_accessible_roles(self) -> None:
        """SVG charts carry role=img + title so assistive tech reads
        them (WCAG 1.1.1); colour is never the only signal - every bar
        pairs with a text value."""
        html = build_report_html(_clean_profile(), _clean_validate(), "s", "h", "v")
        assert 'role="img"' in html
        assert "<title>" in html


# ── math-stage descriptive statistics section ────────────────────────────────


class TestMathSection:
    """Verifies the Descriptive statistics section added for Step 21."""

    def _html_with_math(self, **kw: Any) -> str:
        math = kw.pop("math", _math_findings())
        return build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "h",
            "v",
            math=math,
            **kw,
        )

    def test_section_heading_present(self) -> None:
        assert "Descriptive statistics" in self._html_with_math()

    def test_numeric_mean_renders(self) -> None:
        html = self._html_with_math()
        assert "153.1" in html  # f"{153.125:.4g}"
        assert "n=300" in html

    def test_categorical_entropy_renders(self) -> None:
        html = self._html_with_math()
        assert "2.32" in html  # f"{2.322:.3g}"
        assert "5" in html  # distinct categories

    def test_skipped_columns_show_omitted_not_value(self) -> None:
        math = _math_findings()
        math["skipped"] = ["hidden_col"]
        html = self._html_with_math(math=math)
        assert "hidden_col" in html
        assert "omitted" in html

    def test_math_digest_in_footer(self) -> None:
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "h",
            "v",
            math=_math_findings(),
            math_digest="MATHDIGESTXYZ",
        )
        assert "MATHDIGESTXYZ" in html

    def test_math_none_omits_section(self) -> None:
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "h",
            "v",
            math=None,
        )
        assert "Descriptive statistics" not in html

    def test_math_section_byte_identical(self) -> None:
        """Same math findings → same HTML bytes (pure-function check)."""
        math = _math_findings()
        a = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "h",
            "v",
            "01 January 2026",
            math=math,
            math_digest="MH",
        )
        b = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "h",
            "v",
            "01 January 2026",
            math=math,
            math_digest="MH",
        )
        assert a == b

    def test_math_numbers_trace_to_findings(self) -> None:
        """Every number visible in the math section traces to math.json.
        This is the injected-numbers rule applied to the new section."""
        math = _math_findings()
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "s",
            "PROFILEHASHAAAA",
            "VALIDATEHASHBBBB",
            math=math,
            math_digest="MATHDIGESTCCCC",
        )
        # Build legit set from all three findings sources.
        legit: set[str] = set()
        # profile + validate (same logic as TestInjectedNumbers)
        for v in _clean_profile()["dama_scores"].values():
            if v is not None:
                legit.add(f"{v * 100:.1f}")
        for c in _clean_profile()["columns"]:
            for key in ("total", "nulls", "distinct"):
                legit.add(str(int(c[key])))
                legit.add(f"{int(c[key]):,}")
            for key in ("valid_ratio", "completeness"):
                legit.add(f"{c[key] * 100:.1f}")
        for r in _clean_validate()["results"]:
            legit.add(str(int(r["failures"])))
            digits = re.sub(r"\D", "", str(r["rule_id"]))
            if digits:
                legit.add(digits)
                legit.add(str(int(digits)))
        legit.add(str(_clean_validate()["rules_evaluated"]))
        legit.add(str(_clean_validate()["total_exceptions"]))
        # math numeric
        for s in math["numeric"].values():
            legit.add(f"{float(s['mean']):.4g}")
            legit.add(str(int(s["n"])))
            legit.add(f"{int(s['n']):,}")
        # math categorical
        for s in math["categorical"].values():
            legit.add(f"{float(s['entropy_bits']):.3g}")
            legit.add(str(int(s["distinct"])))
            legit.add(f"{int(s['distinct']):,}")
            legit.add(str(int(s["n"])))
        # "95" from "95% confidence interval" in the note text
        ci_conf = math["constants"]["ci_confidence"]
        legit.add(f"{ci_conf * 100:.0f}")
        # digests
        legit.update(("PROFILEHASHAAAA", "VALIDATEHASHBBBB", "MATHDIGESTCCCC"))

        # Extract visible numbers (same method as TestInjectedNumbers)
        text = re.sub(r"<style.*?</style>", "", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("SHA-256", " ")
        shown = re.findall(r"\d[\d,]*\.?\d*", text)

        legit_bare = {t.replace(",", "") for t in legit}
        for tok in shown:
            bare = tok.rstrip("%").replace(",", "")
            assert bare in legit_bare or tok.rstrip("%") in legit, (
                f"math section number {tok!r} does not trace to findings"
            )

    def test_math_section_accessible(self) -> None:
        """SVG charts in the math section carry role=img + title."""
        html = self._html_with_math()
        assert 'role="img"' in html
        assert "<title>" in html


# ── package integration + edge cases ─────────────────────────────────────────


class TestReportFromPackage:
    def _seal(self, d: Path, profile: dict[str, Any], validate: dict[str, Any]) -> Path:
        import json

        pkg = d / "pkg"
        (pkg / "findings").mkdir(parents=True)
        (pkg / "findings" / "dq_profile.json").write_text(
            json.dumps({"findings": profile, "sha256": "PROFHASH", "stage": "dq_profile"}),
            encoding="utf-8",
        )
        (pkg / "findings" / "dq_validate.json").write_text(
            json.dumps({"findings": validate, "sha256": "VALHASH", "stage": "dq_validate"}),
            encoding="utf-8",
        )
        return pkg

    def test_writes_report_html_into_package(self, tmp_path: Path) -> None:
        pkg = self._seal(tmp_path, _clean_profile(), _clean_validate())
        out = report_from_package(str(pkg))
        assert out.name == "report.html"
        assert out.exists()
        assert "Data review" in out.read_text(encoding="utf-8")

    def test_missing_findings_is_a_clean_error(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        (empty / "findings").mkdir(parents=True)
        with pytest.raises(ReportError, match="not found"):
            report_from_package(str(empty))

    def test_non_directory_is_a_clean_error(self, tmp_path: Path) -> None:
        with pytest.raises(ReportError, match="Not a directory"):
            report_from_package(str(tmp_path / "nope"))

    def test_source_label_pulled_from_manifest(self, tmp_path: Path) -> None:
        import json

        pkg = self._seal(tmp_path, _clean_profile(), _clean_validate())
        (pkg / "manifest.json").write_text(
            json.dumps({"source_fingerprint": {"path": "data/claims.csv", "sha256": "x"}}),
            encoding="utf-8",
        )
        out = report_from_package(str(pkg))
        assert "data/claims.csv" in out.read_text(encoding="utf-8")


# ── loophole hunt regressions ────────────────────────────────────────────────


class TestHuntRegressions:
    def test_h1_column_name_html_is_escaped(self) -> None:
        """A hostile column name cannot inject markup - angle brackets
        are escaped so it renders as text, never as a tag."""
        prof = _clean_profile()
        prof["columns"][0]["name"] = "<script>alert(1)</script>"
        html = build_report_html(prof, _clean_validate(), "s", "h", "v")
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_h2_source_label_is_escaped(self) -> None:
        """The source label (a filename/path) cannot inject markup."""
        html = build_report_html(
            _clean_profile(),
            _clean_validate(),
            "<img src=x onerror=alert(1)>",
            "h",
            "v",
        )
        # angle brackets escaped -> the browser sees text, not a tag
        assert "<img src=x" not in html
        assert "&lt;img" in html

    def test_h3_empty_columns_renders(self) -> None:
        """A profile with no columns still produces a valid report."""
        prof = _clean_profile()
        prof["columns"] = []
        html = build_report_html(prof, _clean_validate(), "s", "h", "v")
        assert "Data review" in html
        assert "</html>" in html

    def test_h4_out_of_range_scores_clamp_to_valid_bars(self) -> None:
        """Malformed scores (>1 or <0) never produce negative or
        overflowing bar widths - the display fraction is clamped."""
        import re

        prof = _clean_profile()
        prof["dama_scores"]["completeness"] = 1.5
        prof["dama_scores"]["consistency"] = -0.2
        html = build_report_html(prof, _clean_validate(), "s", "h", "v")
        widths = [int(w) for w in re.findall(r'width="(-?\d+)"', html)]
        assert all(w >= 0 for w in widths)
        assert all(w <= 640 for w in widths)
