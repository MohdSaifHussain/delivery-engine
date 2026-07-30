"""delivery_engine.store - the Findings Store and the Number Injector.

Charter 4.3: the Findings Store is the audit boundary. Every deterministic
output lands here as canonical JSON with a SHA-256 digest (the same
algorithm as analystkit.ai.findings_digest - one algorithm ecosystem-wide).

Charter 4.1: the injected-numbers rule is enforced ARCHITECTURALLY here,
not by prompt instruction. The NumberInjector is the only legal path for
a number to enter an artifact:

  - artifact builders receive an injector and call inject(value, label)
  - the injector formats the number AND records the exact emitted string
  - after building, verify_artifact_numbers() scans the artifact text and
    fails if it contains any number the injector did not emit

An artifact number without an injector record is a violation by
construction - detectable by test and at package time.
"""
from __future__ import annotations

import json
import re
from typing import Any, Final

from analystkit.ai import findings_digest

__all__ = [
    "FindingsStore",
    "NumberInjector",
    "StoreError",
    "verify_artifact_numbers",
]


class StoreError(Exception):
    """A findings-store problem, stated cleanly."""


class FindingsStore:
    """In-run store: stage_id -> (findings dict, sha256). Append-only."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[dict[str, Any], str]] = {}

    def put(self, stage_id: str, findings: dict[str, Any]) -> str:
        """Stores findings under a stage id. Returns the SHA-256 digest.

        A stage id can be stored once - findings are evidence, and
        evidence is never silently overwritten.
        """
        if stage_id in self._entries:
            raise StoreError(
                f"Findings for stage '{stage_id}' already exist. Evidence "
                f"is append-only; it is never overwritten."
            )
        digest = findings_digest(findings)
        self._entries[stage_id] = (findings, digest)
        return digest

    def get(self, stage_id: str) -> dict[str, Any]:
        if stage_id not in self._entries:
            raise StoreError(
                f"No findings for stage '{stage_id}'. Available: "
                f"{sorted(self._entries)}"
            )
        return self._entries[stage_id][0]

    def digest(self, stage_id: str) -> str:
        if stage_id not in self._entries:
            raise StoreError(f"No findings for stage '{stage_id}'.")
        return self._entries[stage_id][1]

    def digests(self) -> dict[str, str]:
        return {sid: d for sid, (_, d) in self._entries.items()}

    def all_entries(self) -> dict[str, tuple[dict[str, Any], str]]:
        """Returns a copy of all (findings, digest) pairs. Used by the
        presentation stage to snapshot the full store for script
        generation without accessing private state."""
        return dict(self._entries)

    def to_json(self, stage_id: str) -> str:
        findings, digest = self._entries[stage_id]
        return json.dumps(
            {"stage": stage_id, "findings": findings, "sha256": digest},
            indent=2, sort_keys=True, default=str,
        )


class NumberInjector:
    """The only legal path for a number to enter an artifact.

    inject() formats a value and records every numeric token it emitted.
    verify_artifact_numbers() then proves an artifact contains no numeric
    token the injector did not emit. Charter 4.1, enforced by construction.
    """

    def __init__(
        self,
        store: FindingsStore,
        known_identifiers: frozenset[str] = frozenset(),
    ) -> None:
        self._store = store
        self._emitted: set[str] = set()
        # Step 24 (Change 3): column names from the approved plan - governed
        # data, never inferred from artifact text. verify_artifact_numbers
        # uses this to stop misreading a digit-bearing identifier (e.g.
        # sensor_060) as an unprovenanced numeric claim, without loosening
        # the number regex itself (that would stop catching bare "p95").
        self.known_identifiers = known_identifiers

    def inject(self, value: float | int | None, fmt: str = "{}") -> str:
        """Formats a value from the findings store for artifact use.

        None renders as 'n/a' (a scored-nothing is displayed honestly,
        never as zero). Every numeric token in the output is recorded.
        """
        if value is None:
            return "n/a"
        text = fmt.format(value)
        for token in _NUMBER_RE.findall(text):
            self._emitted.add(token)
        return text

    def inject_percent(self, ratio: float | None) -> str:
        """A ratio 0..1 rendered as a percentage with one decimal."""
        if ratio is None:
            return "n/a"
        return self.inject(round(ratio * 100, 1), "{}") + "%"

    def inject_from_findings(self, stage_id: str, text: str) -> str:
        """Verbatim injection of a string that lives INSIDE stored findings.

        OpsKit-style findings carry numbers inside prose ('rose 140%
        (35 -> 84)'). Those numbers come from the hashed Findings Store -
        exactly what charter 4.1 demands - but inject() cannot emit them
        one by one. This method registers a whole store-sourced string:
        it first PROVES the exact text exists as a string value inside the
        stage's stored findings, then records every numeric token in it.

        Provenance is enforced by construction, not by builder
        discipline: text that is not verbatim store content raises
        StoreError, and any number a builder writes itself still fails
        verify_artifact_numbers.
        """
        findings = self._store.get(stage_id)
        if text not in _iter_strings(findings):
            raise StoreError(
                f"inject_from_findings: the text is not a verbatim string "
                f"value inside the findings of stage '{stage_id}'. Only "
                f"exact store content may be injected this way. "
                f"(Charter 4.1)"
            )
        for token in _NUMBER_RE.findall(text):
            self._emitted.add(token)
        return text

    @property
    def emitted(self) -> frozenset[str]:
        return frozenset(self._emitted)


def _iter_strings(obj: Any) -> set[str]:
    """Every string value reachable inside a findings structure."""
    out: set[str] = set()
    if isinstance(obj, str):
        out.add(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            out |= _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= _iter_strings(v)
    return out


# Numeric tokens: integers, decimals, thousands-separated. Deliberately
# broad - it is better to challenge a harmless token than miss a claim.
_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+"
)

# Tokens that are document structure, not data claims: markdown heading
# levels etc. Kept minimal and explicit.
_STRUCTURAL_TOKENS: Final[frozenset[str]] = frozenset({"1", "2", "3", "4"})


_BACKTICK_RE: Final[re.Pattern[str]] = re.compile(r"`[^`]*`")
_HEX_RE: Final[re.Pattern[str]] = re.compile(r"\b[0-9a-f]{8,64}\b")

# Step 24 (Change 3): tokens considered for the known-identifier exemption.
# Word characters only (letters, digits, underscore) - the same alphabet
# column names are drawn from - so "sensor_060" is one token, matched
# whole against the plan's known column names.
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"\w+")


def extract_claims(artifact_text: str, kind: str) -> str:
    """Extracts the CLAIMS surface of an artifact - the prose where a
    number would be a factual assertion.

    The injected-numbers rule governs claims, not references:
    - backtick spans (paths, ids, sample evidence, hashes) are references
    - hex digests are integrity metadata, not figures
    - notebook code cells are scaffolding, not assertions; only markdown
      cell prose makes claims
    """
    if kind == "ipynb":
        nb = json.loads(artifact_text)
        text = "\n".join(
            c["source"] for c in nb["cells"] if c["cell_type"] == "markdown"
        )
    elif kind == "markdown":
        text = artifact_text
    else:
        raise StoreError(f"Unknown artifact kind '{kind}' for verification.")
    text = _BACKTICK_RE.sub(" ", text)
    text = _HEX_RE.sub(" ", text)
    # "SHA-256" is a term, not a figure
    text = re.sub(r"(?i)sha-?256", " ", text)
    return text


def _mask_known_identifiers(text: str, known_identifiers: frozenset[str]) -> str:
    """Blanks whole tokens that are known column identifiers, so the
    number regex cannot read their embedded digits as a claim.

    A token is masked only when it EXACTLY matches a known identifier
    AND contains at least one non-digit character. The non-digit
    requirement closes the laundering hole where a column is literally
    named "95": such a token is all-digit, so it is never masked and a
    bare "95" elsewhere in the text still cannot hide behind it. This
    narrows the exemption to the precise, provable case (STEP24_DECISIONS
    Change 3) - it does not touch the number regex, so "p95" (not a
    column name) is still caught exactly as step 17 intended.
    """
    if not known_identifiers:
        return text

    def _mask(m: re.Match[str]) -> str:
        token = m.group(0)
        if token in known_identifiers and not token.isdigit():
            return "_" * len(token)
        return token

    return _TOKEN_RE.sub(_mask, text)


def verify_artifact_numbers(
    artifact_text: str,
    injector: NumberInjector,
    kind: str = "markdown",
    allow_structural: bool = True,
) -> None:
    """Proves the injected-numbers rule held for an artifact.

    Extracts the claims surface (extract_claims), masks whole tokens that
    exactly match a known column identifier (step 24, Change 3 - governed
    data from the approved plan, never inferred from the text), then
    scans for numeric tokens; every remaining token must have been
    emitted by the injector (or be a declared structural token). Raises
    StoreError naming violations.
    """
    claims = _mask_known_identifiers(
        extract_claims(artifact_text, kind), injector.known_identifiers
    )
    found = set(_NUMBER_RE.findall(claims))
    allowed = set(injector.emitted)
    if allow_structural:
        allowed |= _STRUCTURAL_TOKENS
    violations = found - allowed
    if violations:
        raise StoreError(
            "Injected-numbers rule violated: artifact contains numeric "
            f"token(s) {sorted(violations)} that were not emitted by the "
            "NumberInjector. Every figure must come from the Findings "
            "Store via inject(). (Charter 4.1)"
        )
