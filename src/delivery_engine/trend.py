"""delivery_engine.trend - the deterministic across-runs trend report.

Step 23. Step 22 preserves the iterative cleaning lifecycle as an
ordered chain of sealed runs (run_001 .. run_NNN). This module reads
that chain and renders ONE picture of the remediation journey: how
validation exceptions shrink and data-quality scores climb from the
first messy attempt to the latest. It is the "comparison feature" the
single-run report (Step 21) made people want once they could see one
run at a time.

The discipline is identical to Step 21: every point plotted is a hashed
finding read from some run's sealed package - nothing is computed,
estimated, or decided by an AI. Critically, the report draws the VALUES
from each run and lets the reader see the movement; it never computes a
delta, a percentage improvement, or a "23% better" claim. The
improvement is VISUAL (the bars move across attempts), not an authored
number. Computing a cross-run delta would be the AI writing a figure -
exactly what the constitution forbids - so this module reads and draws,
it does not calculate.

It is a pure function of the runs it is given: the same sealed runs
produce byte-identical HTML (the generation date is display metadata in
the footer, outside the determinism contract, as in Step 21). The trend
is therefore itself re-performable evidence of the remediation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from delivery_engine.lineage import existing_runs, run_number
from delivery_engine.report import (
    _ACCENT,
    _BAR_BG,
    _CHART_W,
    _CSS,
    _GOOD,
    _GRID,
    _INK,
    _MUTED,
    _WARN,
    _esc,
    _pct,
)

__all__ = ["TrendError", "build_trend_html", "trend_from_area"]

_DAMA_ORDER: Final = (
    "completeness", "validity", "consistency", "uniqueness",
)


class TrendError(Exception):
    """A trend report could not be built, stated with the reason."""


# ── one run's numbers, read from its sealed findings ─────────────────────────


def _read_run(run_dir: Path) -> dict[str, Any] | None:
    """Read the hashed numbers a trend needs from one run's package.

    Returns None if the run has no sealed findings (an incomplete or
    stopped run is skipped, not guessed at). Every value returned is
    taken directly from the run's findings - nothing is computed.
    """
    findings = run_dir / "final" / "findings"
    prof_path = findings / "dq_profile.json"
    val_path = findings / "dq_validate.json"
    if not prof_path.exists() or not val_path.exists():
        return None
    prof = json.loads(prof_path.read_text(encoding="utf-8"))
    val = json.loads(val_path.read_text(encoding="utf-8"))
    prof_f = prof.get("findings", prof)
    val_f = val.get("findings", val)
    return {
        "run": run_dir.name,
        "number": run_number(run_dir.name),
        "dama": prof_f["dama_scores"],
        "total_exceptions": int(val_f["total_exceptions"]),
        "rules_evaluated": int(val_f["rules_evaluated"]),
        "profile_sha": str(prof.get("sha256", "")),
        "validate_sha": str(val.get("sha256", "")),
    }


# ── charts: values per run, drawn as a trend ─────────────────────────────────


def _exceptions_trend(runs: list[dict[str, Any]]) -> str:
    """Total validation exceptions per run. Bars shrinking left-to-right
    is the remediation made visible. The scale is the largest exception
    count seen, so the first messy run sets the height and later runs
    fall away from it - no delta is computed, the eye reads the drop."""
    max_exc = max((r["total_exceptions"] for r in runs), default=0)
    row_h = 34
    bar_h = 20
    rows = ""
    y = 8
    for r in runs:
        exc = r["total_exceptions"]
        frac = 0.0 if max_exc == 0 else exc / max_exc
        bar_w = round(frac * (_CHART_W - 240))
        colour = _GOOD if exc == 0 else _WARN
        vlabel = "0 exceptions" if exc == 0 else f"{exc:,} exceptions"
        ty = y + bar_h - 5
        rows += (
            f'<text x="0" y="{ty}" class="lbl">{_esc(r["run"])}</text>'
            f'<rect x="110" y="{y}" width="{_CHART_W - 240}" '
            f'height="{bar_h}" fill="{_BAR_BG}" rx="3"/>'
            f'<rect x="110" y="{y}" width="{bar_w}" height="{bar_h}" '
            f'fill="{colour}" rx="3"/>'
            f'<text x="{_CHART_W - 60}" y="{ty}" class="val">'
            f'{_esc(vlabel)}</text>'
        )
        y += row_h
    return (
        f'<svg viewBox="0 0 {_CHART_W} {y + 4}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="Validation exceptions per run" class="chart">'
        f"<title>Validation exceptions per run</title>{rows}</svg>"
    )


def _completeness_trend(runs: list[dict[str, Any]]) -> str:
    """A DAMA dimension's score per run, drawn as a climbing line of
    points. Values are read from each run; the climb is visual. A
    dimension the engine did not score in a run (None) is drawn as a
    hollow point, never as zero - the same not-scored honesty as the
    single-run report."""
    n = len(runs)
    plot_w = _CHART_W - 120
    plot_h = 150
    left = 100
    top = 10
    step = plot_w / max(1, n - 1) if n > 1 else 0

    def x_at(i: int) -> float:
        return left + (i * step if n > 1 else plot_w / 2)

    def y_at(score: float) -> float:
        # score in [0,1] -> pixel; 1.0 at top, 0.0 at bottom
        return top + (1.0 - score) * plot_h

    body = ""
    # gridlines at 0, 50, 100%
    for frac in (0.0, 0.5, 1.0):
        gy = top + (1.0 - frac) * plot_h
        body += (
            f'<line x1="{left}" y1="{gy:.1f}" x2="{left + plot_w}" '
            f'y2="{gy:.1f}" stroke="{_GRID}" stroke-width="1"/>'
            f'<text x="{left - 8}" y="{gy + 4:.1f}" class="axis" '
            f'text-anchor="end">{_pct(frac)}</text>'
        )
    # one line per dama dimension
    palette = {
        "completeness": _ACCENT, "validity": _GOOD,
        "consistency": _WARN, "uniqueness": _MUTED,
    }
    for dim in _DAMA_ORDER:
        pts: list[tuple[float, float]] = []
        for i, r in enumerate(runs):
            score = r["dama"].get(dim)
            if score is None:
                continue
            pts.append((x_at(i), y_at(float(score))))
        if not pts:
            continue
        colour = palette.get(dim, _INK)
        if len(pts) > 1:
            path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
            body += (
                f'<path d="{path}" fill="none" stroke="{colour}" '
                f'stroke-width="2"/>'
            )
        for x, y in pts:
            body += (
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" '
                f'fill="{colour}"/>'
            )
        # dimension label at the last point
        lx, ly = pts[-1]
        body += (
            f'<text x="{lx + 8:.1f}" y="{ly + 4:.1f}" class="axis" '
            f'fill="{colour}">{_esc(dim)}</text>'
        )
    # run labels along the bottom
    for i, r in enumerate(runs):
        bx = x_at(i)
        body += (
            f'<text x="{bx:.1f}" y="{top + plot_h + 20:.1f}" '
            f'class="axis" text-anchor="middle">{_esc(r["run"])}</text>'
        )
    height = top + plot_h + 34
    return (
        f'<svg viewBox="0 0 {_CHART_W} {height:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="Data quality scores per run" class="chart">'
        f"<title>Data quality scores across runs</title>{body}</svg>"
    )


def _run_table(runs: list[dict[str, Any]]) -> str:
    """The exact per-run numbers behind the charts, each row carrying
    the run's findings hashes so any point can be traced to its run."""
    body = ""
    for r in runs:
        comp = r["dama"].get("completeness")
        comp_s = _pct(float(comp)) if comp is not None else "n/a"
        body += (
            "<tr>"
            f"<td>{_esc(r['run'])}</td>"
            f"<td class='num'>{r['rules_evaluated']}</td>"
            f"<td class='num'>{r['total_exceptions']:,}</td>"
            f"<td class='num'>{comp_s}</td>"
            f"<td><code>{_esc(r['validate_sha'][:12])}</code></td>"
            "</tr>"
        )
    return (
        "<table><thead><tr>"
        "<th>Run</th><th>Rules</th><th>Exceptions</th>"
        "<th>Completeness</th><th>Validate digest</th>"
        "</tr></thead><tbody>" + body + "</tbody></table>"
    )


