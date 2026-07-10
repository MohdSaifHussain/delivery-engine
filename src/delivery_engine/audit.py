"""delivery_engine.audit - the append-only audit log and the manifest.

Charter 4.7: every stage writes an audit entry - what ran, what was
decided, why, with what hash, at what IST time. The log is JSONL and
append-only: entries are never edited or removed.

Charter 4.8: the manifest is the hash tree of the entire delivery
package - every file's SHA-256, every finding's digest, the plan digest.
A reviewer verifies the package against the manifest; if the hashes
match, the package is evidence. If they do not, it has been altered.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo

__all__ = ["AuditLog", "file_sha256", "write_manifest"]

IST: Final[ZoneInfo] = ZoneInfo("Asia/Kolkata")


class AuditLog:
    """Append-only JSONL audit log. Timestamps live HERE, not in
    artifacts - artifacts stay byte-reproducible; the log records when."""

    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def record(
        self,
        stage_id: str,
        action: str,
        outcome: str,
        rationale: str,
        sha256: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "seq": len(self._entries) + 1,
            "at_ist": datetime.now(IST).isoformat(timespec="seconds"),
            "stage": stage_id,
            "action": action,
            "outcome": outcome,
            "rationale": rationale,
        }
        if sha256 is not None:
            entry["sha256"] = sha256
        if extra:
            entry["extra"] = extra
        self._entries.append(entry)

    @property
    def entries(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._entries)

    def write(self, path: Path) -> None:
        lines = [json.dumps(e, sort_keys=True, default=str) for e in self._entries]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(
    out_dir: Path,
    finding_digests: dict[str, str],
    plan_sha256: str,
) -> Path:
    """Writes manifest.json: the hash tree of the package.

    Hashes every file in out_dir (except the manifest itself), records
    the finding digests and the plan digest. The manifest is written
    last; verifying it verifies everything.
    """
    files: dict[str, str] = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            files[str(p.relative_to(out_dir))] = file_sha256(p)
    manifest = {
        "files": files,
        "findings": dict(sorted(finding_digests.items())),
        "plan_sha256": plan_sha256,
        "note": (
            "Verify each file's SHA-256 against this manifest. Matching "
            "hashes = unaltered evidence. The audit log records when and "
            "why each entry came to exist."
        ),
    }
    path = out_dir / "manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return path
