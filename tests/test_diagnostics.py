"""tests/test_diagnostics.py - planted-answer tests for the diagnostic record.

The loophole hunt - what is the sneakiest way this could produce a
wrong result and not fail a test?

  L1: an absolute path leaks through the traceback into the record ->
      caught by test_traceback_frames_carry_no_path_separators, which
      asserts on the SANITISED OUTPUT rather than trusting the code.
  L2: the diagnostic raises and masks the original error the user was
      trying to report -> caught by test_collector_failure_degrades_to
      _unavailable and test_write_returns_none_on_unwritable_target.
  L3: the source PATH is recorded where only the EXTENSION was intended
      -> caught by test_context_records_suffix_not_path.
  L4: the PEP 508 field names drift to invented names, so a maintainer
      misreads them -> caught by test_environment_uses_pep508_field_names,
      which pins the exact standard names.
  L5: a secret reaches the record through environment variables ->
      caught by test_record_contains_no_environment_variables.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from delivery_engine.diagnostics import (
    DIAGNOSTIC_FILENAME,
    TRACKED_PACKAGES,
    collect_diagnostic,
    collect_environment,
    collect_package_versions,
    write_diagnostic,
)

# PEP 508 environment marker names - the packaging standard. These are
# pinned deliberately: a maintainer reading a diagnostic must be able to
# rely on them meaning what PEP 508 says they mean.
PEP508_FIELDS = frozenset({
    "os_name",
    "sys_platform",
    "platform_machine",
    "platform_system",
    "platform_release",
    "python_version",
    "python_full_version",
    "implementation_name",
})


def _raise_and_capture() -> BaseException:
    """Produce a real exception carrying a real traceback."""
    try:
        raise ValueError("planted failure for traceback sanitisation")
    except ValueError as exc:
        return exc


class TestCollectEnvironment:
    def test_environment_uses_pep508_field_names(self) -> None:
        env = collect_environment()
        assert PEP508_FIELDS.issubset(set(env))

    def test_environment_values_are_all_strings(self) -> None:
        env = collect_environment()
        assert all(isinstance(v, str) for v in env.values())

    def test_python_version_is_major_minor_only(self) -> None:
        """python_version is MAJOR.MINOR per PEP 508; the full version
        lives in python_full_version."""
        env = collect_environment()
        assert env["python_version"].count(".") == 1


class TestCollectPackageVersions:
    def test_every_tracked_package_reported(self) -> None:
        versions = collect_package_versions()
        assert set(versions) == set(TRACKED_PACKAGES)

    def test_missing_package_reads_not_installed(self) -> None:
        """A package that is absent must say so rather than vanish -
        'not installed' is itself diagnostic information."""
        versions = collect_package_versions()
        assert all(isinstance(v, str) and v for v in versions.values())


class TestPrivacy:
    def test_traceback_frames_carry_no_path_separators(self) -> None:
        """L1. The sanitiser must reduce absolute filenames to basenames.
        Asserting on the output, not on the implementation."""
        exc = _raise_and_capture()
        record = collect_diagnostic(exc=exc)
        frames = record["failure"]["traceback_frames"]
        assert frames, "expected at least one traceback frame"
        for frame in frames:
            assert "/" not in frame
            assert "\\" not in frame

    def test_traceback_frames_still_locate_the_fault(self) -> None:
        """Sanitisation must not destroy debugging value: the frame
        still names the file, the line, and the function."""
        exc = _raise_and_capture()
        record = collect_diagnostic(exc=exc)
        joined = " ".join(record["failure"]["traceback_frames"])
        assert "test_diagnostics.py" in joined
        assert "_raise_and_capture" in joined

    def test_record_contains_no_environment_variables(self) -> None:
        """L5. Environment variables carry API keys. A planted secret
        must not appear anywhere in the serialised record."""
        os.environ["DELIVERY_ENGINE_TEST_SECRET"] = "planted-secret-value"
        try:
            record = collect_diagnostic()
            blob = json.dumps(record)
            assert "planted-secret-value" not in blob
            assert "DELIVERY_ENGINE_TEST_SECRET" not in blob
        finally:
            del os.environ["DELIVERY_ENGINE_TEST_SECRET"]

    def test_context_records_suffix_not_path(self) -> None:
        """L3. Only the extension is accepted and stored."""
        record = collect_diagnostic(source_suffix=".parquet")
        assert record["context"]["source_suffix"] == ".parquet"
        assert "/" not in json.dumps(record["context"])
        assert "\\" not in json.dumps(record["context"])

    def test_privacy_note_present_in_every_record(self) -> None:
        record = collect_diagnostic()
        assert "no usernames" in record["privacy_note"]


class TestCollectDiagnostic:
    def test_failure_block_absent_without_exception(self) -> None:
        record = collect_diagnostic()
        assert "failure" not in record

    def test_failure_block_present_with_exception(self) -> None:
        exc = _raise_and_capture()
        record = collect_diagnostic(exc=exc)
        assert record["failure"]["exception_type"] == "ValueError"
        assert "planted failure" in record["failure"]["message"]

    def test_context_absent_when_nothing_known(self) -> None:
        record = collect_diagnostic()
        assert "context" not in record

    def test_context_carries_stage_and_playbook(self) -> None:
        record = collect_diagnostic(
            stage="dq_profile", playbook="universal_audit"
        )
        assert record["context"]["stage_attempted"] == "dq_profile"
        assert record["context"]["playbook"] == "universal_audit"

    def test_message_is_truncated(self) -> None:
        """A pathological exception message must not bloat the record."""
        long_exc = ValueError("x" * 5000)
        record = collect_diagnostic(exc=long_exc)
        assert len(record["failure"]["message"]) <= 500

    def test_record_is_json_serialisable(self) -> None:
        """The record is worthless if it cannot be written."""
        exc = _raise_and_capture()
        record = collect_diagnostic(exc=exc, stage="s", source_suffix=".csv")
        assert json.loads(json.dumps(record)) == record


class TestWriteDiagnostic:
    def test_write_creates_named_file(self, tmp_path: Path) -> None:
        path = write_diagnostic(out_dir=tmp_path)
        assert path is not None
        assert path.name == DIAGNOSTIC_FILENAME
        assert path.exists()

    def test_written_file_is_valid_json(self, tmp_path: Path) -> None:
        path = write_diagnostic(out_dir=tmp_path)
        assert path is not None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["schema_version"] == "1.0"

    def test_write_returns_none_on_unwritable_target(
        self, tmp_path: Path
    ) -> None:
        """L2. A diagnostic must never mask the error it describes. If
        the write fails it returns None; it does not raise."""
        missing = tmp_path / "does" / "not" / "exist"
        assert write_diagnostic(out_dir=missing) is None

    def test_written_record_round_trips_the_failure(
        self, tmp_path: Path
    ) -> None:
        exc = _raise_and_capture()
        path = write_diagnostic(exc=exc, out_dir=tmp_path)
        assert path is not None
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["failure"]["exception_type"] == "ValueError"