# ── page assembly ────────────────────────────────────────────────────────────


def build_trend_html(
    runs: list[dict[str, Any]],
    area_label: str,
    generated_date: str = "",
) -> str:
    """Render the across-runs trend report from a list of per-run
    findings dicts (as produced by _read_run), in run order.

    A pure function: the same runs produce byte-identical output. Every
    number shown is read from a run's findings; nothing is computed -
    no deltas, no improvement percentages. The reader sees the values
    move; the report never authors the movement as a figure.
    """
    if not runs:
        raise TrendError(
            "No completed runs with sealed findings were found. The "
            "trend report needs at least one run_NNN with dq_profile "
            "and dq_validate findings."
        )
    latest = runs[-1]
    latest_exc = latest["total_exceptions"]
    n = len(runs)

    single = n == 1
    lede = (
        "This is the remediation journey for the dataset below: each "
        "point is read directly from a sealed run's hashed findings. "
        "The values move as the data was cleaned across attempts - the "
        "report shows the movement, it does not compute it."
    )
    if single:
        lede = (
            "One run has been recorded for the dataset below. The trend "
            "will take shape as further runs are sealed; each point is "
            "read directly from a run's hashed findings."
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Remediation trend - {_esc(area_label)}</title>
<style>{_CSS}
.chart .axis {{ font: 500 12px sans-serif; fill: {_MUTED}; }}
</style>
</head>
<body>
<main class="wrap">
<header>
<h1>Remediation trend</h1>
<p class="sub">Dataset: {_esc(area_label)} &nbsp;·&nbsp; {n} run(s) sealed</p>
</header>

<p class="lede">{lede}</p>

<section>
<h2>Validation exceptions per run</h2>
<p class="note">Total exceptions recorded in each run. Bars falling
away from the first attempt are the cleaning made visible; the latest
run recorded {latest_exc:,}.</p>
{_exceptions_trend(runs)}
</section>

<section>
<h2>Data quality across runs</h2>
<p class="note">Each DAMA dimension's score per run. A dimension the
engine did not score in a run is omitted for that run, never drawn as
zero.</p>
{_completeness_trend(runs)}
</section>

<section>
<h2>The runs</h2>
<p class="note">The exact per-run values behind the charts. Each row
carries the run's validation-findings digest, so any point traces to
its sealed run.</p>
{_run_table(runs)}
</section>

<footer>
{f'<p>Report generated: {_esc(generated_date)}</p>' if generated_date else ''}
<p>Provenance. Each point is a hashed finding from a sealed run under
this dataset's output area; recompute any run's findings digest and
compare. No cross-run figure was computed - the report reads and draws
the values, the reader reads the movement.</p>
<p class="sig">Rendered deterministically by the Delivery Engine from
the sealed run lineage. The runs supply the evidence; the trend simply
places them in order.</p>
</footer>
</main>
</body>
</html>
"""


def trend_from_area(area_dir: str) -> Path:
    """Read a dataset's run lineage and write trend.html into the area.

    Reads run_001 .. run_NNN under the area, pulls each run's hashed
    findings, and renders the trend. Incomplete runs (no sealed
    findings) are skipped, not guessed at. Returns the path written.
    """
    area = Path(area_dir)
    if not area.is_dir():
        raise TrendError(f"Not a directory: {area_dir}")
    run_dirs = existing_runs(area)
    if not run_dirs:
        raise TrendError(
            f"No run_NNN folders under {area_dir}. Run the engine with "
            f"--lineage first to build a run history."
        )
    runs = [r for r in (_read_run(d) for d in run_dirs) if r is not None]
    if not runs:
        raise TrendError(
            f"Found {len(run_dirs)} run folder(s) under {area_dir} but "
            f"none had sealed findings to chart."
        )
    from datetime import date

    generated = date.today().strftime("%d %B %Y")
    doc_html = build_trend_html(runs, area.name, generated)
    out = area / "trend.html"
    out.write_text(doc_html, encoding="utf-8")
    return out
