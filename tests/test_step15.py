"""Step 15 tests - the deterministic statistical inference stage.

Planted-answer testing applied to statistics: every verification value
is computed by an INDEPENDENT implementation inside this file - the
Wilson interval by its published closed form with the standard-normal
constant, Fisher's exact p by brute-force hypergeometric enumeration
(math.comb), the Mann-Whitney exact p from the complete-separation
analytic case, and Benjamini-Hochberg by a hand-coded 1995 procedure.
The engine's scipy/statsmodels answers must match its own re-derivation
- never library-vs-same-library.

The constitutional positions under test:
- V14: stat_test is declared from a fixed sourced list; alpha is
  pre-registered in [stats] and range-checked; stats stages gate and
  declare needs.
- Significance NEVER gates; feasibility does (the step-10 principle).
- Skips are recorded with reasons, never silent; all-skipped fails.
- Same data + same plan + same alpha -> same findings hash.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import pytest
from analystkit.ai import findings_digest
from analystkit_mcp.tools import tool_profile

from delivery_engine import (
    ExecutionStopped,
    PlaybookError,
    approve_plan,
    load_playbook,
    make_plan,
    run,
)
from delivery_engine.stats import StatsError, run_inference

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
SEGMENT = PLAYBOOKS / "segment_comparison.toml"

RULES = [{"column": "customer_id", "rule": "unique"}]
APPROVALS: dict[str, Any] = {"plan_approval": "Saif"}

Z_975 = 1.959963984540054  # standard normal 97.5th percentile (published)


# ── independent implementations (the answer keys) ────────────────────────────


def wilson_by_formula(k: int, n: int) -> tuple[float, float]:
    """Wilson score interval, closed form (Wilson 1927 as given in the
    NIST/SEMATECH e-Handbook), z hard-coded - independent of statsmodels."""
    p = k / n
    z2 = Z_975 * Z_975
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (Z_975 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return center - half, center + half


def fisher_two_sided_by_enumeration(table: list[list[int]]) -> float:
    """Two-sided Fisher exact p by hypergeometric enumeration: the sum
    of probabilities of all tables (fixed margins) no more probable
    than the observed one - independent of scipy."""
    (a, b), (c, d) = table
    r1, r2, c1 = a + b, c + d, a + c
    n = r1 + r2

    def prob(x: int) -> float:
        return (math.comb(r1, x) * math.comb(r2, c1 - x)
                / math.comb(n, c1))

    p_obs = prob(a)
    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    return sum(prob(x) for x in range(lo, hi + 1)
               if prob(x) <= p_obs * (1 + 1e-12))


def bh_adjust_by_hand(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values per the 1995 procedure:
    sort ascending, p*m/rank, enforce monotonicity from the largest,
    cap at 1 - independent of statsmodels."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 1.0
    for pos in range(m - 1, -1, -1):
        i = order[pos]
        running = min(running, pvals[i] * m / (pos + 1))
        adj[i] = min(running, 1.0)
    return adj


def chi2_stat_by_formula(table: list[list[int]]) -> tuple[float, int]:
    """Pearson chi-square statistic and dof by the textbook formula
    sum((O-E)^2 / E) - independent of scipy."""
    rows = [sum(r) for r in table]
    cols = [sum(c) for c in zip(*table, strict=True)]
    n = sum(rows)
    stat = 0.0
    for i, r in enumerate(table):
        for j, obs in enumerate(r):
            exp = rows[i] * cols[j] / n
            stat += (obs - exp) ** 2 / exp
    return stat, (len(rows) - 1) * (len(cols) - 1)


# ── fixtures ──────────────────────────────────────────────────────────────────


def _segment_csv(path: Path, rows: int = 200) -> Path:
    """Planted signal: segment 'a' converts at 80%, segment 'b' at 10% -
    a difference no honest test can miss. 'spend' is completely ordered
    by conversion for a separable numeric signal; 'flatline' is constant
    (must be SKIPPED with a reason, never silently tested)."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["customer_id", "converted", "segment", "spend",
                    "flatline"])
        for i in range(rows):
            seg = "a" if i % 2 == 0 else "b"
            threshold = 8 if seg == "a" else 1
            conv = "yes" if i % 10 < threshold else "no"
            spend = (1000.0 + i) if conv == "yes" else (100.0 + i * 0.5)
            w.writerow([f"C-{i:05d}", conv, seg, f"{spend:.2f}", "7.0"])
    return path


