"""Step 24 tests — model-stage evidence honesty.

STEP24_DECISIONS.md is the spec. Three changes, each opt-in except the
bug fix (Change 3, which has no schema key and is a correctness fix for
every dataset with digit-bearing column names):

- Change 3 (this phase): identifier-aware injected-numbers scanning -
  verify_artifact_numbers must not misread a digit-bearing column name
  (e.g. sensor_060) as an unprovenanced numeric claim, while still
  catching a bare literal like "p95" and a fabricated bare percentage.
- Change 1 (planned): metric confidence intervals for the model stage
  (metric_ci, opt-in).
- Change 2 (planned): evaluation-split honesty (split / n_splits, opt-in).

Planted-answer discipline throughout (CLAUDE.md §7): fixtures contain
known issues, tests verify exactly those are found.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
from analystkit_mcp.tools import tool_profile

from delivery_engine import approve_plan, load_playbook, make_plan, run
from delivery_engine.store import (
    FindingsStore,
    NumberInjector,
    StoreError,
    verify_artifact_numbers,
)

PLAYBOOKS = Path(__file__).parent.parent / "playbooks"
SEGMENT = PLAYBOOKS / "segment_comparison.toml"


def _csv(path: Path, header: list[str], rows: list[list[Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


# ── Change 3: identifier-aware injected-numbers scanning (unit level) ───────


class TestIdentifierAwareScanningUnit:
    """Direct tests of the masking rule in store.py, isolated from the
    executor/pipeline machinery."""

    def test_known_digit_bearing_identifier_does_not_raise(self) -> None:
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        text = "Column sensor_060 failed 17 validation rules."
        # sensor_060 is masked (known, non-digit-only); the bare "17" is
        # still unprovenanced and must still raise.
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers(text, injector)

    def test_known_digit_bearing_identifier_alone_does_not_raise(self) -> None:
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        text = "Column sensor_060 was profiled with no other claims."
        verify_artifact_numbers(text, injector)  # must not raise

    def test_p95_still_raises(self) -> None:
        """The reason the allowlist design was chosen over a regex
        loosening (STEP24_DECISIONS §5, test 10): a bare 'p95' that is
        NOT a known column name must still be caught, exactly as step
        17's amendment celebrates."""
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        text = "Latency reached p95 during the window."
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers(text, injector)

    def test_bare_fabricated_percentage_still_raises(self) -> None:
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        text = "Churn rate was 42.7% this quarter."
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers(text, injector)

    def test_column_named_95_cannot_launder_a_bare_95(self) -> None:
        """A column literally named '95' is an adversarial known
        identifier that is ALL digits. The non-digit requirement means
        it is never masked, so it cannot become a laundering channel
        for an arbitrary bare figure elsewhere in the text."""
        store = FindingsStore()
        injector = NumberInjector(store, known_identifiers=frozenset({"95"}))
        text = "The rate hit 95 last week."
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers(text, injector)

    def test_no_known_identifiers_is_unchanged_behaviour(self) -> None:
        """Default known_identifiers is empty - byte-identical scanning
        behaviour to before step 24 for any caller that does not opt in."""
        store = FindingsStore()
        injector = NumberInjector(store)
        assert injector.known_identifiers == frozenset()
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers("sensor_060 misbehaved.", injector)

    def test_partial_token_match_is_not_masked(self) -> None:
        """The identifier must match the WHOLE token, not a substring -
        'sensor_060x' is a different token and is not exempted."""
        store = FindingsStore()
        injector = NumberInjector(
            store, known_identifiers=frozenset({"sensor_060"})
        )
        with pytest.raises(StoreError, match="Injected-numbers"):
            verify_artifact_numbers("Column sensor_060x failed.", injector)


# ── Change 3: end-to-end through the executor (the real crash site) ─────────


def _digit_named_column_csv(path: Path, rows: int = 200) -> Path:
    """customer_id, converted, segment, sensor_060 - the last column's
    name is exactly the shape (letters + underscore + digits) that
    crashed verify_artifact_numbers before this step: 'sensor_060'
    appears bare (no backticks) in the exception-listing line of
    build_narrative_report when a validate rule against it fails."""
    out = []
    for i in range(rows):
        seg = "a" if i % 2 == 0 else "b"
        threshold = 8 if seg == "a" else 1
        conv = "yes" if i % 10 < threshold else "no"
        sensor = "" if i % 20 == 0 else f"{100.0 + i}"  # planted nulls
        out.append([f"C-{i:05d}", conv, seg, sensor])
    return _csv(
        path, ["customer_id", "converted", "segment", "sensor_060"], out
    )


def _approved_plan_for_digit_csv(src: Path):  # type: ignore[no-untyped-def]
    envelope = json.loads(tool_profile(str(src), None))
    plan = make_plan(
        "segment comparison with statistical significance for the growth team",
        str(src),
        envelope["findings"],
        PLAYBOOKS,
    )
    return approve_plan(plan, "Saif")


class TestIdentifierAwareScanningEndToEnd:
    def test_digit_bearing_column_with_validate_failures_seals(
        self, tmp_path: Path
    ) -> None:
        src = _digit_named_column_csv(tmp_path / "sensors.csv")
        plan = _approved_plan_for_digit_csv(src)
        out = tmp_path / "pkg"
        rules = [{"column": "sensor_060", "rule": "not_null"}]
        approvals: dict[str, Any] = {"plan_approval": "Saif"}

        # Before step 24 this raised StoreError from inside the
        # narrative_report stage (the digits in "sensor_060" read as an
        # unprovenanced numeric claim) and the package never sealed.
        run(plan, load_playbook(SEGMENT), rules, out, approvals=approvals)

        assert (out / "manifest.json").exists()
        assert (out / "audit_log.jsonl").exists()
        narrative = (out / "narrative_report.md").read_text("utf-8")
        assert "sensor_060" in narrative

        validate = json.loads(
            (out / "findings" / "dq_validate.json").read_text("utf-8")
        )["findings"]
        assert validate["total_exceptions"] > 0  # the planted nulls were found
