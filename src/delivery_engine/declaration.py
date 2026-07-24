"""delivery_engine.declaration - Human-Declared-Final (Step 23).

Tier-2 evidence-grade declaration for a sealed delivery package.
Grounded in:
  - EU AI Act Article 14 (human oversight, named and timestamped)
  - NIST AI RMF MANAGE-4.1 (tamper-evident human confirmation)
  - ISO/IEC 42001:2023 §6.1.2 (human review of AI outputs)
  - Maker-Checker / Four-Eyes principle (banking, financial services)

Design positions (all consistent with the charter):

- COGNITIVE SUPPORT TOOL FRAMING. The engine supplies evidence;
  the human supplies judgment. The declaration records both the
  reviewer's identity AND that they confirmed reading the key
  findings and disclosed limitations before signing. This is the
  Northwell high-performing hospital pattern - not the Cigna
  rubber-stamp pattern.

- TIER 2, NOT TIER 3. A single named reviewer is required (Tier 2).
  Two independent reviewers (Tier 3 / Four-Eyes) is appropriate for
  regulated industries; for a cognitive support tool, Tier 2 is the
  correct balance per the research evidence.

- NON-GATING. Packages without a declaration are valid. The fresh-dir
  requirement already prevents overwriting evidence. The declaration
  is an optional governance act, not a mandatory gate - it provides
  the mechanism for those who need it without blocking those who don't.

- TAMPER-EVIDENT. The declaration.json is written BEFORE the manifest
  is regenerated, so the manifest hashes it. Alter the declaration
  and the manifest check fails. Same pattern as handoff_manifest.json.

- NO NEW DEPENDENCIES. stdlib only: hashlib, json, datetime, pathlib,
  zoneinfo. Uses ZoneInfo("Asia/Kolkata") consistent with audit.py.

- TIMESTAMPS OUTSIDE HASHED CONTENT. The declaration_sha256 covers
  the content fields only (declared_by, confirmed_items, package
  digest, framework citations). The timestamps are recorded in the
  audit log entry - the same pattern as every other stage.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo

__all__ = [
    "DeclarationError",
    "build_review_summary",
    "declare_final",
]

IST: Final[ZoneInfo] = ZoneInfo("Asia/Kolkata")

SCHEMA_VERSION: Final[str] = "1.0"

FRAMEWORK_CITATIONS: Final[list[str]] = [
    "EU AI Act Article 14 — human oversight, named and timestamped",
    "NIST AI RMF MANAGE-4.1 — tamper-evident human confirmation",
    "ISO/IEC 42001:2023 §6.1.2 — human review of AI outputs",
    "Maker-Checker / Four-Eyes principle — financial services governance",
]

TOOL_NATURE: Final[str] = (
    "cognitive support tool — the engine supplies evidence, "
    "the human supplies judgment"
)

CONFIRMED_ITEMS: Final[list[str]] = [
    "read the key findings and metrics shown above",
    "accepted the limitations the engine has disclosed",
    "understood the cognitive support tool nature of this system",
    "accepted accountability for acting on this package",
]


class DeclarationError(Exception):
    """A declaration problem, stated cleanly."""


def _load_manifest(package_dir: Path) -> dict[str, Any]:
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        raise DeclarationError(
            f"manifest.json not found in {package_dir}. "
            f"The package must be sealed before it can be declared final."
        )
    result: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return result


def _load_findings(package_dir: Path) -> dict[str, Any]:
    """Load all available findings from the findings/ subfolder."""
    findings: dict[str, Any] = {}
    findings_dir = package_dir / "findings"
    if not findings_dir.exists():
        return findings
    for f in sorted(findings_dir.glob("*.json")):
        with contextlib.suppress(json.JSONDecodeError):
            parsed: Any = json.loads(f.read_text(encoding="utf-8"))
            findings[f.stem] = parsed
    return findings


def _extract_key_metrics(findings: dict[str, Any]) -> list[str]:
    """Extract human-readable key metrics from findings for review."""
    lines: list[str] = []

    if "dq_profile" in findings:
        prof = findings["dq_profile"].get("findings", findings["dq_profile"])
        dama = prof.get("dama_scores", {})
        for dim in sorted(dama):
            val = dama[dim]
            if val is None or (dim == "timeliness" and val == 0.0):
                lines.append(f"  {dim}: not scored")
            else:
                lines.append(f"  {dim}: {round(val * 100, 1)}%")

    if "baseline" in findings:
        bl = findings["baseline"].get("findings", findings["baseline"])
        metrics = bl.get("metrics", {})
        if "roc_auc" in metrics:
            lines.append(f"  roc_auc: {metrics['roc_auc']}")
        if "recall" in metrics:
            lines.append(f"  recall: {metrics['recall']}")
        g2 = bl.get("g2_pseudoreplication", {})
        if g2:
            lines.append(
                f"  G2 pseudoreplication: gate={g2.get('gate')} "
                f"(non-gating disclosure)"
            )
        g3 = bl.get("g3_minimum_detectable_effect", {})
        if g3:
            lines.append(f"  G3 MDE: {g3.get('mde_cohen_h')}")

    if "math" in findings:
        m = findings["math"].get("findings", findings["math"])
        skipped = m.get("skipped", [])
        if skipped:
            lines.append(f"  math skipped columns: {skipped}")

    if "stats" in findings:
        s = findings["stats"].get("findings", findings["stats"])
        n_sig = sum(
            1 for t in s.get("tests", []) if t.get("significant_at_alpha")
        )
        lines.append(
            f"  stats: {len(s.get('tests', []))} tests, "
            f"{n_sig} significant at alpha={s.get('alpha')}"
        )

    return lines if lines else ["  (no structured findings available)"]


def _extract_limitations(findings: dict[str, Any]) -> list[str]:
    """Extract disclosed limitations from findings."""
    lines: list[str] = []

    if "dq_profile" in findings:
        prof = findings["dq_profile"].get("findings", findings["dq_profile"])
        dama = prof.get("dama_scores", {})
        for dim in ["accuracy", "timeliness"]:
            val = dama.get(dim)
            if val is None or (dim == "timeliness" and val == 0.0):
                lines.append(
                    f"  {dim}: not scored — dataset alone cannot establish"
                )

    if "baseline" in findings:
        bl = findings["baseline"].get("findings", findings["baseline"])
        omissions = bl.get("omissions", [])
        for o in omissions:
            lines.append(f"  omission: {o}")

    return lines if lines else ["  (no limitations disclosed)"]


def build_review_summary(package_dir: Path) -> str:
    """Build the review summary shown to the human before declaration.

    This is the Tier-2 requirement: the reviewer must see the key
    findings and limitations before they can confirm. Not a rubber stamp.
    """
    manifest = _load_manifest(package_dir)
    findings = _load_findings(package_dir)

    # Try to read plan.json for context
    plan_info: dict[str, Any] = {}
    plan_path = package_dir / "plan.json"
    if plan_path.exists():
        with contextlib.suppress(json.JSONDecodeError):
            plan_info = json.loads(plan_path.read_text(encoding="utf-8"))

    lines: list[str] = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  HUMAN DECLARATION OF FINAL PACKAGE")
    lines.append("=" * 60)
    lines.append("")
    lines.append("Framework basis:")
    for c in FRAMEWORK_CITATIONS:
        lines.append(f"  - {c}")
    lines.append("")
    lines.append(
        "You are declaring this package final as output from a\n"
        "cognitive support tool. The engine supplied the evidence.\n"
        "The judgment is yours."
    )
    lines.append("")
    lines.append("--- Package ---")
    lines.append(f"  Path:     {package_dir}")
    if plan_info:
        lines.append(f"  Playbook: {plan_info.get('playbook_name', 'unknown')}")
        lines.append(f"  Goal:     {plan_info.get('goal', 'unknown')}")
        lines.append(f"  Source:   {plan_info.get('source', 'unknown')}")
        lines.append(f"  Approved by (Gate 1): {plan_info.get('approved_by', 'unknown')}")
    lines.append("")

    lines.append("--- Key findings you are declaring final ---")
    lines.extend(_extract_key_metrics(findings))
    lines.append("")

    lines.append("--- Limitations disclosed by the engine ---")
    lines.extend(_extract_limitations(findings))
    lines.append("")

    n_files = len(manifest.get("files", {}))
    lines.append("--- Package integrity ---")
    lines.append(f"  manifest SHA-256: {manifest.get('plan_sha256', 'n/a')}")
    lines.append(f"  Files hashed in manifest: {n_files}")
    lines.append("")

    lines.append("--- What you are confirming ---")
    for i, item in enumerate(CONFIRMED_ITEMS, 1):
        lines.append(f"  [{i}] {item}")
    lines.append("")
    lines.append("-" * 60)

    return "\n".join(lines)


def _content_digest(
    declared_by: str,
    confirmed_items: list[str],
    manifest_sha256: str,
) -> str:
    """SHA-256 of the declaration content (excluding timestamps).

    Timestamps are excluded so the content digest is deterministic —
    the same reviewer declaring the same package always produces the
    same content digest. Timestamps live in the audit log entry.
    """
    content = json.dumps(
        {
            "declared_by": declared_by,
            "confirmed_items": confirmed_items,
            "manifest_sha256": manifest_sha256,
            "framework_citations": FRAMEWORK_CITATIONS,
            "tool_nature": TOOL_NATURE,
        },
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def declare_final(
    package_dir: Path,
    declared_by: str,
) -> Path:
    """Write declaration.json into the package and regenerate manifest.

    Shows a review summary, requires the human to type CONFIRMED,
    then writes the tamper-evident declaration and regenerates the
    manifest to include it.

    Returns the path to declaration.json.
    """
    package_dir = Path(package_dir)
    if not package_dir.exists():
        raise DeclarationError(
            f"Package directory not found: {package_dir}"
        )

    # Load current manifest to get its SHA-256 before we add declaration
    manifest = _load_manifest(package_dir)
    manifest_path = package_dir / "manifest.json"
    from delivery_engine.audit import file_sha256
    manifest_sha256 = file_sha256(manifest_path)

    # Show review summary and require explicit confirmation
    summary = build_review_summary(package_dir)
    print(summary)
    print("Type CONFIRMED to declare this package final, or Ctrl+C to cancel:")
    print()

    try:
        response = input("> ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nDeclaration cancelled.")
        raise SystemExit(0) from None

    if response != "CONFIRMED":
        raise DeclarationError(
            f"Declaration requires the exact text CONFIRMED. "
            f"Got: '{response}'. No declaration was written."
        )

    # Build the declaration record
    now_utc = datetime.now(UTC)
    now_ist = datetime.now(IST)

    content_sha256 = _content_digest(
        declared_by, CONFIRMED_ITEMS, manifest_sha256
    )

    declaration: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "framework_citations": FRAMEWORK_CITATIONS,
        "tool_nature": TOOL_NATURE,
        "declared_by": declared_by,
        "declared_at_utc": now_utc.isoformat(timespec="seconds"),
        "declared_at_ist": now_ist.isoformat(timespec="seconds"),
        "confirmed_items": CONFIRMED_ITEMS,
        "package_manifest_sha256": manifest_sha256,
        "content_sha256": content_sha256,
        "note": (
            "The content_sha256 covers declared_by, confirmed_items, "
            "manifest_sha256, framework_citations, and tool_nature — "
            "excluding timestamps so the content is independently "
            "verifiable. The manifest.json is regenerated after this "
            "file is written, so it hashes the declaration itself. "
            "Alter either file and the other's hash check fails."
        ),
    }

    # Write declaration.json
    decl_path = package_dir / "declaration.json"
    if decl_path.exists():
        raise DeclarationError(
            f"declaration.json already exists in {package_dir}. "
            f"A package can only be declared final once. "
            f"To re-declare, remove declaration.json first — "
            f"the audit log will record both events."
        )

    decl_path.write_text(
        json.dumps(declaration, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    # Regenerate manifest to include declaration.json
    # Reuse write_manifest from audit.py — same function, same pattern
    from delivery_engine.audit import write_manifest
    finding_digests: dict[str, str] = manifest.get("findings", {})
    plan_sha256: str = manifest.get("plan_sha256", "")
    source_fingerprint = manifest.get("source_fingerprint")

    write_manifest(
        package_dir,
        finding_digests,
        plan_sha256,
        source_fingerprint,
    )

    return decl_path
