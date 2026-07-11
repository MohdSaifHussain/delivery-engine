"""Planner tests - every decision path planted and verified.

The planted answers: synthetic profile findings shaped exactly like the
analystkit_mcp envelope, with known column kinds, run against a known
playbook library. Each decision path (deterministic single, deterministic
scored, human choice, LLM tie-break, ambiguity, hard failures) is
exercised, and the charter's non-overridability rules are proven:
neither the LLM nor a human choice can rescue a failed requirements check.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from delivery_engine.planner import (
    ColumnKind,
    DecisionSource,
    PlannerAmbiguityError,
    PlannerError,
    approve_plan,
    check_requirements,
    classify_columns,
    make_plan,
    render_plan,
)

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"


def _col(name: str, dtype: str, total: int, nulls: int, distinct: int) -> dict[str, Any]:
    return {
        "name": name, "dtype": dtype, "total": total, "nulls": nulls,
        "completeness": 1.0, "distinct": distinct, "case_variants": 0,
        "valid_ratio": 1.0,
    }


@pytest.fixture()
def churn_profile() -> dict[str, Any]:
    """A profile that qualifies for churn_analysis: id + binary target,
    1000 rows."""
    return {
        "columns": [
            _col("customer_id", "VARCHAR", 1000, 0, 1000),
            _col("churned", "VARCHAR", 1000, 0, 2),
            _col("tenure_months", "BIGINT", 1000, 0, 60),
            _col("signup_date", "TIMESTAMP", 1000, 0, 950),
            _col("plan_type", "VARCHAR", 1000, 0, 4),
        ],
        "dama_scores": {"completeness": 1.0},
    }


@pytest.fixture()
def no_target_profile() -> dict[str, Any]:
    """No binary column anywhere - churn requirements must fail."""
    return {
        "columns": [
            _col("customer_id", "VARCHAR", 1000, 0, 1000),
            _col("amount", "DOUBLE", 1000, 0, 900),
        ],
        "dama_scores": {"completeness": 1.0},
    }


# ── Classification: the declared defaults do what they declare ───────────────


class TestClassification:
    def test_id_column_detected(self, churn_profile: dict[str, Any]) -> None:
        kinds = classify_columns(churn_profile)
        assert ColumnKind.ID_COLUMN in kinds["customer_id"]

    def test_binary_target_detected(self, churn_profile: dict[str, Any]) -> None:
        kinds = classify_columns(churn_profile)
        assert ColumnKind.BINARY_TARGET in kinds["churned"]

    def test_timestamp_detected(self, churn_profile: dict[str, Any]) -> None:
        kinds = classify_columns(churn_profile)
        assert ColumnKind.TIMESTAMP_COLUMN in kinds["signup_date"]

    def test_numeric_detected(self, churn_profile: dict[str, Any]) -> None:
        kinds = classify_columns(churn_profile)
        assert ColumnKind.NUMERIC_COLUMN in kinds["tenure_months"]

    def test_categorical_detected(self, churn_profile: dict[str, Any]) -> None:
        kinds = classify_columns(churn_profile)
        assert ColumnKind.CATEGORICAL_COLUMN in kinds["plan_type"]

    def test_a_column_can_hold_multiple_kinds(
        self, churn_profile: dict[str, Any]
    ) -> None:
        # 'churned': VARCHAR, 2 distinct => binary target AND categorical
        kinds = classify_columns(churn_profile)
        assert set(kinds["churned"]) >= {
            ColumnKind.BINARY_TARGET, ColumnKind.CATEGORICAL_COLUMN,
        }

    def test_empty_profile_clean_error(self) -> None:
        with pytest.raises(PlannerError, match="no columns"):
            classify_columns({"columns": []})


# ── Requirements: deterministic and honest ────────────────────────────────────


class TestRequirements:
    def test_churn_profile_qualifies(self, churn_profile: dict[str, Any]) -> None:
        from delivery_engine import load_playbook

        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        results = check_requirements(pb, churn_profile, "data.csv")
        assert all(ok for _, ok, _ in results)

    def test_missing_target_fails_with_named_check(
        self, no_target_profile: dict[str, Any]
    ) -> None:
        from delivery_engine import load_playbook

        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        results = check_requirements(pb, no_target_profile, "data.csv")
        failed = [check for check, ok, _ in results if not ok]
        assert "required kind 'binary_target'" in failed

    def test_notes_name_the_qualifying_columns(
        self, churn_profile: dict[str, Any]
    ) -> None:
        from delivery_engine import load_playbook

        pb = load_playbook(PLAYBOOKS / "churn_analysis.toml")
        results = check_requirements(pb, churn_profile, "data.csv")
        target_row = next(r for r in results if "binary_target" in r[0])
        assert "churned" in target_row[2]


# ── Planning: every decision path ─────────────────────────────────────────────


class TestPlanning:
    def test_single_qualified_deterministic(
        self, churn_profile: dict[str, Any]
    ) -> None:
        plan = make_plan(
            "churn analysis on telecom data", "data.csv",
            churn_profile, PLAYBOOKS,
        )
        assert plan.playbook_name == "churn_analysis"
        assert plan.decision_source is DecisionSource.DETERMINISTIC
        assert plan.approved is False

    def test_no_qualified_raises_with_reasons(
        self, no_target_profile: dict[str, Any], tmp_path: Path
    ) -> None:
        # A churn-only library: the general data_quality_review archetype
        # (added in step 5) legitimately accepts this profile, so the
        # no-qualified path needs a library where requirements CAN fail.
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "churn_analysis.toml").write_text(
            (PLAYBOOKS / "churn_analysis.toml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        with pytest.raises(PlannerError, match="binary_target"):
            make_plan("churn analysis", "data.csv", no_target_profile, lib)

    def test_human_choice_recorded(self, churn_profile: dict[str, Any]) -> None:
        plan = make_plan(
            "some goal", "data.csv", churn_profile, PLAYBOOKS,
            chosen_playbook="churn_analysis",
        )
        assert plan.decision_source is DecisionSource.HUMAN

    def test_human_choice_cannot_override_failed_requirements(
        self, no_target_profile: dict[str, Any]
    ) -> None:
        """Charter 4.6: nothing overrides a failed deterministic check."""
        with pytest.raises(PlannerError, match="does not override"):
            make_plan(
                "churn", "data.csv", no_target_profile, PLAYBOOKS,
                chosen_playbook="churn_analysis",
            )

    def test_empty_goal_rejected(self, churn_profile: dict[str, Any]) -> None:
        with pytest.raises(PlannerError, match="Goal"):
            make_plan("   ", "data.csv", churn_profile, PLAYBOOKS)

    def test_plan_digest_reproducible(self, churn_profile: dict[str, Any]) -> None:
        a = make_plan("churn analysis", "data.csv", churn_profile, PLAYBOOKS)
        b = make_plan("churn analysis", "data.csv", churn_profile, PLAYBOOKS)
        assert a.plan_digest() == b.plan_digest()  # timestamps outside the hash


# ── Ambiguity and the LLM resolver (mocked; bounded; logged) ─────────────────


def _second_playbook(tmp_path: Path) -> Path:
    """A library with churn_analysis plus a near-identical rival, so both
    qualify and neither wins on goal keywords for a vague goal."""
    lib = tmp_path / "lib"
    lib.mkdir()
    ref = (PLAYBOOKS / "churn_analysis.toml").read_text(encoding="utf-8")
    (lib / "churn_analysis.toml").write_text(ref, encoding="utf-8")
    rival = ref.replace(
        'name = "churn_analysis"', 'name = "retention_review"'
    ).replace(
        'description = "Customer churn analysis: DQ-gated EDA, narrative, packaged as re-performable evidence"',
        'description = "Retention review with gates and packaged narrative"',
    )
    (lib / "retention_review.toml").write_text(rival, encoding="utf-8")
    return lib


class TestAmbiguity:
    def test_tie_without_key_raises_ambiguity_with_candidates(
        self, churn_profile: dict[str, Any], tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        lib = _second_playbook(tmp_path)
        with pytest.raises(PlannerAmbiguityError) as exc_info:
            make_plan("do the project", "data.csv", churn_profile, lib)
        assert set(exc_info.value.candidates) == {
            "churn_analysis", "retention_review",
        }

    def test_goal_keywords_break_tie_deterministically(
        self, churn_profile: dict[str, Any], tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        lib = _second_playbook(tmp_path)
        plan = make_plan(
            "churn analysis please", "data.csv", churn_profile, lib,
        )
        assert plan.playbook_name == "churn_analysis"
        assert plan.decision_source is DecisionSource.DETERMINISTIC

    def _mock_sdk(
        self, monkeypatch: pytest.MonkeyPatch, reply: str
    ) -> None:
        class _Block:
            type = "text"

            def __init__(self, text: str) -> None:
                self.text = text

        class _Message:
            def __init__(self) -> None:
                self.content = [_Block(reply)]

        class _Messages:
            def create(self, **kwargs: Any) -> _Message:
                return _Message()

        class _Anthropic:
            def __init__(self, **kwargs: Any) -> None:
                self.messages = _Messages()

        fake = types.ModuleType("anthropic")
        fake.Anthropic = _Anthropic  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "anthropic", fake)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def test_llm_resolves_tie_and_is_logged(
        self, churn_profile: dict[str, Any], tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._mock_sdk(
            monkeypatch,
            "CHOICE: retention_review\nREASON: goal wording suggests review.",
        )
        lib = _second_playbook(tmp_path)
        plan = make_plan("do the project", "data.csv", churn_profile, lib)
        assert plan.playbook_name == "retention_review"
        assert plan.decision_source is DecisionSource.LLM
        assert "retention_review" in plan.decision_rationale

    def test_llm_inventing_a_name_is_rejected(
        self, churn_profile: dict[str, Any], tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The resolver may pick, never invent."""
        self._mock_sdk(
            monkeypatch,
            "CHOICE: totally_new_playbook\nREASON: I made it up.",
        )
        lib = _second_playbook(tmp_path)
        with pytest.raises(PlannerError, match="never invent"):
            make_plan("do the project", "data.csv", churn_profile, lib)


