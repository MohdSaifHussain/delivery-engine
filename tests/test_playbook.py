"""Playbook loader tests — the constitution, planted and verified.

Philosophy: for every validation rule V1-V9, plant a playbook that
violates exactly that rule and verify it fails with the right error.
Then verify the reference playbook loads completely and correctly.
A constitution that cannot reject a violation is not a constitution.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from delivery_engine import (
    AiSlot,
    GateMode,
    PlaybookError,
    StageKind,
    load_playbook,
)

REFERENCE = Path(__file__).parent.parent / "playbooks" / "churn_analysis.toml"

VALID_HEAD = '''
schema_version = 1

[playbook]
name = "test"
version = "1.0.0"
description = "test playbook"
'''

VALID_GATE_STAGE = '''
[[stages]]
id = "gate"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"
'''

VALID_TAIL = '''
[deliverables]
artifacts = ["audit_log", "manifest"]
'''


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "pb.toml"
    p.write_text(body, encoding="utf-8")
    return p


# ── The reference playbook is fully constitutional ───────────────────────────


class TestReferencePlaybook:
    def test_loads(self) -> None:
        pb = load_playbook(REFERENCE)
        assert pb.name == "churn_analysis"
        assert pb.schema_version == 1

    def test_first_stage_is_deterministic_gate(self) -> None:
        pb = load_playbook(REFERENCE)
        assert pb.stages[0].kind is StageKind.KIT
        assert pb.stages[0].gate is GateMode.MUST_PASS

    def test_all_ai_stages_use_findings_store(self) -> None:
        pb = load_playbook(REFERENCE)
        ai_stages = [s for s in pb.stages if s.kind is StageKind.AI]
        assert len(ai_stages) >= 3
        assert all(s.numbers_from == "findings_store" for s in ai_stages)

    def test_mandatory_deliverables_present(self) -> None:
        pb = load_playbook(REFERENCE)
        assert "audit_log" in pb.artifacts
        assert "manifest" in pb.artifacts

    def test_requirements_parsed(self) -> None:
        pb = load_playbook(REFERENCE)
        assert pb.requirements.min_rows == 100
        assert "binary_target" in pb.requirements.required_kinds

    def test_ai_slots_typed(self) -> None:
        pb = load_playbook(REFERENCE)
        eda = next(s for s in pb.stages if s.stage_id == "eda")
        assert eda.slot is AiSlot.EDA_NOTEBOOK


# ── V1-V9: plant each violation, verify each rejection ───────────────────────


class TestConstitution:
    def test_v1_duplicate_stage_ids_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE + '''
[[stages]]
id = "gate"
kind = "package"
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V1\)"):
            load_playbook(_write(tmp_path, body))

    def test_v2_ai_first_stage_rejected(self, tmp_path: Path) -> None:
        """The injected-numbers rule's precondition: gates run first."""
        body = VALID_HEAD + '''
[[stages]]
id = "eda"
kind = "ai"
slot = "eda_notebook"
numbers_from = "findings_store"
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V2"):
            load_playbook(_write(tmp_path, body))

    def test_v2_advisory_first_stage_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + '''
[[stages]]
id = "gate"
kind = "kit"
tool = "analystkit_profile"
gate = "advisory"
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V2"):
            load_playbook(_write(tmp_path, body))

    def test_v3_numbers_from_anything_else_rejected(self, tmp_path: Path) -> None:
        """The injected-numbers rule itself: charter 4.1 as executable law."""
        body = VALID_HEAD + VALID_GATE_STAGE + '''
[[stages]]
id = "eda"
kind = "ai"
slot = "eda_notebook"
numbers_from = "model_generated"
needs = ["gate"]
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match="injected-numbers"):
            load_playbook(_write(tmp_path, body))

    def test_v3_numbers_from_missing_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE + '''
[[stages]]
id = "eda"
kind = "ai"
slot = "eda_notebook"
needs = ["gate"]
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match="numbers_from"):
            load_playbook(_write(tmp_path, body))

    def test_v4_feeds_deterministic_without_approval_rejected(
        self, tmp_path: Path
    ) -> None:
        """Human Gate 2: charter 4.4 as executable law."""
        body = VALID_HEAD + VALID_GATE_STAGE + '''
[[stages]]
id = "rules"
kind = "ai"
slot = "rules_draft"
numbers_from = "findings_store"
feeds_deterministic = true
human_approval = false
needs = ["gate"]
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match="Human Gate 2"):
            load_playbook(_write(tmp_path, body))

    def test_v4_feeds_deterministic_with_approval_accepted(
        self, tmp_path: Path
    ) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE + '''
