"""Step 19 tests - the playbook generator and the one project runner.

The constitutional positions under test:

Generator:
- Output is a DRAFT in playbooks/generated/ - outside the planner's
  non-recursive glob, invisible to the archetype lottery.
- The constitution is the compiler's type-checker: every generated
  file re-loads through load_playbook (V1-V15); an invalid draft is
  deleted, never left half-valid.
- Feasibility gates the menu: stats/model without a binary target is
  a refusal, not a playbook that fails later.
- Drafted rules are evidence-typed: numerics as numbers, booleans as
  booleans (the AnalystKit v2.0.2 contract, honored at the source).
- Deterministic: same profile + same answers -> byte-identical output.
- Drafts are never silently overwritten.

Runner:
- One runner, config-driven - no per-project script drift.
- A generated draft requires --playbook-approved-by: a pipeline never
  approves its own rules of engagement.
- Raising the exception-rate gate prints a loud override warning (the
  fraud-run lesson).
- End to end: generate -> approve -> run -> sealed package.
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine import make_plan
from delivery_engine.generator import (
    GENERATED_DIR_NAME,
    GeneratorError,
    compile_playbook,
)
from delivery_engine.playbook import load_playbook
from delivery_engine.runner import main as run_main

REPO_PLAYBOOKS = Path(__file__).parent.parent / "playbooks"


def _csvfile(path: Path, rows: int = 160) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["record_id", "converted", "tier", "amount",
                    "is_priority"])
        for i in range(rows):
            w.writerow([
                f"R-{i:05d}",
                "yes" if i % 3 == 0 else "no",
                ("gold", "silver", "bronze")[i % 3],
                round(50.0 + (i % 40) * 3.3, 2),
                "True" if i % 5 == 0 else "False",
            ])
    return path


def _no_target_csv(path: Path, rows: int = 160) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["record_id", "tier", "amount"])
        for i in range(rows):
            w.writerow([f"R-{i:05d}", ("a", "b", "c", "d")[i % 4],
                        50.0 + i])
    return path


def _profile(src: Path) -> dict[str, Any]:
    return json.loads(tool_profile(str(src), None))["findings"]


def _minimal_rules(tmp_path: Path) -> Path:
    p = tmp_path / "rules.json"
    p.write_text(json.dumps([{"column": "record_id", "rule": "unique"}]),
                 encoding="utf-8")
    return p


def _pbdir(tmp_path: Path) -> Path:
    d = tmp_path / "playbooks"
    d.mkdir(parents=True)
    shutil.copy(REPO_PLAYBOOKS / "segment_comparison.toml", d)
    shutil.copy(REPO_PLAYBOOKS / "universal_audit.toml", d)
    return d


class TestGenerator:
    def test_generates_a_constitution_valid_draft(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        gp = compile_playbook(
            str(src), "quarterly conversion audit", "conversion_audit",
            _pbdir(tmp_path), _profile(src), ["math", "stats"],
            alpha=0.01,
        )
        assert gp.playbook_path.parent.name == GENERATED_DIR_NAME
        pb = load_playbook(gp.playbook_path)  # the compile check, again
        assert pb.name == "conversion_audit"
        assert pb.alpha == 0.01
        kinds = [s.kind.value for s in pb.stages]
        assert "math" in kinds and "stats" in kinds
        text = gp.playbook_path.read_text(encoding="utf-8")
        assert "GENERATED DRAFT" in text
        assert gp.decisions["status"].startswith("DRAFT")

    def test_infeasible_stage_is_a_refusal_not_a_broken_file(
        self, tmp_path: Path
    ) -> None:
        src = _no_target_csv(tmp_path / "nt.csv")
        pbdir = _pbdir(tmp_path)
        with pytest.raises(GeneratorError, match="binary target"):
            compile_playbook(str(src), "goal", "bad_stats", pbdir,
                             _profile(src), ["stats"])
        assert not (pbdir / GENERATED_DIR_NAME / "bad_stats.toml").exists()

    def test_math_only_works_without_a_target(
        self, tmp_path: Path
    ) -> None:
        src = _no_target_csv(tmp_path / "nt.csv")
        gp = compile_playbook(str(src), "shape audit", "shape_audit",
                              _pbdir(tmp_path), _profile(src), ["math"])
        pb = load_playbook(gp.playbook_path)
        assert [s.kind.value for s in pb.stages].count("stats") == 0

    def test_bad_name_refused(self, tmp_path: Path) -> None:
        src = _csvfile(tmp_path / "d.csv")
        with pytest.raises(GeneratorError, match="lowercase"):
            compile_playbook(str(src), "g", "Bad Name!",
                             _pbdir(tmp_path), _profile(src), ["math"])

    def test_existing_draft_never_silently_overwritten(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        pbdir = _pbdir(tmp_path)
        prof = _profile(src)
        compile_playbook(str(src), "g", "dup_name", pbdir, prof, ["math"])
        with pytest.raises(GeneratorError, match="never "):
            compile_playbook(str(src), "g", "dup_name", pbdir, prof,
                             ["math"])

    def test_rules_are_evidence_typed(self, tmp_path: Path) -> None:
        """Numerics as numbers, booleans as booleans, strings as
        strings - the v2.0.2 per-dtype contract honored at drafting."""
        src = _csvfile(tmp_path / "d.csv")
        gp = compile_playbook(str(src), "g", "typed_rules",
                              _pbdir(tmp_path), _profile(src), ["math"])
        rules = json.loads(gp.rules_path.read_text(encoding="utf-8"))
        by_col = {}
        for r in rules:
            by_col.setdefault(r["column"], []).append(r)
        assert {r["rule"] for r in by_col["record_id"]} == {
            "unique", "not_null"
        }
        tier_vals = next(r for r in by_col["tier"]
                         if r["rule"] == "allowed")["values"]
        assert sorted(tier_vals) == ["bronze", "gold", "silver"]
        pri_vals = next(r for r in by_col["is_priority"]
                        if r["rule"] == "allowed")["values"]
        assert all(isinstance(v, bool) for v in pri_vals)
        # DuckDB's sniffer reads a yes/no column as BOOLEAN (the same
        # lesson as True/TRUE strings in the v2.0.1 tests) - so the
        # evidence-typed rule correctly carries booleans, which the
        # v2.0.2 per-dtype comparison then validates cleanly at run
        # time (proven end-to-end in TestRunner).
        conv_vals = next(r for r in by_col["converted"]
                         if r["rule"] == "allowed")["values"]
        assert all(isinstance(v, bool) for v in conv_vals)
        assert len(conv_vals) == 2

    def test_deterministic_byte_identical(self, tmp_path: Path) -> None:
        src = _csvfile(tmp_path / "d.csv")
        prof = _profile(src)
        g1 = compile_playbook(str(src), "g", "det_check",
                              _pbdir(tmp_path / "a"), prof,
                              ["math", "stats"])
        g2 = compile_playbook(str(src), "g", "det_check",
                              _pbdir(tmp_path / "b"), prof,
                              ["math", "stats"])
        assert (g1.playbook_path.read_bytes()
                == g2.playbook_path.read_bytes())
        assert g1.rules_path.read_bytes() == g2.rules_path.read_bytes()

    def test_generated_dir_invisible_to_goal_matching(
        self, tmp_path: Path
    ) -> None:
        """The planner's non-recursive glob means a generated draft can
        never win (or tie) the archetype lottery - even when the goal
        is its own description verbatim."""
        src = _csvfile(tmp_path / "d.csv")
        pbdir = _pbdir(tmp_path)
        prof = _profile(src)
        compile_playbook(str(src), "very specific generated goal words",
                         "lottery_probe", pbdir, prof, ["math"])
        from delivery_engine.planner import PlannerError

        try:
            plan = make_plan("very specific generated goal words",
                             str(src), prof, pbdir)
            assert plan.playbook_name != "lottery_probe"
        except PlannerError:
            pass  # no curated match at all - the probe still never won


class TestRunner:
    def _generate(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        src = _csvfile(tmp_path / "d.csv")
        pbdir = _pbdir(tmp_path)
        gp = compile_playbook(
            str(src), "conversion audit end to end", "e2e_audit",
            pbdir, _profile(src), ["math", "stats"],
        )
        return src, pbdir, gp.rules_path

    def test_generated_draft_requires_named_reviewer(
        self, tmp_path: Path
    ) -> None:
        src, pbdir, rules = self._generate(tmp_path)
        with pytest.raises(SystemExit, match="GENERATED DRAFT"):
            run_main([
                "--source", str(src), "--goal", "conversion audit",
                "--playbook", "e2e_audit", "--rules", str(rules),
                "--approver", "Saif", "--yes",
                "--out", str(tmp_path / "out"),
                "--playbook-dir", str(pbdir),
            ])

    def test_end_to_end_generate_approve_run_seal(
        self, tmp_path: Path
    ) -> None:
        src, pbdir, rules = self._generate(tmp_path)
        final = run_main([
            "--source", str(src), "--goal", "conversion audit",
            "--playbook", "e2e_audit", "--rules", str(rules),
            "--approver", "Saif", "--yes",
            "--playbook-approved-by", "Saif",
            "--out", str(tmp_path / "out"),
            "--playbook-dir", str(pbdir),
        ])
        assert (final / "manifest.json").exists()
        assert (final / "handoff_manifest.json").exists()
        findings = json.loads(
            (final / "findings" / "stats.json").read_text("utf-8")
        )
        assert findings["findings"]["alpha"] == 0.05
        assert (final.parent / "compatibility_report.md").exists()

    def test_curated_playbook_needs_no_extra_approval(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        pbdir = _pbdir(tmp_path)
        final = run_main([
            "--source", str(src),
            "--goal", "universal descriptive audit: distribution shape",
            "--playbook", "universal_audit",
            "--rules", str(_minimal_rules(tmp_path)),
            "--approver", "Saif", "--yes",
            "--out", str(tmp_path / "out"),
            "--playbook-dir", str(pbdir),
        ])
        assert (final / "manifest.json").exists()

    def test_missing_rules_is_an_early_clean_exit(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        with pytest.raises(SystemExit, match="no rules"):
            run_main([
                "--source", str(src),
                "--goal", "universal descriptive audit",
                "--playbook", "universal_audit",
                "--approver", "Saif", "--yes",
                "--out", str(tmp_path / "out"),
                "--playbook-dir", str(_pbdir(tmp_path)),
            ])

    def test_override_prints_loud_warning(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        pbdir = _pbdir(tmp_path)
        run_main([
            "--source", str(src),
            "--goal", "universal descriptive audit: distribution shape",
            "--playbook", "universal_audit",
            "--rules", str(_minimal_rules(tmp_path)),
            "--approver", "Saif", "--yes",
            "--max-exception-rate", "1.5",
            "--out", str(tmp_path / "out"),
            "--playbook-dir", str(pbdir),
        ])
        out = capsys.readouterr().out
        assert "OVERRIDE" in out
        assert "evidence" in out

    def test_interactive_fallback_asks_for_missing_inputs(
        self, tmp_path: Path, monkeypatch: Any
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        pbdir = _pbdir(tmp_path)
        answers = iter([
            str(src),                                   # source
            "universal descriptive audit: shape",       # goal
            "universal_audit",                          # playbook
            "Saif",                                     # approver
        ])
        monkeypatch.setattr("builtins.input",
                            lambda _="": next(answers))
        final = run_main([
            "--yes",
            "--rules", str(_minimal_rules(tmp_path)),
            "--out", str(tmp_path / "out"),
            "--playbook-dir", str(pbdir),
        ])
        assert (final / "manifest.json").exists()

    def test_unknown_playbook_is_a_clean_exit(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        with pytest.raises(SystemExit, match="not found"):
            run_main([
                "--source", str(src), "--goal", "g",
                "--playbook", "does_not_exist",
                "--approver", "Saif", "--yes",
                "--out", str(tmp_path / "out"),
                "--playbook-dir", str(_pbdir(tmp_path)),
            ])


# ── hunt regressions ─────────────────────────────────────────────────────────


class TestHuntRegressions:
    def test_l1_hostile_goal_text_survives_sanitized(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        gp = compile_playbook(
            str(src), 'audit "Q3" results\nacross \\ regions',
            "quote_goal", _pbdir(tmp_path), _profile(src), ["math"],
        )
        pb = load_playbook(gp.playbook_path)  # valid despite the quotes
        assert "Q3" in pb.description
        assert '"Q3"' not in pb.description   # quotes neutralized

    def test_l4_curated_name_shadowing_refused(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        with pytest.raises(GeneratorError, match="SHADOWED"):
            compile_playbook(str(src), "g", "universal_audit",
                             _pbdir(tmp_path), _profile(src), ["math"])

    def test_l5_path_fragment_in_name_is_a_clean_exit(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        with pytest.raises(SystemExit, match="valid playbook name"):
            run_main([
                "--source", str(src), "--goal", "g",
                "--playbook", "../sneaky",
                "--approver", "Saif", "--yes",
                "--out", str(tmp_path / "out"),
                "--playbook-dir", str(_pbdir(tmp_path)),
            ])

    def test_l7_invalid_rules_json_is_a_clean_exit(
        self, tmp_path: Path
    ) -> None:
        src = _csvfile(tmp_path / "d.csv")
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(SystemExit, match="not valid JSON"):
            run_main([
                "--source", str(src), "--goal", "g",
                "--playbook", "universal_audit",
                "--rules", str(bad),
                "--approver", "Saif", "--yes",
                "--out", str(tmp_path / "out"),
                "--playbook-dir", str(_pbdir(tmp_path)),
            ])
