"""delivery_engine.diagnostics - the reproducible-environment record.

When a run fails before the executor starts - a source that will not
load, a playbook that will not validate, a missing dependency - no
audit log exists yet, because the audit log is written by the executor.
The user is left with a terminal traceback, and the maintainer is left
with a bug report that cannot be reproduced.

This module closes that gap. It writes a diagnostic record the user can
attach to a GitHub issue: enough to reproduce the environment exactly,
and nothing else.

Design positions:

- PEP 508 ENVIRONMENT MARKERS. The environment block uses the field
  names defined by PEP 508 (os_name, sys_platform, platform_machine,
  platform_system, platform_release, python_version,
  python_full_version, implementation_name). These are the Python
  packaging standard for describing an environment - not an ad-hoc
  list. A maintainer reading them knows exactly what they mean.

- DATA MINIMISATION. Only what is necessary to diagnose. No usernames,
  no hostnames, no absolute paths, no environment variables (they carry
  API keys), no dataset content, no column names. The source file is
  recorded by EXTENSION only - ".parquet" tells you the reader path
  that failed; the path would tell you the user's directory structure.

- SANITISED TRACEBACK. traceback.extract_tb gives structured frames.
  We keep filename (basename only), line number, and function name -
  the full debugging value of a traceback with none of the path
  leakage. A frame reading "sources.py:105 in load_dataframe" locates
  the fault precisely without revealing C:\\Users\\<name>\\.

- LOCAL ONLY, NEVER TRANSMITTED. The file is written to the current
  working directory. Nothing is sent anywhere. The user reads it,
  decides, and attaches it to an issue - or does not. Consent is the
  act of attaching, exactly as it is for a pasted stack trace.

- NO SUBPROCESS. A crash reporter that crashes is worse than none.
  Node is detected by shutil.which (presence on PATH) rather than by
  running it. Every collector is individually guarded: a failure to
  collect one field records "unavailable" and continues.

- NOT A FINDING. Diagnostics are not evidence and never enter the
  Findings Store or a manifest (Charter 4.3). They describe the
  machine, not the data.
"""
from __future__ import annotations

import json
import platform
import shutil
import sys
import traceback
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import TracebackType
from typing import Any, Final

__all__ = [
    "DIAGNOSTIC_FILENAME",
    "TRACKED_PACKAGES",
    "collect_diagnostic",
    "collect_environment",
    "collect_package_versions",
    "write_diagnostic",
]

DIAGNOSTIC_FILENAME: Final[str] = "delivery-engine-diagnostic.json"

SCHEMA_VERSION: Final[str] = "1.0"

#: Packages whose versions materially change engine behaviour. duckdb
#: and pandas drive the reader; scikit-learn drives the deterministic
#: baseline; scipy drives the stats and math stages.
TRACKED_PACKAGES: Final[tuple[str, ...]] = (
    "delivery-engine",
    "analystkit",
    "analystkit-mcp",
    "opskit-mcp",
    "duckdb",
    "pandas",
    "numpy",
    "scikit-learn",
    "scipy",
)

UNAVAILABLE: Final[str] = "unavailable"

PRIVACY_NOTE: Final[str] = (
    "This record contains no usernames, hostnames, absolute paths, "
    "environment variables, or dataset content. Traceback frames carry "
    "file basenames only. Nothing is transmitted; the file is written "
    "locally and attaching it to an issue is your decision."
)


def collect_environment() -> dict[str, str]:
    """Environment described with PEP 508 marker names.

    Each field is collected independently: if one raises, it records
    UNAVAILABLE rather than aborting the whole diagnostic.
    """
    collectors: dict[str, Any] = {
        "os_name": lambda: __import__("os").name,
        "sys_platform": lambda: sys.platform,
        "platform_machine": platform.machine,
        "platform_system": platform.system,
        "platform_release": platform.release,
        "python_version": lambda: ".".join(
            platform.python_version_tuple()[:2]
        ),
        "python_full_version": platform.python_version,
        "implementation_name": lambda: sys.implementation.name,
    }
    env: dict[str, str] = {}
    for key, fn in collectors.items():
        try:
            env[key] = str(fn())
        except Exception:  # a diagnostic never raises
            env[key] = UNAVAILABLE
    return env


def collect_package_versions() -> dict[str, str]:
    """Installed versions of the packages that change engine behaviour."""
    versions: dict[str, str] = {}
    for pkg in TRACKED_PACKAGES:
        try:
            versions[pkg] = version(pkg)
        except PackageNotFoundError:
            versions[pkg] = "not installed"
        except Exception:  # a diagnostic never raises
            versions[pkg] = UNAVAILABLE
    return versions


def _collect_node() -> dict[str, str]:
    """Node presence on PATH - the docx/pptx builders shell out to it.

    Presence only, by shutil.which. Running `node --version` would need
    a subprocess, and a diagnostic tool must not introduce a failure
    mode of its own.
    """
    try:
        found = shutil.which("node")
    except Exception:  # a diagnostic never raises
        return {"node_on_path": UNAVAILABLE}
    return {"node_on_path": "yes" if found else "no"}


def _sanitise_traceback(tb: TracebackType | None) -> list[str]:
    """Structured frames as 'basename.py:LINE in function'.

    traceback.extract_tb yields FrameSummary objects carrying the
    absolute filename. We keep the basename only: the fault is located
    precisely, and the user's directory structure stays private.
    """
    if tb is None:
        return []
    frames: list[str] = []
    try:
        for frame in traceback.extract_tb(tb):
            name = Path(frame.filename).name
            frames.append(f"{name}:{frame.lineno} in {frame.name}")
    except Exception:  # a diagnostic never raises
        return [UNAVAILABLE]
    return frames


def collect_diagnostic(
    exc: BaseException | None = None,
    stage: str | None = None,
    source_suffix: str | None = None,
    playbook: str | None = None,
) -> dict[str, Any]:
    """Assemble the diagnostic record.

    exc            the unhandled exception, if this is a crash report
    stage          the stage or phase being attempted, if known
    source_suffix  the source file EXTENSION only (".csv"), never a path
    playbook       the playbook name, if one had been resolved
    """
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "privacy_note": PRIVACY_NOTE,
        "environment": collect_environment(),
        "packages": collect_package_versions(),
        "runtime": _collect_node(),
    }

    context: dict[str, str] = {}
    if stage is not None:
        context["stage_attempted"] = stage
    if source_suffix is not None:
        context["source_suffix"] = source_suffix
    if playbook is not None:
        context["playbook"] = playbook
    if context:
        record["context"] = context

    if exc is not None:
        record["failure"] = {
            "exception_type": type(exc).__name__,
            "exception_module": type(exc).__module__,
            "message": str(exc)[:500],
            "traceback_frames": _sanitise_traceback(exc.__traceback__),
        }

    return record


def write_diagnostic(
    exc: BaseException | None = None,
    stage: str | None = None,
    source_suffix: str | None = None,
    playbook: str | None = None,
    out_dir: Path | None = None,
) -> Path | None:
    """Write the diagnostic to disk. Returns the path, or None on failure.

    Writes to out_dir (default: current working directory). Returns None
    rather than raising if the write itself fails - a diagnostic must
    never mask the original error it is describing.
    """
    record = collect_diagnostic(exc, stage, source_suffix, playbook)
    target = (out_dir or Path.cwd()) / DIAGNOSTIC_FILENAME
    try:
        target.write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )
    except Exception:  # never mask the original error
        return None
    return target