[[stages]]
id = "rules"
kind = "ai"
slot = "rules_draft"
numbers_from = "findings_store"
feeds_deterministic = true
human_approval = true
needs = ["gate"]
''' + VALID_TAIL
        pb = load_playbook(_write(tmp_path, body))
        rules = next(s for s in pb.stages if s.stage_id == "rules")
        assert rules.human_approval is True

    def test_v5_unsupported_schema_version_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD.replace("schema_version = 1", "schema_version = 99")
        body += VALID_GATE_STAGE + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V5\)"):
            load_playbook(_write(tmp_path, body))

    def test_v6_unknown_key_rejected(self, tmp_path: Path) -> None:
        """Typos never become silent misconfiguration."""
        body = VALID_HEAD + '''
[[stages]]
id = "gate"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"
gaurdrail = true
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V6"):
            load_playbook(_write(tmp_path, body))

    def test_v7_missing_manifest_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE + '''
[deliverables]
artifacts = ["audit_log"]
'''
        with pytest.raises(PlaybookError, match=r"\(V7"):
            load_playbook(_write(tmp_path, body))

    def test_v8_unknown_tool_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + '''
[[stages]]
id = "gate"
kind = "kit"
tool = "analystkit_hack_everything"
gate = "must_pass"
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V8\)"):
            load_playbook(_write(tmp_path, body))

    def test_v8_unknown_slot_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE + '''
[[stages]]
id = "x"
kind = "ai"
slot = "free_generation"
numbers_from = "findings_store"
needs = ["gate"]
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V8\)"):
            load_playbook(_write(tmp_path, body))

    def test_v9_forward_reference_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + '''
[[stages]]
id = "gate"
kind = "kit"
tool = "analystkit_profile"
gate = "must_pass"
needs = ["later"]

[[stages]]
id = "later"
kind = "package"
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V9\)"):
            load_playbook(_write(tmp_path, body))

    def test_v9_unknown_reference_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE + '''
[[stages]]
id = "pkg"
kind = "package"
needs = ["ghost_stage"]
''' + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V9\)"):
            load_playbook(_write(tmp_path, body))


# ── Edges ─────────────────────────────────────────────────────────────────────


class TestEdges:
    def test_missing_file_clean_error(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="not found"):
            load_playbook(tmp_path / "ghost.toml")

    def test_invalid_toml_clean_error(self, tmp_path: Path) -> None:
        with pytest.raises(PlaybookError, match="not valid TOML"):
            load_playbook(_write(tmp_path, "this is [ not toml"))

    def test_empty_stages_rejected(self, tmp_path: Path) -> None:
        # stages = [] must be top-level: placed after [playbook] it would
        # belong to that table (TOML 1.0.0 scoping) and fail as unknown key
        body = "schema_version = 1\nstages = []\n" + \
            VALID_HEAD.replace("schema_version = 1\n", "") + VALID_TAIL
        with pytest.raises(PlaybookError, match="at least one stage"):
            load_playbook(_write(tmp_path, body))

    def test_min_rows_boolean_rejected(self, tmp_path: Path) -> None:
        """bool is an int subclass in Python — must not slip through."""
        body = VALID_HEAD + '''
[requirements]
min_rows = true
''' + VALID_GATE_STAGE + VALID_TAIL
        with pytest.raises(PlaybookError, match="min_rows"):
            load_playbook(_write(tmp_path, body))

    def test_playbook_is_frozen(self) -> None:
        pb = load_playbook(REFERENCE)
        with pytest.raises(AttributeError):
            pb.name = "hacked"  # type: ignore[misc]


class TestV10Identifiers:
    """Loophole hunt fix: empty and non-snake_case ids poisoned nothing
    at load time but would poison audit references and filenames later."""

    def test_empty_stage_id_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE.replace('id = "gate"', 'id = ""') + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V10\)"):
            load_playbook(_write(tmp_path, body))

    def test_emoji_stage_id_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD + VALID_GATE_STAGE.replace('id = "gate"', 'id = "🚀"') + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V10\)"):
            load_playbook(_write(tmp_path, body))

    def test_uppercase_playbook_name_rejected(self, tmp_path: Path) -> None:
        body = VALID_HEAD.replace('name = "test"', 'name = "TestPlaybook"') \
            + VALID_GATE_STAGE + VALID_TAIL
        with pytest.raises(PlaybookError, match=r"\(V10\)"):
            load_playbook(_write(tmp_path, body))
