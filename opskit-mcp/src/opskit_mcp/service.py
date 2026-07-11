"""Service layer: everything the MCP tools do, as pure typed functions.

Design decisions (Step 6, approved):

1. STDOUT ISOLATION. The MCP stdio transport owns stdout for JSON-RPC; per
   the MCP specification, a stdio server must never write non-protocol
   bytes there. OpsKit's ``build_context`` prints its assumption lines to
   stdout by design. Every OpsKit call here runs under
   ``contextlib.redirect_stdout``; the captured assumption lines are
   returned as DATA in the payload (``assumptions``), because what OpsKit
   inferred about the source is audit-relevant fact, not noise.

2. NO AMBIENT CONFIG. OpsKit's CLI defaults to ``./opskit.toml`` if
   present. A server inheriting configuration from whatever directory it
   happened to start in is an ambient-authority hazard: the audit trail
   could not say which config produced which findings. Here configuration
   is explicit-only: no ``config_path`` means library defaults, full stop.
   A supplied ``config_path`` that does not exist is an error, never a
   silent fallback. The config file's SHA-256 and the resolved threshold
   values are recorded in every payload.

3. SOURCE IDENTITY BY HASH. Payloads carry the source file's SHA-256 and
   basename, never its absolute path. Hashing the bytes is stronger
   evidence than naming a location, and it keeps ``payload_sha256``
   reproducible across machines.

4. STRUCTURED REFUSAL. ``conditional_drill`` returns ``[]`` both for
   "no driver found" and "avg metric refused". The wrapper distinguishes
   them: a non-additive metric yields an explicit refusal record with the
   Simpson's-paradox rationale, so a downstream engine can log WHY there
   is no attribution instead of guessing.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
from dataclasses import replace
from pathlib import Path
from typing import Any

from opskit_mcp._vendor.opskit4 import (
    PLAYBOOKS,
    Config,
    Metric,
    OpsKitError,
    Playbook,
    Severity,
    build_context,
    conditional_drill,
    load_config,
    materialise_custom_playbooks,
    resolve_metric,
    run_playbook,
)

AVG_REFUSAL_REASON = (
    "Averages do not decompose additively across segments (mix vs rate "
    "effects — Simpson's paradox). Attributing an avg delta to a segment "
    "would be mathematically wrong, so attribution is refused. Compare "
    "segment averages directly instead."
)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_config(
    config_path: str | None,
) -> tuple[Config, dict[str, Any], dict[str, Any]]:
    """Explicit-only configuration. Returns (cfg, custom_raw, config_record)."""
    if config_path is None:
        cfg = Config()
        record: dict[str, Any] = {
            "source": "defaults",
            "file_sha256": None,
            "resolved": _resolved(cfg),
        }
        return cfg, {}, record
    path = Path(config_path)
    if not path.exists():
        raise OpsKitError(
            f"Config file not found: {path}. An explicitly supplied config "
            f"path must exist; silent fallback to defaults is refused."
        )
    cfg, custom_raw = load_config(path)
    record = {
        "source": path.name,
        "file_sha256": _file_sha256(path),
        "resolved": _resolved(cfg),
    }
    return cfg, custom_raw, record


def _resolved(cfg: Config) -> dict[str, Any]:
    return {k: getattr(cfg, k) for k in sorted(Config.__dataclass_fields__)}


def _books(custom_raw: dict[str, Any]) -> dict[str, Playbook]:
    return {**PLAYBOOKS, **materialise_custom_playbooks(custom_raw)}


def _require_source(source: str) -> Path:
    path = Path(source)
    if not path.exists():
        raise OpsKitError(f"Source not found: {path}")
    return path


def list_playbooks_payload(config_path: str | None = None) -> dict[str, Any]:
    _cfg, custom_raw, config_record = _load_config(config_path)
    books = _books(custom_raw)
    return {
        "config": config_record,
        "playbooks": [
            {
                "key": pb.key,
                "title": pb.title,
                "description": pb.description,
                "steps": [s.key for s in pb.steps],
                "origin": "builtin" if pb.key in PLAYBOOKS else "custom",
            }
            for pb in books.values()
        ],
    }


def explain_playbook_payload(
    playbook: str, config_path: str | None = None
) -> dict[str, Any]:
    _cfg, custom_raw, config_record = _load_config(config_path)
    books = _books(custom_raw)
    pb = books.get(playbook)
    if pb is None:
        raise OpsKitError(
            f"No playbook '{playbook}'. Available: {', '.join(books)}"
        )
    return {
        "config": config_record,
        "playbook": {
            "key": pb.key,
            "title": pb.title,
            "description": pb.description,
            "steps": [
                {
                    "key": s.key,
                    "question": s.question,
                    "rationale": s.rationale,
                    "requires": list(s.requires),
                }
                for s in pb.steps
            ],
        },
    }


def run_playbook_payload(
    playbook: str,
    source: str,
    table: str | None = None,
    metric: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    cfg, custom_raw, config_record = _load_config(config_path)
    books = _books(custom_raw)
    pb = books.get(playbook)
    if pb is None:
        raise OpsKitError(
            f"No playbook '{playbook}'. Available: {', '.join(books)}"
        )
    if metric is not None:
        cfg = replace(cfg, metric=metric)
        config_record = dict(config_record)
        config_record["resolved"] = _resolved(cfg)
    src = _require_source(source)
    # Seal the declared input BEFORE execution (TOCTOU discipline): the
    # recorded hash is of the file as approved for analysis; any mid-run
    # swap makes re-performance fail loudly against this seal.
    source_sha256 = _file_sha256(src)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        ctx = build_context(src, cfg, table)
        if metric is not None:
            # Eager validation: a playbook without a volume step would
            # otherwise never touch the metric, and the audit record
            # would claim an unvalidated metric produced these findings.
            resolve_metric(ctx, cfg)
        findings = run_playbook(pb, ctx, cfg)

    critical = sum(1 for f in findings if f.severity is Severity.CRITICAL)
    return {
        "config": config_record,
        "playbook": pb.key,
        "source_name": src.name,
        "source_sha256": source_sha256,
        "table": table,
        "assumptions": [
            line for line in captured.getvalue().splitlines() if line.strip()
        ],
        "findings": [
            {"schema": "opskit.finding/v1", **f.as_json()} for f in findings
        ],
        "critical_findings": critical,
        "gate": "stop" if critical else "pass",
    }


def drill_payload(
    source: str,
    table: str | None = None,
    metric: str | None = None,
    config_path: str | None = None,
) -> dict[str, Any]:
    cfg, _custom_raw, config_record = _load_config(config_path)
    if metric is not None:
        cfg = replace(cfg, metric=metric)
        config_record = dict(config_record)
        config_record["resolved"] = _resolved(cfg)
    src = _require_source(source)
    source_sha256 = _file_sha256(src)   # sealed before execution (TOCTOU)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        ctx = build_context(src, cfg, table)
        resolved: Metric = resolve_metric(ctx, cfg)
        if not resolved.additive:
            return {
                "config": config_record,
                "source_name": src.name,
                "source_sha256": source_sha256,
                "metric": resolved.label,
                "refused": True,
                "reason": AVG_REFUSAL_REASON,
                "path": [],
            }
        path = conditional_drill(ctx, cfg, resolved)

    return {
        "config": config_record,
        "source_name": src.name,
        "source_sha256": source_sha256,
        "metric": resolved.label,
        "refused": False,
        "reason": None,
        "path": [
            {
                "level": i,
                "column": lvl.column,
                "value": lvl.value,
                "current": lvl.cur,
                "previous": lvl.prev,
                "contribution": lvl.contribution,
            }
            for i, lvl in enumerate(path, 1)
        ],
    }