# ── Human Gate 1 ──────────────────────────────────────────────────────────────


class TestHumanGate1:
    def test_plan_born_unapproved(self, churn_profile: dict[str, Any]) -> None:
        plan = make_plan("churn analysis", "data.csv", churn_profile, PLAYBOOKS)
        assert plan.approved is False
        assert "NOT APPROVED" in render_plan(plan)

    def test_approval_recorded(self, churn_profile: dict[str, Any]) -> None:
        plan = make_plan("churn analysis", "data.csv", churn_profile, PLAYBOOKS)
        approved = approve_plan(plan, "Saif")
        assert approved.approved is True
        assert approved.approved_by == "Saif"
        assert approved.approved_at_ist is not None
        assert plan.approved is False  # original untouched (frozen)

    def test_empty_approver_rejected(self, churn_profile: dict[str, Any]) -> None:
        plan = make_plan("churn analysis", "data.csv", churn_profile, PLAYBOOKS)
        with pytest.raises(PlannerError, match="Approver"):
            approve_plan(plan, "   ")

    def test_double_approval_rejected(self, churn_profile: dict[str, Any]) -> None:
        plan = make_plan("churn analysis", "data.csv", churn_profile, PLAYBOOKS)
        approved = approve_plan(plan, "Saif")
        with pytest.raises(PlannerError, match="already approved"):
            approve_plan(approved, "Someone Else")

    def test_approval_does_not_change_plan_digest(
        self, churn_profile: dict[str, Any]
    ) -> None:
        plan = make_plan("churn analysis", "data.csv", churn_profile, PLAYBOOKS)
        approved = approve_plan(plan, "Saif")
        assert plan.plan_digest() == approved.plan_digest()


class TestProfileFailClosed:
    """Loophole hunt fixes: corrupt or malformed profiles are rejected
    with clean errors, never classified silently and never raw-crashed."""

    def test_column_entry_not_a_dict_clean_error(self) -> None:
        with pytest.raises(PlannerError, match="not an object"):
            classify_columns({"columns": ["a", "b"]})

    def test_column_missing_keys_clean_error(self) -> None:
        with pytest.raises(PlannerError, match="missing keys"):
            classify_columns({"columns": [{"name": "x"}]})

    def test_non_integer_counts_clean_error(self) -> None:
        bad = {"columns": [{
            "name": "a", "dtype": "VARCHAR",
            "total": "many", "nulls": 0, "distinct": 1,
        }]}
        with pytest.raises(PlannerError, match="must be integers"):
            classify_columns(bad)

    def test_nulls_exceeding_total_clean_error(self) -> None:
        bad = {"columns": [{
            "name": "a", "dtype": "VARCHAR",
            "total": 100, "nulls": 150, "distinct": 2,
        }]}
        with pytest.raises(PlannerError, match="corrupt"):
            classify_columns(bad)
