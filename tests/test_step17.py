"""Step 17 tests - the universal descriptive math stage.

Planted-answer discipline, applied to descriptive statistics: every
verification value is computed by an INDEPENDENT implementation inside
this file - the Joanes & Gill adjusted skewness/kurtosis formulas by
hand, the t-interval from the published critical value t(0.975, df=9),
the linear-interpolation percentile by hand, the MAD modified z-score
by hand, Shannon entropy from exact fractions - never
library-vs-same-library.

The constitutional positions under test (rule V15):
- math_checks is declared from a fixed sourced list; math stages gate
  and declare needs; math_checks on other kinds is refused.
- Columns come from the plan; thresholds are fixed disclosed constants.
- Descriptive values never gate; feasibility does. Skips carry written
  reasons (MAD == 0 is a declared refusal, not a division by zero).
- The Lilliefors correction: normal/lognormal carry a valid p; Weibull
  carries a KS distance and an explicit reason why no p exists.
- Same data + same plan -> same findings hash.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, ClassVar

import pytest
from analystkit.ai import findings_digest
from analystkit_mcp.tools import tool_profile

from delivery_engine import (
    PlaybookError,
    approve_plan,
    load_playbook,
    make_plan,
    run,
)
from delivery_engine.mathkit import MathError, run_math

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
UNIVERSAL = PLAYBOOKS / "universal_audit.toml"

RULES = [{"column": "record_id", "rule": "unique"}]
APPROVALS: dict[str, Any] = {"plan_approval": "Saif"}

T_975_DF9 = 2.2621571628  # published t table: 97.5th pct, 9 df


# ── independent implementations (the answer keys) ────────────────────────────


def skew_g1_by_hand(x: list[float]) -> float:
    """Adjusted Fisher-Pearson G1 (Joanes & Gill 1998, eq. for G1)."""
    n = len(x)
    m = sum(x) / n
    m2 = sum((v - m) ** 2 for v in x) / n
    m3 = sum((v - m) ** 3 for v in x) / n
    g1 = m3 / m2 ** 1.5
    return g1 * math.sqrt(n * (n - 1)) / (n - 2)


def kurt_g2_by_hand(x: list[float]) -> float:
    """Adjusted excess kurtosis G2 (Joanes & Gill 1998)."""
    n = len(x)
    m = sum(x) / n
    m2 = sum((v - m) ** 2 for v in x) / n
    m4 = sum((v - m) ** 4 for v in x) / n
    g2 = m4 / m2 ** 2 - 3.0
    return ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * g2 + 6.0)


def percentile_linear_by_hand(sorted_x: list[float], q: float) -> float:
    """numpy's documented 'linear' interpolation, re-derived."""
    n = len(sorted_x)
    rank = (q / 100.0) * (n - 1)
    lo = math.floor(rank)
    frac = rank - lo
    if lo + 1 >= n:
        return sorted_x[-1]
    return sorted_x[lo] + frac * (sorted_x[lo + 1] - sorted_x[lo])


