"""declare_final.py - CLI entry point for Human-Declared-Final.

Separate from run_project.py by design: declaration is a deliberate
governance act that happens AFTER the package is sealed, not during
the run. Keeping it separate prevents accidental auto-declaration in
scripted runs and makes the human intent explicit.

Usage:
    python declare_final.py --package examples/churn_analysis/output/final \
        --declarer "Sarah Ahmed, Head of Analytics"

Or with interactive prompt (omit --declarer):
    python declare_final.py --package examples/churn_analysis/output/final
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from delivery_engine.declaration import DeclarationError, declare_final


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(
        description=(
            "Declare a sealed Delivery Engine package final. "
            "Shows key findings and limitations, requires explicit "
            "CONFIRMED input, then writes a tamper-evident "
            "declaration.json and regenerates the manifest. "
            "\n\nFramework basis: EU AI Act Art.14, "
            "NIST AI RMF MANAGE-4.1, ISO/IEC 42001 §6.1.2, "
            "Maker-Checker / Four-Eyes principle."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--package",
        required=True,
        help="path to the sealed package directory (contains manifest.json)",
    )
    ap.add_argument(
        "--declarer",
        help="your name and role — recorded in the tamper-evident "
             "declaration (e.g. 'Sarah Ahmed, Head of Analytics'). "
             "If omitted you will be prompted.",
    )
    args = ap.parse_args(argv)

    package_dir = Path(args.package)

    declarer = args.declarer
    if not declarer:
        print(f"Declaring package: {package_dir}")
        declarer = input("Your name and role: ").strip()
        if not declarer:
            raise SystemExit("Required: your name and role.")

    try:
        decl_path = declare_final(package_dir, declarer)
    except DeclarationError as exc:
        print(f"\nDECLARATION ERROR: {exc}")
        raise SystemExit(1) from exc

    print()
    print("=" * 60)
    print("  DECLARATION RECORDED")
    print("=" * 60)
    print(f"  declaration.json: {decl_path}")
    print(f"  manifest.json regenerated to include declaration hash")
    print()
    print("  This package is now declared final by:")
    print(f"  {declarer}")
    print()
    print("  The content_sha256 in declaration.json can be independently")
    print("  verified. The manifest now hashes declaration.json — alter")
    print("  either file and the other's hash check fails.")
    print()
    return decl_path


if __name__ == "__main__":
    main(sys.argv[1:])
