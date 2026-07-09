"""analystkit_mcp.findings — the canonical findings envelope.

Every tool in this server returns its results wrapped in this envelope:
canonical JSON (sort_keys) with a SHA-256 digest of the payload. This is
the Findings Store format of the Delivery Engine charter (section 4.3),
born here: same findings, same hash, re-performable evidence.

The digest algorithm is identical to analystkit.ai.findings_digest —
one algorithm across the whole ecosystem, so a finding hashed by the
MCP layer verifies against a finding hashed by the toolkit.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from analystkit.ai import findings_digest

IST = ZoneInfo("Asia/Kolkata")

__all__ = ["envelope"]


def envelope(tool: str, source: str, payload: dict[str, Any]) -> str:
    """Wraps a tool result in the canonical findings envelope.

    Returns a JSON string:
    {
      "tool":       which tool produced this,
      "source":     what was analysed,
      "run_at_ist": IST timestamp of the run,
      "findings":   the payload (all computed facts live here),
      "sha256":     digest of the findings payload ONLY — timestamp and
                    metadata are outside the hash, so the same data always
                    produces the same digest regardless of when it ran.
    }
    """
    digest = findings_digest(payload)
    body = {
        "tool": tool,
        "source": source,
        "run_at_ist": datetime.now(IST).isoformat(timespec="seconds"),
        "findings": payload,
        "sha256": digest,
    }
    return json.dumps(body, indent=2, sort_keys=True, default=str)