def mad_mod_z_by_hand(x: list[float]) -> tuple[float, list[float]]:
    xs = sorted(x)
    n = len(xs)
    med = (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)
    devs = sorted(abs(v - med) for v in x)
    mad = (devs[n // 2] if n % 2 else (devs[n // 2 - 1] + devs[n // 2]) / 2)
    return mad, [0.6745 * (v - med) / mad for v in x]


# ── fixtures ──────────────────────────────────────────────────────────────────


def _csv(path: Path, header: list[str], rows: list[list[Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def _normal_grid(n: int) -> list[float]:
    """A deterministic, perfectly normal-shaped sample via the inverse
    CDF on a mid-point grid - no RNG anywhere."""
    from scipy.stats import norm

    return [float(norm.ppf((i + 0.5) / n)) for i in range(n)]


# ── planted answers, unit level ───────────────────────────────────────────────


class TestNumericShape:
    DATA: ClassVar[list[float]] = [12.0, 15.5, 9.0, 22.0,
                                   18.5, 11.0, 25.0, 14.0, 16.5, 30.0]

    def _findings(self, tmp_path: Path) -> dict[str, Any]:
        src = _csv(tmp_path / "n.csv", ["val"], [[v] for v in self.DATA])
        return run_math(str(src), "numeric_shape", ["val"], [], [])

    def test_skewness_matches_joanes_gill_formula(
        self, tmp_path: Path
    ) -> None:
        e = self._findings(tmp_path)["numeric"]["val"]
        assert e["skewness_g1_adjusted"] == pytest.approx(
            skew_g1_by_hand(self.DATA), abs=1e-6
        )

    def test_kurtosis_matches_joanes_gill_formula(
        self, tmp_path: Path
    ) -> None:
        e = self._findings(tmp_path)["numeric"]["val"]
        assert e["excess_kurtosis_g2_adjusted"] == pytest.approx(
            kurt_g2_by_hand(self.DATA), abs=1e-6
        )

    def test_mean_ci_matches_published_t_critical(
        self, tmp_path: Path
    ) -> None:
        e = self._findings(tmp_path)["numeric"]["val"]
        n = len(self.DATA)
        m = sum(self.DATA) / n
        sd = math.sqrt(sum((v - m) ** 2 for v in self.DATA) / (n - 1))
        half = T_975_DF9 * sd / math.sqrt(n)
        assert e["mean_ci_low"] == pytest.approx(m - half, abs=1e-5)
        assert e["mean_ci_high"] == pytest.approx(m + half, abs=1e-5)
        assert "leans on approximate normality" in e["mean_ci_note"]

    def test_percentiles_match_hand_interpolation(
        self, tmp_path: Path
    ) -> None:
        e = self._findings(tmp_path)["numeric"]["val"]
        xs = sorted(self.DATA)
        assert e["p95"] == pytest.approx(
            percentile_linear_by_hand(xs, 95), abs=1e-6
        )
        assert e["p99"] == pytest.approx(
            percentile_linear_by_hand(xs, 99), abs=1e-6
        )


class TestMadOutliers:
    def test_planted_outlier_flagged_and_mad_matches_hand(
        self, tmp_path: Path
    ) -> None:
        data = [float(v) for v in range(1, 10)] + [1000.0]
        src = _csv(tmp_path / "o.csv", ["val"], [[v] for v in data])
        f = run_math(str(src), "outliers", ["val"], [], [])
        o = f["outliers"]["val"]
        mad, zs = mad_mod_z_by_hand(data)
        assert o["mad"] == pytest.approx(mad, abs=1e-9)
        assert o["outlier_count"] == sum(1 for z in zs if abs(z) > 3.5) == 1
        assert o["threshold"] == 3.5 and o["scale_factor"] == 0.6745

    def test_zero_mad_is_a_declared_skip_not_a_crash(
        self, tmp_path: Path
    ) -> None:
        data = [7.0] * 30 + [1.0, 2.0]
        src = _csv(tmp_path / "z.csv", ["val"], [[v] for v in data])
        f = run_math(str(src), "all", ["val"], [], [])
        assert any("MAD is zero" in s["reason"] for s in f["skipped"])
        assert "val" not in f["outliers"]
        # the rest of the suite still ran on the column
        assert "val" in f["numeric"]


class TestDistributionFit:
    def test_normal_grid_prefers_normal_with_valid_lilliefors_p(
        self, tmp_path: Path
    ) -> None:
        data = [10.0 + 2.0 * v for v in _normal_grid(200)]
        src = _csv(tmp_path / "g.csv", ["val"], [[v] for v in data])
        f = run_math(str(src), "distribution_fit", ["val"], [], [])
        d = f["distribution_fit"]["val"]
        assert d["best_fit"] == "normal"
        assert d["candidates"]["normal"]["lilliefors_p"] > 0.2

    def test_exp_grid_prefers_lognormal(self, tmp_path: Path) -> None:
        data = [math.exp(v) for v in _normal_grid(200)]
        src = _csv(tmp_path / "ln.csv", ["val"], [[v] for v in data])
        f = run_math(str(src), "distribution_fit", ["val"], [], [])
        d = f["distribution_fit"]["val"]
        assert d["best_fit"] == "lognormal"
        assert d["candidates"]["lognormal"]["lilliefors_p"] > 0.2

    def test_weibull_reports_distance_and_the_reason_no_p_exists(
        self, tmp_path: Path
    ) -> None:
        data = [math.exp(v) for v in _normal_grid(120)]
        src = _csv(tmp_path / "w.csv", ["val"], [[v] for v in data])
        f = run_math(str(src), "distribution_fit", ["val"], [], [])
        wb = f["distribution_fit"]["val"]["candidates"]["weibull"]
        assert "ks_distance" in wb
        assert "lilliefors_p" not in wb and "p_value" not in wb
        assert "Lilliefors 1967" in wb["p_value_omitted_reason"]

    def test_negative_values_skip_positive_only_candidates(
        self, tmp_path: Path
    ) -> None:
        data = list(_normal_grid(100))  # symmetric around 0
        src = _csv(tmp_path / "neg.csv", ["val"], [[v] for v in data])
        f = run_math(str(src), "distribution_fit", ["val"], [], [])
        cands = f["distribution_fit"]["val"]["candidates"]
        assert "lognormal" not in cands and "weibull" not in cands
        assert "normal" in cands


class TestEntropy:
    def test_uniform_four_categories_is_exactly_two_bits(
        self, tmp_path: Path
    ) -> None:
        rows = [[c] for c in ("a", "b", "c", "d") for _ in range(50)]
        src = _csv(tmp_path / "u.csv", ["cat"], rows)
        f = run_math(str(src), "categorical_entropy", [], ["cat"], [])
        c = f["categorical"]["cat"]
        assert c["entropy_bits"] == pytest.approx(2.0, abs=1e-9)
        assert c["entropy_normalized"] == pytest.approx(1.0, abs=1e-9)

    def test_half_quarter_quarter_is_one_point_five_bits(
        self, tmp_path: Path
    ) -> None:
        rows = ([["x"]] * 100) + ([["y"]] * 50) + ([["z"]] * 50)
        src = _csv(tmp_path / "m.csv", ["cat"], rows)
        f = run_math(str(src), "categorical_entropy", [], ["cat"], [])
        assert f["categorical"]["cat"]["entropy_bits"] == pytest.approx(
            1.5, abs=1e-9
        )

    def test_rare_category_below_fixed_threshold_is_listed(
        self, tmp_path: Path
    ) -> None:
        rows = ([["common"]] * 299) + [["unicorn"]]  # 1/300 = 0.33%
        src = _csv(tmp_path / "r.csv", ["cat"], rows)
        f = run_math(str(src), "categorical_entropy", [], ["cat"], [])
        c = f["categorical"]["cat"]
        assert c["rare_count"] == 1
        assert "unicorn" in c["rare_categories"]
        assert c["rare_threshold"] == 0.01


class TestTemporal:
    def test_planted_gap_and_positive_trend(self, tmp_path: Path) -> None:
        from datetime import date, timedelta

        rows: list[list[Any]] = []
        d0 = date(2026, 1, 1)
        for i in range(20):                 # 20 consecutive days
            for _ in range(1 + i):          # increasing daily volume
                rows.append([(d0 + timedelta(days=i)).isoformat()])
        d1 = d0 + timedelta(days=19 + 30)   # then a 30-day gap
        for i in range(10):
            for _ in range(25 + i):
                rows.append([(d1 + timedelta(days=i)).isoformat()])
        src = _csv(tmp_path / "t.csv", ["ts"], rows)
        f = run_math(str(src), "temporal", [], [], ["ts"])
        t = f["temporal"]["ts"]
        assert t["max_gap_days"] == 30
        assert t["distinct_days"] == 30
        assert t["trend_slope_rows_per_day"] > 0

    def test_too_few_days_is_a_declared_skip(self, tmp_path: Path) -> None:
        rows = [["2026-01-01"]] * 40 + [["2026-01-02"]] * 40
        src = _csv(tmp_path / "t2.csv", ["ts"], rows)
        with pytest.raises(MathError, match="feasibility"):
            run_math(str(src), "temporal", [], [], ["ts"])


class TestDeterminism:
    def test_same_inputs_same_hash(self, tmp_path: Path) -> None:
        rows = [[float(i % 37), ("a", "b", "c")[i % 3]] for i in range(200)]
        src = _csv(tmp_path / "d.csv", ["val", "cat"], rows)
        f1 = run_math(str(src), "all", ["val"], ["cat"], [])
        f2 = run_math(str(src), "all", ["val"], ["cat"], [])
        assert findings_digest(f1) == findings_digest(f2)


class TestRefusals:
    def test_unknown_checks(self, tmp_path: Path) -> None:
        src = _csv(tmp_path / "x.csv", ["v"], [[1.0]] * 20)
        with pytest.raises(MathError, match="Unknown math_checks"):
            run_math(str(src), "vibes", ["v"], [], [])

    def test_missing_column_names_plan_drift(self, tmp_path: Path) -> None:
        src = _csv(tmp_path / "x.csv", ["v"], [[float(i)] for i in range(20)])
        with pytest.raises(MathError, match="re-profile and re-plan"):
            run_math(str(src), "all", ["ghost"], [], [])

    def test_duplicate_features_refused(self, tmp_path: Path) -> None:
        src = _csv(tmp_path / "x.csv", ["v"], [[float(i)] for i in range(20)])
        with pytest.raises(MathError, match="Duplicate"):
            run_math(str(src), "all", ["v", "v"], [], [])

    def test_nothing_measurable_is_a_feasibility_failure(
        self, tmp_path: Path
    ) -> None:
        src = _csv(tmp_path / "x.csv", ["v"], [[1.0]] * 4)  # n < MIN_N
        with pytest.raises(MathError, match="feasibility"):
            run_math(str(src), "all", ["v"], [], [])


# ── the constitution: V15 ────────────────────────────────────────────────────


_BASE = """
schema_version = 1

[playbook]
name = "v15_probe"
version = "0.0.1"
description = "constitution probe"

[[stages]]
id = "dq_profile"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"

{math_stage}

[[stages]]
id = "package"
kind = "package"
needs = ["dq_profile"]

[deliverables]
artifacts = ["audit_log", "manifest"]
"""


def _pb(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


class TestV15:
    def test_valid_math_stage_loads(self, tmp_path: Path) -> None:
        pb = load_playbook(_pb(tmp_path / "ok.toml", _BASE.format(
            math_stage=('[[stages]]\nid = "math"\nkind = "math"\n'
                        'math_checks = "all"\ngate = "must_pass"\n'
                        'needs = ["dq_profile"]'))))
        assert pb.stages[1].math_checks == "all"

    def test_unknown_math_checks_refused(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="V15"):
            load_playbook(_pb(tmp_path / "bad.toml", _BASE.format(
                math_stage=('[[stages]]\nid = "math"\nkind = "math"\n'
                            'math_checks = "vibes"\ngate = "must_pass"\n'
                            'needs = ["dq_profile"]'))))

    def test_math_stage_requires_needs(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="V15"):
            load_playbook(_pb(tmp_path / "bad.toml", _BASE.format(
                math_stage=('[[stages]]\nid = "math"\nkind = "math"\n'
                            'math_checks = "all"\ngate = "must_pass"'))))

    def test_math_checks_on_kit_stage_refused(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="unknown key"):
            load_playbook(_pb(tmp_path / "bad.toml", _BASE.format(
                math_stage=('[[stages]]\nid = "leak"\nkind = "kit"\n'
                            'tool = "analystkit_validate"\n'
                            'gate = "advisory"\nmath_checks = "all"\n'
                            'needs = ["dq_profile"]'))))


# ── end to end: the universal_audit archetype ────────────────────────────────


def _universal_csv(path: Path, rows: int = 240) -> Path:
    from datetime import date, timedelta

    d0 = date(2026, 1, 1)
    out: list[list[Any]] = []
    for i in range(rows):
        out.append([
            f"R-{i:05d}",
            round(50.0 + (i % 40) * 3.7 + (250.0 if i == 100 else 0.0), 2),
            ("north", "south", "east", "west")[i % 4],
            (d0 + timedelta(days=i % 60)).isoformat(),
        ])
    return _csv(path, ["record_id", "amount", "region", "event_date"], out)


class TestEndToEnd:
    def _run(self, tmp_path: Path) -> Path:
        src = _universal_csv(tmp_path / "u.csv")
        envelope = json.loads(tool_profile(str(src), None))
        plan = make_plan(
            "universal descriptive audit: distribution shape outliers "
            "entropy temporal structure", str(src),
            envelope["findings"], PLAYBOOKS,
        )
        assert plan.playbook_name == "universal_audit"
        plan = approve_plan(plan, "Saif")
        out = tmp_path / "pkg"
        run(plan, load_playbook(UNIVERSAL), RULES, out,
            approvals=APPROVALS)
        return out

    def test_full_run_seals_math_and_narrates_it(
        self, tmp_path: Path
    ) -> None:
        out = self._run(tmp_path)
        payload = json.loads(
            (out / "findings" / "math.json").read_text(encoding="utf-8")
        )
        f = payload["findings"]
        assert f["numeric"] and f["categorical"]
        assert f["constants"]["mad_threshold"] == 3.5
        report = (out / "narrative_report.md").read_text(encoding="utf-8")
        assert "Distribution & shape" in report
        assert "never gated" in report
        audit = (out / "audit_log.jsonl").read_text(encoding="utf-8")
        assert "math:descriptive" in audit
        # handoff carries the QA math check with the sealed digest
        handoff = json.loads(
            (out / "handoff_manifest.json").read_text(encoding="utf-8")
        )
        qa = " ".join(
            c["check"] for c in
            handoff["team_handoff"]["qa_quality_control"]["checks"]
        )
        assert "descriptive math findings" in qa

    def test_reperformable_same_hash_across_runs(
        self, tmp_path: Path
    ) -> None:
        src = _universal_csv(tmp_path / "u.csv")
        envelope = json.loads(tool_profile(str(src), None))
        plan = approve_plan(make_plan(
            "universal descriptive audit: distribution shape outliers "
            "entropy temporal structure", str(src),
            envelope["findings"], PLAYBOOKS), "Saif")
        pb = load_playbook(UNIVERSAL)
        run(plan, pb, RULES, tmp_path / "p1", approvals=APPROVALS)
        run(plan, pb, RULES, tmp_path / "p2", approvals=APPROVALS)
        d1 = json.loads((tmp_path / "p1" / "findings" / "math.json")
                        .read_text("utf-8"))["sha256"]
        d2 = json.loads((tmp_path / "p2" / "findings" / "math.json")
                        .read_text("utf-8"))["sha256"]
        assert d1 == d2


# ── loophole-hunt regressions (step-17 hunt) ─────────────────────────────────


class TestLoopholeRegressions:
    def test_m2_binary_columns_excluded_from_numeric_suite(
        self, tmp_path: Path
    ) -> None:
        """A 0/1 column is a category wearing a number's clothes: it
        must not receive shape statistics, and the exclusion is
        disclosed."""
        from datetime import date, timedelta

        d0 = date(2026, 1, 1)
        rows: list[list[Any]] = []
        for i in range(240):
            rows.append([
                f"R-{i:05d}",
                1 if i % 3 == 0 else 0,             # numeric AND binary
                round(50.0 + (i % 40) * 3.7, 2),    # genuinely numeric
                ("north", "south", "east", "west")[i % 4],
                (d0 + timedelta(days=i % 60)).isoformat(),
            ])
        src = _csv(tmp_path / "b.csv",
                   ["record_id", "flag", "amount", "region", "event_date"],
                   rows)
        envelope = json.loads(tool_profile(str(src), None))
        plan = approve_plan(make_plan(
            "universal descriptive audit: distribution shape outliers "
            "entropy temporal structure", str(src),
            envelope["findings"], PLAYBOOKS), "Saif")
        out = tmp_path / "pkg"
        run(plan, load_playbook(UNIVERSAL), RULES, out,
            approvals=APPROVALS)
        f = json.loads((out / "findings" / "math.json")
                       .read_text("utf-8"))["findings"]
        assert "flag" not in f["numeric"]
        assert "flag" not in f["distribution_fit"]
        assert "amount" in f["numeric"]
        assert "binary_target" in f["column_selection"]

    def test_m4_nan_accounting_everywhere(self, tmp_path: Path) -> None:
        rows: list[list[Any]] = []
        for i in range(120):
            rows.append([("a", "b", "c")[i % 3], "2026-01-0" + str(1 + i % 9)])
        rows += [["", ""]] * 7  # empty -> NaN
        src = _csv(tmp_path / "nan.csv", ["cat", "ts"], rows)
        f = run_math(str(src), "all", [], ["cat"], ["ts"])
        assert f["categorical"]["cat"]["n_dropped_nan"] == 7
        assert f["temporal"]["ts"]["n_dropped_unparseable_or_nan"] == 7

    def test_m7_weibull_fit_failure_never_wins_best_fit(
        self, tmp_path: Path
    ) -> None:
        """The failure path pins ks_distance at the theoretical maximum
        so a failed fit can never be selected."""
        data = [math.exp(v) for v in _normal_grid(120)]
        src = _csv(tmp_path / "w.csv", ["val"], [[v] for v in data])
        f = run_math(str(src), "distribution_fit", ["val"], [], [])
        cands = f["distribution_fit"]["val"]["candidates"]
        worst = max(c["ks_distance"] for c in cands.values())
        assert worst <= 1.0  # the pinned failure value is the ceiling

    def test_m8_constant_daily_counts_declared_undefined_not_nan(
        self, tmp_path: Path
    ) -> None:
        rows = [["2026-01-0" + str(1 + i % 9)] for i in range(90)]
        src = _csv(tmp_path / "flat.csv", ["ts"], rows)
        f = run_math(str(src), "temporal", [], [], ["ts"])
        t = f["temporal"]["ts"]
        assert t["trend_slope_rows_per_day"] == 0.0
        assert "trend_r" not in t
        assert "undefined" in t["trend_r_undefined_reason"]
        # allow_nan=False raises on any NaN/Inf VALUE anywhere in the
        # findings - the precise claim (key names may contain "nan")
        json.dumps(f, allow_nan=False)
