"""Findings envelope: the audit-boundary discipline applied to OpsKit output.

Every tool response is an envelope. The payload is serialised as canonical
JSON (sorted keys, minimal separators, UTF-8) and SHA-256 hashed; the hash
covers ONLY deterministic content, so the same source + same config always
reproduces the same ``payload_sha256``. Run metadata that legitimately varies
(the IST timestamp) lives outside the hashed payload.

Same findings, same hash, re-performable evidence — the pattern proven in
AnalystKit v2.0 and analystkit-mcp, applied here unchanged.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Final
from zoneinfo import ZoneInfo

from opskit_mcp._vendor import OPSKIT_VERSION, VENDORED_OPSKIT_SHA256

IST: Final[ZoneInfo] = ZoneInfo("Asia/Kolkata")

ENVELOPE_SCHEMA: Final[str] = "opskit.envelope/v1"


def canonical_json(payload: dict[str, Any]) -> str:
    """Canonical serialisation: sorted keys, no whitespace, UTF-8 preserved.

    ``sort_keys=True`` plus fixed separators means semantically identical
    payloads always serialise to identical bytes — the precondition for
    hash-based re-performance.
    """
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def sha256_of(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def wrap(tool: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Wraps a deterministic payload in the versioned, hashed envelope."""
    return {
        "schema": ENVELOPE_SCHEMA,
        "tool": tool,
        "opskit_version": OPSKIT_VERSION,
        "vendored_opskit_sha256": VENDORED_OPSKIT_SHA256,
        "generated_at": datetime.now(IST).isoformat(timespec="seconds"),
        "payload": payload,
        "payload_sha256": sha256_of(payload),
    }
