"""Step 25 tests - generator schema-currency: surface the step-24 keys.

STEP25_DECISIONS.md is the spec (and its 2026-07-31 correction note).
The generator now emits three FIXED, COMMENTED suggestion lines inside a
drafted model stage - metric_ci always, split/n_splits only when the
profile classifies a timestamp_column. Comments are invisible to
tomllib, so a draft still loads and means exactly what a pre-step-25
draft meant; the human uncommenting a line is the approval act.

This file is also, per the Phase 0 correction, the FIRST content
coverage the model-stage branch of `_emit_toml` has ever had: no call
to `compile_playbook` in tests/test_step19.py ever passed "model" in
include_stages (grepped exhaustively - every call uses ["math"],
["stats"], or ["math", "stats"]). There was consequently no existing
byte-pinning test to update for this step; test_step25 closes that
latent gap as a side effect of adding the comment lines.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from analystkit_mcp.tools import tool_profile

from delivery_engine.generator import compile_playbook
from delivery_engine.playbook import load_playbook

METRIC_CI_LINE = (
    "# metric_ci = true          # Wilson 95% CIs on recall/precision "
    "(statsmodels/NIST)"
)
SPLIT_LINE = (
    '# split = "walk_forward"    # time-ordered evaluation '
    "(scikit-learn TimeSeriesSplit)"
)
N_SPLITS_LINE = (
    '# n_splits = 5              # legal only with split = "walk_forward"'
)


def _csv(path: Path, header: list[str], rows: list[list[Any]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def _profile(src: Path) -> dict[str, Any]:
    return json.loads(tool_profile(str(src), None))["findings"]


def _pbdir(tmp_path: Path) -> Path:
    d = tmp_path / "playbooks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _with_timestamp_csv(path: Path, rows: int = 160) -> Path:
    """record_id (id), converted (binary target), signup_date
    (timestamp_column - distinct calendar dates, well under the
    id-ratio threshold so it is NOT also an id column)."""
    start = datetime(2024, 1, 1)
    out = []
    for i in range(rows):
        day = (start + timedelta(days=i % 40)).strftime("%Y-%m-%d")
        out.append([f"R-{i:05d}", "yes" if i % 3 == 0 else "no", day])
    return _csv(path, ["record_id", "converted", "signup_date"], out)


def _without_timestamp_csv(path: Path, rows: int = 160) -> Path:
    """record_id (id), converted (binary target), tier (categorical) -
    no date/timestamp-typed column anywhere."""
    out = []
    for i in range(rows):
        out.append([
            f"R-{i:05d}", "yes" if i % 3 == 0 else "no",
            ("gold", "silver", "bronze")[i % 3],
        ])
    return _csv(path, ["record_id", "converted", "tier"], out)


def _timestamp_also_id_csv(path: Path, rows: int = 200) -> Path:
    """event_time is BOTH timestamp_column (date-typed) AND id_column
    (>=99.9% distinct: ID_DISTINCT_RATIO, planner.py) - every row gets
    a unique second-precision timestamp."""
    start = datetime(2024, 1, 1, 0, 0, 0)
    out = []
    for i in range(rows):
        ts = (start + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
        out.append([ts, "yes" if i % 3 == 0 else "no"])
    return _csv(path, ["event_time", "converted"], out)


class TestModelStageCommentBlock:
    def test_with_timestamp_column_has_all_three_comment_lines(
        self, tmp_path: Path
    ) -> None:
        src = _with_timestamp_csv(tmp_path / "d.csv")
        gp = compile_playbook(
            str(src), "goal", "with_ts", _pbdir(tmp_path), _profile(src),
            ["model"],
        )
        text = gp.playbook_path.read_text(encoding="utf-8")
        assert METRIC_CI_LINE in text
        assert SPLIT_LINE in text
        assert N_SPLITS_LINE in text

    def test_without_timestamp_column_has_only_metric_ci(
        self, tmp_path: Path
    ) -> None:
        src = _without_timestamp_csv(tmp_path / "d.csv")
        gp = compile_playbook(
            str(src), "goal", "no_ts", _pbdir(tmp_path), _profile(src),
            ["model"],
        )
        text = gp.playbook_path.read_text(encoding="utf-8")
        assert METRIC_CI_LINE in text
        assert SPLIT_LINE not in text
        assert N_SPLITS_LINE not in text

    def test_drafts_load_and_are_semantically_identical_to_pre_step25(
        self, tmp_path: Path
    ) -> None:
        """The comments are invisible to tomllib - V6 strict parsing
        survives them because they are not keys at all. First content
        coverage of the model-stage branch: no prior test ever loaded a
        generated draft whose stage list contains kind = "model"."""
        src = _with_timestamp_csv(tmp_path / "d.csv")
        gp = compile_playbook(
            str(src), "goal", "loads_fine", _pbdir(tmp_path), _profile(src),
            ["model"],
        )
        pb = load_playbook(gp.playbook_path)  # must not raise (V1-V15)
        kinds = [s.kind.value for s in pb.stages]
        assert kinds.count("model") == 1  # first-ever generated & loaded
        baseline = next(s for s in pb.stages if s.kind.value == "model")
        # Defaults exactly as if the comment lines were never written -
        # a commented key is invisible, not a silently-activated one.
        assert baseline.metric_ci is False
        assert baseline.split == "random"
        assert baseline.n_splits == 5

    def test_deterministic_byte_identical_with_model_stage(
        self, tmp_path: Path
    ) -> None:
        src = _with_timestamp_csv(tmp_path / "d.csv")
        prof = _profile(src)
        g1 = compile_playbook(
            str(src), "goal", "det_check", _pbdir(tmp_path / "a"), prof,
            ["model"],
        )
        g2 = compile_playbook(
            str(src), "goal", "det_check", _pbdir(tmp_path / "b"), prof,
            ["model"],
        )
        assert (g1.playbook_path.read_bytes()
                == g2.playbook_path.read_bytes())


class TestLoopholeHunt:
    def test_timestamp_column_also_id_column_still_suggests_split(
        self, tmp_path: Path
    ) -> None:
        """has_id and has_timestamp are independent any() checks over
        every column's kinds - neither excludes a column the other
        already claimed. A column that is BOTH (>=99.9% distinct AND
        date-typed) must not suppress the split/n_splits suggestion."""
        src = _timestamp_also_id_csv(tmp_path / "d.csv")
        prof = _profile(src)
        from delivery_engine.planner import ColumnKind, classify_columns

        kinds = classify_columns(prof)
        assert ColumnKind.ID_COLUMN in kinds["event_time"]
        assert ColumnKind.TIMESTAMP_COLUMN in kinds["event_time"]

        gp = compile_playbook(
            str(src), "goal", "ts_also_id", _pbdir(tmp_path), prof,
            ["model"],
        )
        text = gp.playbook_path.read_text(encoding="utf-8")
        assert SPLIT_LINE in text
        assert N_SPLITS_LINE in text
        pb = load_playbook(gp.playbook_path)  # still constitution-valid
        assert "id_column" in pb.requirements.required_kinds

    def test_hostile_column_names_cannot_break_out_of_comment_context(
        self, tmp_path: Path
    ) -> None:
        """The three suggestion lines are fixed strings with zero
        interpolation of column names, goal text, or any other
        user-controlled data - structurally unreachable by a hostile
        column name. Proven, not assumed: a column name containing a
        TOML comment terminator shape, a bracket pair, and a quote
        still produces byte-identical suggestion lines and a loadable
        draft."""
        hostile = 'a"] # evil'
        rows = [[f"{i}", "yes" if i % 3 == 0 else "no",
                 f"2024-01-{(i % 28) + 1:02d}"]
                for i in range(160)]
        src = _csv(tmp_path / "d.csv", [hostile, "converted", "signup_date"],
                   rows)
        prof = _profile(src)
        gp = compile_playbook(
            str(src), "goal", "hostile_col", _pbdir(tmp_path), prof,
            ["model"],
        )
        text = gp.playbook_path.read_text(encoding="utf-8")
        assert METRIC_CI_LINE in text
        assert SPLIT_LINE in text
        assert N_SPLITS_LINE in text
        load_playbook(gp.playbook_path)  # still constitution-valid