def _approved_plan(src: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "segment comparison with statistical significance for the "
        "analytics team", str(src), envelope["findings"], PLAYBOOKS,
    )
    assert plan.playbook_name == "segment_comparison"
    return approve_plan(plan, "Saif")


# ── planted answers, unit level ───────────────────────────────────────────────


class TestWilsonInterval:
    def test_matches_closed_form(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        f = run_inference(str(src), "proportion_ci", "converted",
                          ["segment"], [], 0.05)
        overall = next(p for p in f["proportions"]
                       if p["scope"] == "overall")
        lo, hi = wilson_by_formula(overall["count_positive"], overall["n"])
        assert overall["ci_low"] == pytest.approx(lo, abs=1e-6)
        assert overall["ci_high"] == pytest.approx(hi, abs=1e-6)

    def test_positive_class_rule_is_disclosed(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        f = run_inference(str(src), "proportion_ci", "converted",
                          [], [], 0.05)
        assert f["positive_class"] == "yes"  # lexicographically last
        assert "disclosed deterministic rule" in f["positive_class_rule"]


class TestFisherExact:
    def test_2x2_matches_hypergeometric_enumeration(
        self, tmp_path: Path
    ) -> None:
        # A tiny handcrafted 2x2: 8/2 vs 1/5 successes.
        src = tmp_path / "tiny.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["grp", "hit"])
            rows = ([("g1", "yes")] * 8 + [("g1", "no")] * 2
                    + [("g2", "yes")] * 1 + [("g2", "no")] * 5)
            w.writerows(rows)
        f = run_inference(str(src), "chi2_independence", "hit",
                          ["grp"], [], 0.05)
        t = f["tests"][0]
        assert t["method"] == "fisher_exact_two_sided"
        # crosstab(grp, hit) -> [[no, yes] per group]; enumeration is
        # margin-invariant, so feed it the same observed table.
        expected_p = fisher_two_sided_by_enumeration([[2, 8], [5, 1]])
        assert t["p_value"] == pytest.approx(expected_p, abs=1e-6)
        assert "effect_size_cramers_v" in t  # ASA: effect size always

    def test_planted_segment_difference_is_significant(
        self, tmp_path: Path
    ) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        f = run_inference(str(src), "chi2_independence", "converted",
                          ["segment"], [], 0.05)
        t = next(x for x in f["tests"] if x["columns"][1] == "segment")
        assert t["significant_at_alpha"] is True
        assert t["p_adjusted_bh"] < 0.001


class TestChiSquareRxC:
    def test_statistic_matches_textbook_formula(self, tmp_path: Path) -> None:
        src = tmp_path / "rxc.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["tier", "flag"])
            counts = {("t1", "yes"): 30, ("t1", "no"): 10,
                      ("t2", "yes"): 20, ("t2", "no"): 20,
                      ("t3", "yes"): 10, ("t3", "no"): 30}
            for (tier, flag), n in counts.items():
                w.writerows([(tier, flag)] * n)
        f = run_inference(str(src), "chi2_independence", "flag",
                          ["tier"], [], 0.05)
        t = f["tests"][0]
        assert t["method"] == "pearson_chi2_no_correction"
        # crosstab(tier, flag): rows t1..t3, cols no/yes (sorted)
        stat, dof = chi2_stat_by_formula([[10, 30], [20, 20], [30, 10]])
        assert t["chi2"] == pytest.approx(stat, abs=1e-6)
        assert t["dof"] == dof
        assert t["cochran_rule_met"] is True

    def test_cochran_violation_is_flagged_not_hidden(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "sparse.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["tier", "flag"])
            counts = {("t1", "yes"): 2, ("t1", "no"): 1,
                      ("t2", "yes"): 1, ("t2", "no"): 2,
                      ("t3", "yes"): 2, ("t3", "no"): 2}
            for (tier, flag), n in counts.items():
                w.writerows([(tier, flag)] * n)
        f = run_inference(str(src), "chi2_independence", "flag",
                          ["tier"], [], 0.05)
        t = f["tests"][0]
        assert t["cochran_rule_met"] is False
        assert "validity_warning" in t


class TestMannWhitney:
    def test_complete_separation_exact_p(self, tmp_path: Path) -> None:
        """All of group 'no' below all of group 'yes', 6 vs 6, no ties:
        the exact two-sided p is analytically 2 / C(12, 6)."""
        src = tmp_path / "sep.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["hit", "score"])
            for i in range(6):
                w.writerow(["no", f"{1.0 + i:.1f}"])
            for i in range(6):
                w.writerow(["yes", f"{100.0 + i:.1f}"])
        f = run_inference(str(src), "mann_whitney", "hit", [],
                          ["score"], 0.05)
        t = f["tests"][0]
        assert t["p_value"] == round(2 / math.comb(12, 6), 6)  # 6dp contract
        # complete separation: rank-biserial correlation is +/- 1
        assert abs(t["effect_size_rank_biserial"]) == pytest.approx(
            1.0, abs=1e-9
        )

    def test_constant_column_is_skipped_with_reason(
        self, tmp_path: Path
    ) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        f = run_inference(str(src), "mann_whitney", "converted", [],
                          ["spend", "flatline"], 0.05)
        assert any("flatline" in s["what"] and "variation" in s["reason"]
                   for s in f["skipped"])


class TestBenjaminiHochberg:
    def test_adjusted_p_matches_hand_procedure(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        f = run_inference(str(src), "full_inference", "converted",
                          ["segment"], ["spend"], 0.05)
        raw = [t["p_value"] for t in f["tests"]]
        expected = bh_adjust_by_hand(raw)
        got = [t["p_adjusted_bh"] for t in f["tests"]]
        for g, e in zip(got, expected, strict=True):
            assert g == pytest.approx(e, abs=1e-6)
        assert f["bh_family_size"] == len(raw)

    def test_significance_flag_uses_adjusted_not_raw(
        self, tmp_path: Path
    ) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        f = run_inference(str(src), "full_inference", "converted",
                          ["segment"], ["spend"], 0.05)
        for t in f["tests"]:
            assert t["significant_at_alpha"] == (
                t["p_adjusted_bh"] <= 0.05
                or bool(t["p_adjusted_bh"] < 0.05)
            )


class TestDeterminism:
    def test_same_inputs_same_hash(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        f1 = run_inference(str(src), "full_inference", "converted",
                           ["segment"], ["spend", "flatline"], 0.05)
        f2 = run_inference(str(src), "full_inference", "converted",
                           ["segment"], ["spend", "flatline"], 0.05)
        assert findings_digest(f1) == findings_digest(f2)


# ── feasibility refusals, unit level ─────────────────────────────────────────


class TestRefusals:
    def test_unknown_stat_test(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        with pytest.raises(StatsError, match="Unknown stat_test"):
            run_inference(str(src), "students_t", "converted",
                          ["segment"], [], 0.05)

    def test_alpha_out_of_range(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        with pytest.raises(StatsError, match="alpha"):
            run_inference(str(src), "full_inference", "converted",
                          ["segment"], [], 1.5)

    def test_non_binary_target_refused(self, tmp_path: Path) -> None:
        src = tmp_path / "tri.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["status", "grp"])
            w.writerows([("a", "x"), ("b", "x"), ("c", "y")] * 40)
        with pytest.raises(StatsError, match="exactly 2"):
            run_inference(str(src), "chi2_independence", "status",
                          ["grp"], [], 0.05)

    def test_missing_column_names_plan_drift(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        with pytest.raises(StatsError, match="re-profile and re-plan"):
            run_inference(str(src), "full_inference", "converted",
                          ["ghost_column"], [], 0.05)

    def test_nothing_testable_is_a_feasibility_failure(
        self, tmp_path: Path
    ) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        with pytest.raises(StatsError, match="feasibility"):
            run_inference(str(src), "mann_whitney", "converted", [],
                          ["flatline"], 0.05)


# ── the constitution: V14 ────────────────────────────────────────────────────


def _write_playbook(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


_BASE = """
schema_version = 1

[playbook]
name = "v14_probe"
version = "0.0.1"
description = "constitution probe"

[[stages]]
id = "dq_profile"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"

{stats_stage}

[[stages]]
id = "package"
kind = "package"
needs = ["dq_profile"]

{stats_table}
[deliverables]
artifacts = ["audit_log", "manifest"]
"""


class TestV14:
    def test_valid_stats_stage_loads(self, tmp_path: Path) -> None:
        pb = load_playbook(_write_playbook(
            tmp_path / "ok.toml",
            _BASE.format(stats_stage=(
                '[[stages]]\nid = "stats"\nkind = "stats"\n'
                'stat_test = "full_inference"\ngate = "must_pass"\n'
                'needs = ["dq_profile"]'
            ), stats_table='[stats]\nalpha = 0.01\n'),
        ))
        assert pb.alpha == 0.01
        assert pb.stages[1].stat_test == "full_inference"

    def test_unknown_stat_test_refused(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="V14"):
            load_playbook(_write_playbook(
                tmp_path / "bad.toml",
                _BASE.format(stats_stage=(
                    '[[stages]]\nid = "stats"\nkind = "stats"\n'
                    'stat_test = "vibes"\ngate = "must_pass"\n'
                    'needs = ["dq_profile"]'
                ), stats_table=""),
            ))

    def test_stats_stage_requires_needs(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="V14"):
            load_playbook(_write_playbook(
                tmp_path / "bad.toml",
                _BASE.format(stats_stage=(
                    '[[stages]]\nid = "stats"\nkind = "stats"\n'
                    'stat_test = "full_inference"\ngate = "must_pass"'
                ), stats_table=""),
            ))

    def test_alpha_out_of_range_refused(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="V14"):
            load_playbook(_write_playbook(
                tmp_path / "bad.toml",
                _BASE.format(stats_stage=(
                    '[[stages]]\nid = "stats"\nkind = "stats"\n'
                    'stat_test = "full_inference"\ngate = "must_pass"\n'
                    'needs = ["dq_profile"]'
                ), stats_table='[stats]\nalpha = 1.5\n'),
            ))

    def test_alpha_bool_refused(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="V14"):
            load_playbook(_write_playbook(
                tmp_path / "bad.toml",
                _BASE.format(stats_stage=(
                    '[[stages]]\nid = "stats"\nkind = "stats"\n'
                    'stat_test = "full_inference"\ngate = "must_pass"\n'
                    'needs = ["dq_profile"]'
                ), stats_table='[stats]\nalpha = true\n'),
            ))

    def test_stats_table_without_stats_stage_refused(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(PlaybookError, match="V14"):
            load_playbook(_write_playbook(
                tmp_path / "bad.toml",
                _BASE.format(stats_stage="",
                             stats_table='[stats]\nalpha = 0.05\n'),
            ))

    def test_unknown_key_in_stats_table_refused(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(PlaybookError, match="unknown key"):
            load_playbook(_write_playbook(
                tmp_path / "bad.toml",
                _BASE.format(stats_stage=(
                    '[[stages]]\nid = "stats"\nkind = "stats"\n'
                    'stat_test = "full_inference"\ngate = "must_pass"\n'
                    'needs = ["dq_profile"]'
                ), stats_table='[stats]\nalpha = 0.05\nbeta = 0.2\n'),
            ))

    def test_stat_test_on_kit_stage_refused(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="unknown key"):
            load_playbook(_write_playbook(
                tmp_path / "bad.toml",
                _BASE.format(stats_stage=(
                    '[[stages]]\nid = "leak"\nkind = "kit"\n'
                    'tool = "analystkit_validate"\ngate = "advisory"\n'
                    'stat_test = "full_inference"\nneeds = ["dq_profile"]'
                ), stats_table=""),
            ))

    def test_default_alpha_without_stats_table(self, tmp_path: Path) -> None:
        pb = load_playbook(_write_playbook(
            tmp_path / "ok.toml",
            _BASE.format(stats_stage=(
                '[[stages]]\nid = "stats"\nkind = "stats"\n'
                'stat_test = "mann_whitney"\ngate = "must_pass"\n'
                'needs = ["dq_profile"]'
            ), stats_table=""),
        ))
        assert pb.alpha == 0.05


# ── the executor: end to end, and the never-gate-on-p principle ─────────────


class TestEndToEnd:
    def test_full_run_seals_inference_and_narrates_it(
        self, tmp_path: Path
    ) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        pb = load_playbook(SEGMENT)
        out = tmp_path / "pkg"
        run(plan, pb, RULES, out, approvals=APPROVALS)

        stats_json = out / "findings" / "stats.json"
        assert stats_json.exists()
        payload = json.loads(stats_json.read_text(encoding="utf-8"))
        assert payload["findings"]["alpha"] == 0.05
        assert payload["findings"]["tests"], "planted difference must test"

        report = (out / "narrative_report.md").read_text(encoding="utf-8")
        assert "Statistical evidence" in report
        assert "never gated" in report

        audit = (out / "audit_log.jsonl").read_text(encoding="utf-8")
        assert "stats:inference" in audit
        assert "significance never gates" in audit

    def test_significant_result_never_stops_a_must_pass_stage(
        self, tmp_path: Path
    ) -> None:
        """The anti-p-hacking position: the planted difference is
        overwhelmingly significant AND the must_pass stats stage passes.
        Only feasibility can stop it."""
        src = _segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        pb = load_playbook(SEGMENT)
        out = tmp_path / "pkg"
        run(plan, pb, RULES, out, approvals=APPROVALS)  # no ExecutionStopped
        payload = json.loads(
            (out / "findings" / "stats.json").read_text(encoding="utf-8")
        )
        assert any(t["significant_at_alpha"]
                   for t in payload["findings"]["tests"])

    def test_reperformable_same_hash_across_runs(
        self, tmp_path: Path
    ) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        pb = load_playbook(SEGMENT)
        run(plan, pb, RULES, tmp_path / "p1", approvals=APPROVALS)
        run(plan, pb, RULES, tmp_path / "p2", approvals=APPROVALS)
        d1 = json.loads((tmp_path / "p1" / "findings" / "stats.json")
                        .read_text(encoding="utf-8"))["sha256"]
        d2 = json.loads((tmp_path / "p2" / "findings" / "stats.json")
                        .read_text(encoding="utf-8"))["sha256"]
        assert d1 == d2

    def test_source_drift_after_approval_stops_the_run(
        self, tmp_path: Path
    ) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        pb = load_playbook(SEGMENT)
        # Swap the source AFTER Human Gate 1: drop the planted target.
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["customer_id", "note"])
            for i in range(150):
                w.writerow([f"C-{i:05d}", "x"])
        with pytest.raises(ExecutionStopped):
            run(plan, pb, RULES, tmp_path / "pkg", approvals=APPROVALS)


# ── loophole-hunt regressions (step 15 hunt, round 2) ────────────────────────


class TestLoopholeRegressions:
    def test_l4_target_as_feature_refused(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        with pytest.raises(StatsError, match="itself"):
            run_inference(str(src), "chi2_independence", "converted",
                          ["converted"], [], 0.05)

    def test_l4b_duplicate_features_refused(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        with pytest.raises(StatsError, match="Duplicate"):
            run_inference(str(src), "full_inference", "converted",
                          ["segment", "segment"], [], 0.05)

    def test_l10_wilson_bounds_stay_in_unit_interval(
        self, tmp_path: Path
    ) -> None:
        """k=0 and k~n extremes: the Wald interval would go negative or
        above 1 here; Wilson must not (Brown, Cai & DasGupta 2001)."""
        src = tmp_path / "extreme.csv"
        with src.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["converted", "segment"])
            for _ in range(100):
                w.writerow(["no", "a"])
            for i in range(100):
                w.writerow(["yes" if i < 1 else "no", "b"])
        f = run_inference(str(src), "proportion_ci", "converted",
                          ["segment"], [], 0.05)
        for p in f["proportions"]:
            assert 0.0 <= p["ci_low"] <= p["ci_high"] <= 1.0

    def test_l1_alpha_is_live_not_decorative(self, tmp_path: Path) -> None:
        src = _segment_csv(tmp_path / "seg.csv")
        f95 = run_inference(str(src), "proportion_ci", "converted",
                            [], [], 0.05)
        f99 = run_inference(str(src), "proportion_ci", "converted",
                            [], [], 0.01)
        w95 = (f95["proportions"][0]["ci_high"]
               - f95["proportions"][0]["ci_low"])
        w99 = (f99["proportions"][0]["ci_high"]
               - f99["proportions"][0]["ci_low"])
        assert w99 > w95  # 99% interval must be wider than 95%

    def test_l6_row_order_invariance(self, tmp_path: Path) -> None:
        import pandas as pd

        src = _segment_csv(tmp_path / "seg.csv")
        df = pd.read_csv(src)
        shuffled = tmp_path / "shuffled.csv"
        df.sample(frac=1, random_state=7).to_csv(shuffled, index=False)
        fa = run_inference(str(src), "full_inference", "converted",
                           ["segment"], ["spend"], 0.05)
        fb = run_inference(str(shuffled), "full_inference", "converted",
                           ["segment"], ["spend"], 0.05)
        assert findings_digest(fa) == findings_digest(fb)
