"""Step 18 tests - the Analyst-Error Guardrails.

Six controls, each traceable to the research that motivated it, each
tested with planted answers verified by independent implementations:

- G1 leakage sentinel (model stage): motivated by a production run
  where a post-hoc label produced AUC 1.0.
- G2 pseudoreplication disclosure (stats stage): Forstmeier,
  Wagenmakers & Parker 2017 - non-independence invalidates p-values.
- G3 minimum detectable effect (stats stage): Cohen 1988 closed forms;
  low power inflates both false negatives and false positives.
- G4 analyst-bias checklist (handoff): Panko/EuSpRIG - structured
  checklists catch what self-checking does not.
- G5 source fingerprint (manifest): the 2026 lineage control - "the
  data changed" becomes provable.
- G6 Limitations & assumptions section (narrative): the 2026
  anti-hallucination control - uncertainty communicated, never
  fabricated; absent caveats mean nothing was recorded, and every
  present caveat is read from hashed findings.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine import (
    approve_plan,
    load_playbook,
    make_plan,
    run,
)
from delivery_engine.audit import file_sha256
from delivery_engine.model import LEAKAGE_THRESHOLD, train_baseline
from delivery_engine.stats import MDE_POWER, run_inference

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
SEGMENT = PLAYBOOKS / "segment_comparison.toml"

RULES = [{"column": "customer_id", "rule": "unique"}]
APPROVALS: dict[str, Any] = {"plan_approval": "Saif"}

Z_975 = 1.959963984540054   # standard normal 97.5th pct (published)
Z_80 = 0.8416212335729143   # standard normal 80th pct (published)


def _csv(path: Path, header: list[str], rows: list[list[Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


# ── G1: the leakage sentinel ─────────────────────────────────────────────────


class TestLeakageSentinel:
    def _leaky_csv(self, tmp_path: Path) -> Path:
        rows = []
        for i in range(240):
            f = 1 if i % 4 == 0 else 0
            rows.append([
                f,
                "fraudish" if f else "none",     # answer key in disguise
                i % 7,                            # clean numeric
                f * 100.0,                        # numeric answer key
                ("a", "b", "c")[i % 3],           # clean categorical
            ])
        return _csv(tmp_path / "leak.csv",
                    ["flag", "leaky_cat", "clean_num", "leaky_num",
                     "clean_cat"], rows)

    def test_planted_leaks_flagged_clean_features_not(
        self, tmp_path: Path
    ) -> None:
        f = train_baseline(str(self._leaky_csv(tmp_path)), "flag",
                           ["clean_num", "leaky_num"],
                           ["leaky_cat", "clean_cat"])
        flagged = {w["feature"]: w for w in f["leakage_warnings"]}
        assert set(flagged) == {"leaky_cat", "leaky_num"}
        assert flagged["leaky_cat"]["measure"] == "cramers_v"
        assert flagged["leaky_cat"]["association"] == pytest.approx(
            1.0, abs=1e-6
        )
        assert flagged["leaky_num"]["measure"] == "abs_point_biserial"
        assert f["leakage_threshold"] == LEAKAGE_THRESHOLD

    def test_warning_never_gates_metrics_still_produced(
        self, tmp_path: Path
    ) -> None:
        f = train_baseline(str(self._leaky_csv(tmp_path)), "flag",
                           ["leaky_num"], ["leaky_cat"])
        assert f["leakage_warnings"]           # flagged
        assert "metrics" in f                  # and the run completed
        assert f["metrics"]["roc_auc"] >= 0.99  # the AUC-1.0 pattern

    def test_clean_dataset_has_no_warnings(self, tmp_path: Path) -> None:
        rows = [[1 if i % 3 == 0 else 0, i % 11, ("x", "y")[i % 2]]
                for i in range(240)]
        src = _csv(tmp_path / "clean.csv", ["flag", "num", "cat"], rows)
        f = train_baseline(str(src), "flag", ["num"], ["cat"])
        assert f["leakage_warnings"] == []


# ── G3: minimum detectable effect ────────────────────────────────────────────


class TestMde:
    def _segment_csv(self, tmp_path: Path, rows: int = 200) -> Path:
        out = []
        for i in range(rows):
            seg = "a" if i % 2 == 0 else "b"
            threshold = 8 if seg == "a" else 1
            conv = "yes" if i % 10 < threshold else "no"
            out.append([f"C-{i:05d}", conv, seg, 100.0 + i])
        return _csv(tmp_path / "seg.csv",
                    ["customer_id", "converted", "segment", "spend"], out)

    def test_fisher_mde_matches_cohen_closed_form(
        self, tmp_path: Path
    ) -> None:
        src = self._segment_csv(tmp_path)
        f = run_inference(str(src), "chi2_independence", "converted",
                          ["segment"], [], 0.05)
        t = next(x for x in f["tests"] if "mde" in x)
        n1, n2 = 100, 100  # segment margins by construction
        expected = (Z_975 + Z_80) * math.sqrt(1 / n1 + 1 / n2)
        assert t["mde"]["cohens_h"] == pytest.approx(expected, abs=1e-6)
        assert t["mde"]["power"] == MDE_POWER
        assert "rules out effects above" in t["mde"]["note"]

    def test_mwu_mde_matches_normal_approximation(
        self, tmp_path: Path
    ) -> None:
        src = self._segment_csv(tmp_path)
        f = run_inference(str(src), "mann_whitney", "converted", [],
                          ["spend"], 0.05)
        t = f["tests"][0]
        # Step 20: the single reader types this yes/no column BOOLEAN
        # (DuckDB's sniffer), matching what the profile gate always
        # reported - so the group keys are 'False'/'True'. The MDE
        # formula under test is unchanged; only the labels are.
        n1 = t["groups"]["False"]
        n2 = t["groups"]["True"]
        expected = (Z_975 + Z_80) * math.sqrt(
            (n1 + n2 + 1) / (3.0 * n1 * n2)
        )
        assert t["mde"]["rank_biserial"] == pytest.approx(
            expected, abs=1e-6
        )

    def test_stricter_alpha_raises_the_mde(self, tmp_path: Path) -> None:
        src = self._segment_csv(tmp_path)
        f05 = run_inference(str(src), "chi2_independence", "converted",
                           ["segment"], [], 0.05)
        f01 = run_inference(str(src), "chi2_independence", "converted",
                           ["segment"], [], 0.01)
        h05 = next(x for x in f05["tests"] if "mde" in x)["mde"]["cohens_h"]
        h01 = next(x for x in f01["tests"] if "mde" in x)["mde"]["cohens_h"]
        assert h01 > h05  # harder to detect at stricter alpha


# ── G2 + G5 + G6: end to end through the segment archetype ───────────────────


def _grouped_segment_csv(path: Path, rows: int = 200) -> Path:
    """Planted pseudoreplication: 200 rows from only 40 households
    (avg 5 rows per entity - exactly the disclosed scan thresholds)."""
    out = []
    for i in range(rows):
        seg = "a" if i % 2 == 0 else "b"
        threshold = 8 if seg == "a" else 1
        conv = "yes" if i % 10 < threshold else "no"
        out.append([f"C-{i:05d}", f"H-{i % 40:03d}", conv, seg,
                    100.0 + i])
    return _csv(path, ["customer_id", "household", "converted",
                       "segment", "spend"], out)


def _approved_plan(src: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "segment comparison with statistical significance for the "
        "growth team", str(src), envelope["findings"], PLAYBOOKS,
    )
    return approve_plan(plan, "Saif")


class TestEndToEnd:
    def _run(self, tmp_path: Path) -> Path:
        src = _grouped_segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        out = tmp_path / "pkg"
        run(plan, load_playbook(SEGMENT), RULES, out, approvals=APPROVALS)
        return out

    def test_g2_pseudoreplication_disclosed(self, tmp_path: Path) -> None:
        out = self._run(tmp_path)
        s = json.loads((out / "findings" / "stats.json")
                       .read_text("utf-8"))["findings"]
        indep = s["independence"]
        cols = [g["column"] for g in indep["grouping_candidates"]]
        assert "household" in cols
        hh = next(g for g in indep["grouping_candidates"]
                  if g["column"] == "household")
        assert hh["distinct"] == 40
        assert hh["avg_rows_per_value"] == 5.0
        assert "Forstmeier" in indep["warning"]

    def test_g2_no_grouping_no_warning(self, tmp_path: Path) -> None:
        rows = []
        for i in range(200):
            seg = "a" if i % 2 == 0 else "b"
            threshold = 8 if seg == "a" else 1
            conv = "yes" if i % 10 < threshold else "no"
            rows.append([f"C-{i:05d}", conv, seg, 100.0 + i])
        src = _csv(tmp_path / "flat.csv",
                   ["customer_id", "converted", "segment", "spend"], rows)
        plan = _approved_plan(src)
        out = tmp_path / "pkg"
        run(plan, load_playbook(SEGMENT), RULES, out, approvals=APPROVALS)
        s = json.loads((out / "findings" / "stats.json")
                       .read_text("utf-8"))["findings"]
        assert s["independence"]["warning"] is None
        assert s["independence"]["grouping_candidates"] == []

    def test_g5_manifest_fingerprints_the_source(
        self, tmp_path: Path
    ) -> None:
        src = _grouped_segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        out = tmp_path / "pkg"
        run(plan, load_playbook(SEGMENT), RULES, out, approvals=APPROVALS)
        manifest = json.loads((out / "manifest.json").read_text("utf-8"))
        fp = manifest["source_fingerprint"]
        assert fp["sha256"] == file_sha256(src)
        assert fp["bytes"] == src.stat().st_size
        audit = (out / "audit_log.jsonl").read_text(encoding="utf-8")
        assert "source_fingerprint" in audit

    def test_g5_different_source_different_fingerprint(
        self, tmp_path: Path
    ) -> None:
        s1 = _grouped_segment_csv(tmp_path / "a.csv")
        s2 = _grouped_segment_csv(tmp_path / "b.csv", rows=204)
        m1 = tmp_path / "p1"
        m2 = tmp_path / "p2"
        run(_approved_plan(s1), load_playbook(SEGMENT), RULES, m1,
            approvals=APPROVALS)
        run(_approved_plan(s2), load_playbook(SEGMENT), RULES, m2,
            approvals=APPROVALS)
        f1 = json.loads((m1 / "manifest.json").read_text("utf-8"))
        f2 = json.loads((m2 / "manifest.json").read_text("utf-8"))
        assert (f1["source_fingerprint"]["sha256"]
                != f2["source_fingerprint"]["sha256"])

    def test_g6_limitations_section_reads_from_findings(
        self, tmp_path: Path
    ) -> None:
        out = self._run(tmp_path)
        report = (out / "narrative_report.md").read_text(encoding="utf-8")
        assert "## Limitations & assumptions" in report
        # independence caveat present because household was planted
        assert "cluster-robust" in report
        assert "household" in report
        # MDE caveat present because two-group tests ran
        assert "minimum" in report and "detectable" in report
        # provenance sentence: caveats are read, never inferred
        assert "read from the hashed findings" in report

    def test_g6_never_fabricates_absent_caveats(
        self, tmp_path: Path
    ) -> None:
        """A run with no grouping column must NOT carry the independence
        caveat - absent caveats stay absent."""
        rows = []
        for i in range(200):
            seg = "a" if i % 2 == 0 else "b"
            threshold = 8 if seg == "a" else 1
            conv = "yes" if i % 10 < threshold else "no"
            rows.append([f"C-{i:05d}", conv, seg, 100.0 + i])
        src = _csv(tmp_path / "flat.csv",
                   ["customer_id", "converted", "segment", "spend"], rows)
        plan = _approved_plan(src)
        out = tmp_path / "pkg"
        run(plan, load_playbook(SEGMENT), RULES, out, approvals=APPROVALS)
        report = (out / "narrative_report.md").read_text(encoding="utf-8")
        assert "cluster-robust" not in report

    def test_g4_handoff_carries_the_bias_checklist(
        self, tmp_path: Path
    ) -> None:
        out = self._run(tmp_path)
        handoff = json.loads(
            (out / "handoff_manifest.json").read_text(encoding="utf-8")
        )
        mgr = " ".join(
            c["check"]
            for c in handoff["team_handoff"]["manager"]["checks"]
        )
        assert "survivorship" in mgr.lower()
        assert "denominator" in mgr.lower()
        assert "granularity" in mgr.lower()

    def test_reperformable_same_hash_across_runs(
        self, tmp_path: Path
    ) -> None:
        src = _grouped_segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        pb = load_playbook(SEGMENT)
        run(plan, pb, RULES, tmp_path / "p1", approvals=APPROVALS)
        run(plan, pb, RULES, tmp_path / "p2", approvals=APPROVALS)
        d1 = json.loads((tmp_path / "p1" / "findings" / "stats.json")
                        .read_text("utf-8"))["sha256"]
        d2 = json.loads((tmp_path / "p2" / "findings" / "stats.json")
                        .read_text("utf-8"))["sha256"]
        assert d1 == d2


# ── hunt regressions ─────────────────────────────────────────────────────────


class TestHuntRegressions:
    def test_h5_vanished_source_is_an_audited_stop(
        self, tmp_path: Path
    ) -> None:
        from delivery_engine import ExecutionStopped

        src = _grouped_segment_csv(tmp_path / "seg.csv")
        plan = _approved_plan(src)
        src.unlink()  # the file disappears after Human Gate 1
        out = tmp_path / "pkg"
        with pytest.raises(ExecutionStopped, match="does not exist"):
            run(plan, load_playbook(SEGMENT), RULES, out,
                approvals=APPROVALS)
        audit = (out / "audit_log.jsonl").read_text(encoding="utf-8")
        assert "source_fingerprint" in audit and "fail" in audit
