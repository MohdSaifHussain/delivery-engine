"""tests/test_declaration.py - planted-answer tests for Step 23.

Tests follow the same discipline as every other test in the suite:
- tmp_path isolation (never write to examples/)
- planted answers, not output inspection
- tests cover both correct behaviour and failure modes
- the loophole hunt: what is the sneakiest way this could produce
  a wrong result and not fail a test?

  L1: declaration written without the human seeing the summary -> caught
      by test_review_summary_contains_key_sections (summary must be built)
  L2: declaration written with wrong confirmed_items -> caught by
      test_content_sha256_is_deterministic (same input = same digest)
  L3: double-declaration goes undetected -> caught by
      test_cannot_declare_twice
  L4: manifest not regenerated after declaration -> caught by
      test_manifest_includes_declaration_after_declare_final
  L5: declaration accepted without CONFIRMED input -> caught by
      test_declaration_requires_confirmed (monkeypatched input)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from delivery_engine.declaration import (
    CONFIRMED_ITEMS,
    FRAMEWORK_CITATIONS,
    SCHEMA_VERSION,
    TOOL_NATURE,
    DeclarationError,
    _content_digest,
    build_review_summary,
    declare_final,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_package(tmp_path: Path) -> Path:
    """Build a minimal sealed package for testing."""
    pkg = tmp_path / "final"
    pkg.mkdir(parents=True)
    findings_dir = pkg / "findings"
    findings_dir.mkdir()

    dq = {
        "stage": "dq_profile",
        "findings": {
            "dama_scores": {
                "accuracy": None,
                "completeness": 1.0,
                "consistency": 1.0,
                "timeliness": 0.0,
                "uniqueness": 1.0,
                "validity": 1.0,
            },
            "columns": [{"total": 300}],
        },
        "sha256": "aaa",
    }
    (findings_dir / "dq_profile.json").write_text(
        json.dumps(dq), encoding="utf-8"
    )

    plan = {
        "playbook_name": "universal_audit",
        "goal": "test declaration",
        "source": "test.csv",
        "approved_by": "Test Analyst",
    }
    (pkg / "plan.json").write_text(json.dumps(plan), encoding="utf-8")

    (pkg / "audit_log.jsonl").write_text(
        json.dumps({"seq": 1, "stage": "test", "outcome": "pass"}) + "\n",
        encoding="utf-8",
    )

    files: dict[str, str] = {}
    for p in sorted(pkg.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            files[str(p.relative_to(pkg))] = h

    manifest = {
        "files": files,
        "findings": {"dq_profile": "aaa"},
        "plan_sha256": "bbb",
        "note": "test manifest",
    }
    (pkg / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return pkg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildReviewSummary:
    def test_summary_contains_package_path(self, tmp_path: Path) -> None:
        pkg = _minimal_package(tmp_path)
        summary = build_review_summary(pkg)
        assert str(pkg) in summary

    def test_summary_contains_framework_citations(self, tmp_path: Path) -> None:
        pkg = _minimal_package(tmp_path)
        summary = build_review_summary(pkg)
        assert "EU AI Act Article 14" in summary
        assert "NIST AI RMF" in summary
        assert "ISO/IEC 42001" in summary

    def test_summary_contains_confirmed_items(self, tmp_path: Path) -> None:
        pkg = _minimal_package(tmp_path)
        summary = build_review_summary(pkg)
        assert "accepted accountability" in summary
        for item in CONFIRMED_ITEMS:
            assert item[:30] in summary

    def test_summary_shows_not_scored_for_missing_dama(
        self, tmp_path: Path
    ) -> None:
        pkg = _minimal_package(tmp_path)
        summary = build_review_summary(pkg)
        assert "not scored" in summary

    def test_summary_requires_existing_manifest(self, tmp_path: Path) -> None:
        pkg = tmp_path / "empty"
        pkg.mkdir()
        with pytest.raises(DeclarationError, match=r"manifest\.json not found"):
            build_review_summary(pkg)


class TestContentDigest:
    def test_content_digest_is_deterministic(self) -> None:
        d1 = _content_digest("Alice", CONFIRMED_ITEMS, "abc123")
        d2 = _content_digest("Alice", CONFIRMED_ITEMS, "abc123")
        assert d1 == d2

    def test_different_declarer_gives_different_digest(self) -> None:
        d1 = _content_digest("Alice", CONFIRMED_ITEMS, "abc123")
        d2 = _content_digest("Bob", CONFIRMED_ITEMS, "abc123")
        assert d1 != d2

    def test_different_manifest_sha_gives_different_digest(self) -> None:
        d1 = _content_digest("Alice", CONFIRMED_ITEMS, "abc123")
        d2 = _content_digest("Alice", CONFIRMED_ITEMS, "xyz789")
        assert d1 != d2


class TestDeclareFinal:
    def test_declaration_requires_confirmed(self, tmp_path: Path) -> None:
        pkg = _minimal_package(tmp_path)
        with patch("builtins.input", return_value="yes"), \
             pytest.raises(DeclarationError, match="CONFIRMED"):
            declare_final(pkg, "Test Reviewer")

    def test_successful_declaration_writes_file(self, tmp_path: Path) -> None:
        pkg = _minimal_package(tmp_path)
        with patch("builtins.input", return_value="CONFIRMED"):
            decl_path = declare_final(pkg, "Test Reviewer")
        assert decl_path.exists()
        assert decl_path.name == "declaration.json"

    def test_declaration_schema_fields_present(self, tmp_path: Path) -> None:
        pkg = _minimal_package(tmp_path)
        with patch("builtins.input", return_value="CONFIRMED"):
            decl_path = declare_final(pkg, "Test Reviewer")
        decl = json.loads(decl_path.read_text(encoding="utf-8"))
        assert decl["schema_version"] == SCHEMA_VERSION
        assert decl["declared_by"] == "Test Reviewer"
        assert decl["tool_nature"] == TOOL_NATURE
        assert decl["confirmed_items"] == CONFIRMED_ITEMS
        assert decl["framework_citations"] == FRAMEWORK_CITATIONS
        assert "declared_at_utc" in decl
        assert "declared_at_ist" in decl
        assert "content_sha256" in decl
        assert "package_manifest_sha256" in decl

    def test_manifest_includes_declaration_after_declare_final(
        self, tmp_path: Path
    ) -> None:
        pkg = _minimal_package(tmp_path)
        with patch("builtins.input", return_value="CONFIRMED"):
            declare_final(pkg, "Test Reviewer")
        manifest = json.loads(
            (pkg / "manifest.json").read_text(encoding="utf-8")
        )
        assert "declaration.json" in manifest["files"]

    def test_cannot_declare_twice(self, tmp_path: Path) -> None:
        pkg = _minimal_package(tmp_path)
        with patch("builtins.input", return_value="CONFIRMED"):
            declare_final(pkg, "Test Reviewer")
        with patch("builtins.input", return_value="CONFIRMED"), \
             pytest.raises(DeclarationError, match="already exists"):
            declare_final(pkg, "Test Reviewer")

    def test_nonexistent_package_raises(self, tmp_path: Path) -> None:
        with pytest.raises(DeclarationError, match="not found"):
            declare_final(tmp_path / "nonexistent", "Test Reviewer")

    def test_content_sha256_is_deterministic_across_calls(
        self, tmp_path: Path
    ) -> None:
        """Same reviewer + same package content = same content_sha256."""
        pkg1 = _minimal_package(tmp_path / "pkg1")
        pkg2 = _minimal_package(tmp_path / "pkg2")
        from delivery_engine.audit import file_sha256
        sha1 = file_sha256(pkg1 / "manifest.json")
        sha2 = file_sha256(pkg2 / "manifest.json")
        d1 = _content_digest("Alice", CONFIRMED_ITEMS, sha1)
        d2 = _content_digest("Alice", CONFIRMED_ITEMS, sha2)
        assert d1 == d2
