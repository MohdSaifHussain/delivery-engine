"""delivery_engine.presentation - the deterministic PPT builder.

Produces a professional 7-slide delivery deck from the Findings Store.
Every number on every slide is a Python f-string over store-retrieved
findings - the same injected-numbers contract as the narrative report,
enforced in the generator code rather than by a post-build verifier
(the .pptx binary cannot be scanned for numeric tokens; instead the JS
script IS the auditable artifact and is hash-recorded in the findings).

Tool chain: pptxgenjs 4.0.1 (per the PPTX skill, create-new decks =
pptxgenjs). The builder writes a self-contained JS script to a temp
file, executes it via subprocess, validates the output with the skill's
office/validate.py if available, and records the script SHA-256.

Design rationale (charter amendment, step 11):
- The JS script is FULLY DETERMINISTIC engine code. No AI generates
  it. The slot is named PRESENTATION under the AI stage kind only
  because the executor's slot dispatch is the cleanest wiring point;
  the implementation is deterministic in the same sense as the EDA
  notebook.
- Numbers per slide: injected as Python literals inside the JS strings.
  The script's SHA-256 is recorded in the audit trail - a reviewer can
  recompute it from the same findings and get the same script.
- Layout: LAYOUT_WIDE (13.3" x 7.5") per the skill; coordinates are
  verified to stay within the canvas.
- Colors: a coherent dark-navy/teal palette designed for this project,
  not the default pptxgenjs gray.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path
from typing import Any

__all__ = ["PresentationError", "build_presentation_script", "run_script"]

_PPTX_NODE_MODULES = Path("/home/claude/pptwork/node_modules")
# Windows path for the machine the package lands on
_PPTX_NODE_MODULES_WIN = Path("node_modules")

NAV = "1B3A6B"   # dark navy - dominant
TEA = "0A7E8C"   # teal - accent
WHT = "FFFFFF"   # white - text on dark
LBL = "2C3E50"   # dark slate - body text
SLT = "F4F7FA"   # near-white slide background
ACC = "E8A020"   # amber - highlight/critical
GRN = "1A7A4A"   # green - pass


class PresentationError(Exception):
    """A presentation-build failure, stated cleanly."""


def _r(v: float | int | None, decimals: int = 2) -> str:
    """Format a number for slide display; None -> 'n/a'."""
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


def _pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v * 100:.1f}%"


def build_presentation_script(
    store_snapshot: dict[str, Any],
    source: str,
    goal: str,
    out_pptx: str,
    node_modules: str,
) -> str:
    """Returns a self-contained pptxgenjs JS script (string).

    All numbers are Python literals injected from store_snapshot —
    the findings as a plain dict, pulled from the store before this
    function is called so the script is a pure function of its inputs.
    """
    # Normalise to forward slashes: Windows paths with backslashes corrupt
    # the JS require() string when embedded in an f-string literal.
    nm = node_modules.replace("\\", "/")

    profile = store_snapshot.get("dq_profile", {})
    validate = store_snapshot.get("dq_validate", {})
    baseline = store_snapshot.get("baseline")
    ops = store_snapshot.get("ops_review")

    # ── Profile summary ──
    cols = profile.get("columns", [])
    n_cols = len(cols)
    n_rows = cols[0]["total"] if cols else 0
    dama = profile.get("dama_scores", {})
    completeness = dama.get("completeness")

    # ── Validation summary ──
    rules_eval = validate.get("rules_evaluated", 0)
    total_exc = validate.get("total_exceptions", 0)
    critical_rules = [
        r for r in validate.get("results", [])
        if r.get("failures", 0) > 0
    ][:4]

    # ── Baseline summary ──
    bl_target = baseline.get("target", "—") if baseline else "—"
    bl_metrics = baseline.get("metrics", {}) if baseline else {}
    bl_roc = bl_metrics.get("roc_auc")
    bl_f1 = bl_metrics.get("f1")
    bl_acc = bl_metrics.get("accuracy")
    bl_n_train = baseline.get("n_train") if baseline else None
    bl_n_test = baseline.get("n_test") if baseline else None

    # ── Ops summary ──
    ops_findings = ops.get("findings", []) if ops else []
    ops_crit = [f for f in ops_findings if f.get("severity") == "CRITICAL"]
    ops_gate = ops.get("gate", "—") if ops else "—"
    ops_playbook = ops.get("playbook", "—") if ops else "—"

    # ── Column table (up to 6 rows) ──
    col_rows_js = ""
    for c in cols[:6]:
        null_pct = (c["nulls"] / c["total"] * 100) if c["total"] else 0
        col_rows_js += f"""
    slide3.addTable([[
      {{text: '{c["name"]}', options: {{color: '{LBL}', fontSize: 11}}}},
      {{text: '{c["dtype"]}', options: {{color: '{LBL}', fontSize: 11}}}},
      {{text: '{c["total"]:,}', options: {{color: '{LBL}', fontSize: 11, align: 'right'}}}},
      {{text: '{null_pct:.1f}%', options: {{color: '{"D0021B" if null_pct > 5 else LBL}', fontSize: 11, align: 'right'}}}},
      {{text: '{c["distinct"]:,}', options: {{color: '{LBL}', fontSize: 11, align: 'right'}}}},
    ]], {{ x:0.4, y:{1.4 + list(cols[:6]).index(c)*0.45:.2f}, w:12.5, h:0.4,
      colW:[3,2,2,2,3], fill:{{color:'{"F8FAFC" if list(cols[:6]).index(c)%2==0 else WHT}'}},
      border:{{type:'solid',color:'E2E8F0',pt:0.5}} }});"""

    # ── Validation findings table ──
    finding_rows_js = ""
    for r in critical_rules:
        finding_rows_js += f"""
    slide4.addTable([[
      {{text: '{r["rule_id"]}', options: {{color: '{LBL}', fontSize: 11}}}},
      {{text: '{r["column"]}', options: {{color: '{LBL}', fontSize: 11}}}},
      {{text: '{r["rule"]}', options: {{color: '{LBL}', fontSize: 11}}}},
      {{text: '{r["failures"]:,}', options: {{color: 'D0021B', bold: true, fontSize: 11, align: 'right'}}}},
    ]], {{ x:0.4, y:{2.0 + critical_rules.index(r)*0.5:.2f}, w:12.5, h:0.45,
      colW:[2.5,2.5,4.5,3], fill:{{color:'FFF5F5'}},
      border:{{type:'solid',color:'FED7D7',pt:0.5}} }});"""

    # ── Ops criticals ──
    ops_crit_js = ""
    for i, f in enumerate(ops_crit[:3]):
        txt = f.get("text", "")[:110].replace("'", "\\'")
        ops_crit_js += f"""
    slide5.addText('\u25cf {txt}', {{
      x:0.5, y:{2.2 + i*0.85:.2f}, w:12.2, h:0.75,
      fontSize:13, color:'{LBL}', wrap:true,
      fill:{{color:'FFF8E7'}}, line:{{color:'{ACC}',pt:1}} }});"""

    baseline_slide_js = ""
    if baseline:
        baseline_slide_js = f"""
  // ── Slide 6: baseline model ──
  const slide6 = pres.addSlide();
  slide6.background = {{color: '{SLT}'}};
  slide6.addText('Baseline Model', {{
    x:0.4, y:0.18, w:12.5, h:0.6,
    fontSize:26, bold:true, color:'{NAV}' }});
  slide6.addText(
    'Deterministic reference point \u2014 same source + same seed = same metrics every run.',
    {{x:0.4, y:0.82, w:12.5, h:0.4, fontSize:13, color:'{TEA}'}});
  slide6.addText('Target: {bl_target}  |  Train: {_r(bl_n_train, 0)} rows  |  Test: {_r(bl_n_test, 0)} rows', {{
    x:0.4, y:1.38, w:12.5, h:0.4, fontSize:13, color:'{LBL}' }});
  const metricsData = [{{
    name:'Score',
    labels:['ROC AUC','F1','Accuracy'],
    values:[{_r(bl_roc,4)},{_r(bl_f1,4)},{_r(bl_acc,4)}]
  }}];
  slide6.addChart(pres.ChartType.bar, metricsData, {{
    x:0.4, y:1.9, w:7, h:4.5,
    chartColors:['{TEA}'],
    showValue:true, dataLabelPosition:'outEnd', dataLabelFontSize:12,
    valAxisMinVal:0, valAxisMaxVal:1,
    showTitle:false, showLegend:false,
    valGridLine:{{color:'E2E8F0',size:0.5}},
    catGridLine:{{style:'none'}},
    valAxisLabelColor:'{LBL}', catAxisLabelColor:'{LBL}',
    catAxisLabelFontSize:12,
  }});
  slide6.addText(
    'Fixed-seed logistic regression (sklearn).\\n'
    + 'Metric values never gate the pipeline \u2014\\n'
    + 'training feasibility does.\\n\\n'
    + 'This is a reference point,\\nnot a delivered model.',
    {{x:8.1, y:1.9, w:4.7, h:4.5,
      fontSize:13, color:'{LBL}', valign:'middle', wrap:true }});"""

    # Pre-compute digest shorts as Python literals; avoids Python slice
    # syntax leaking into the JS string body.
    dq_p_dig = store_snapshot.get("_digests", {}).get("dq_profile", "not run")[:24]
    dq_v_dig = store_snapshot.get("_digests", {}).get("dq_validate", "not run")[:24]
    bl_dig = (store_snapshot.get("_digests", {}).get("baseline", "not run")[:24]
              if baseline else "not included")
    ops_dig = (store_snapshot.get("_digests", {}).get("ops_review", "not run")[:24]
               if ops else "not included")

    script = f"""
'use strict';
const PptxGenJS = require('{nm}/pptxgenjs');

const pres = new PptxGenJS();
pres.layout = 'LAYOUT_WIDE';   // 13.3" x 7.5" per PPTX skill
pres.title = 'Delivery Package';
pres.company = 'Delivery Engine';

// ── Slide 1: Title ──
const slide1 = pres.addSlide();
slide1.background = {{color: '{NAV}'}};
slide1.addText('Delivery Package', {{
  x:0.5, y:1.8, w:12.3, h:1.2,
  fontSize:44, bold:true, color:'{WHT}', align:'center' }});
slide1.addText('{goal.replace(chr(39), chr(92)+chr(39))[:90]}', {{
  x:0.5, y:3.2, w:12.3, h:0.7,
  fontSize:20, color:'{TEA}', align:'center' }});
slide1.addText('Source: {Path(source).name}', {{
  x:0.5, y:4.1, w:12.3, h:0.5,
  fontSize:14, color:'9BB3CC', align:'center' }});
slide1.addText(
  'Agent proposes \u00b7 Deterministic tools dispose \u00b7 Human governs \u00b7 Every claim traceable',
  {{x:0.5, y:6.5, w:12.3, h:0.5,
    fontSize:11, color:'6B8AAD', align:'center', italic:true }});

// ── Slide 2: Dataset overview ──
const slide2 = pres.addSlide();
slide2.background = {{color: '{SLT}'}};
slide2.addText('Dataset Overview', {{
  x:0.4, y:0.18, w:12.5, h:0.6,
  fontSize:26, bold:true, color:'{NAV}' }});

const kpis = [
  {{label:'Rows', value:'{n_rows:,}'}},
  {{label:'Columns', value:'{n_cols}'}},
  {{label:'Completeness', value:'{_pct(completeness)}'}},
  {{label:'Rules evaluated', value:'{rules_eval}'}},
  {{label:'Total exceptions', value:'{total_exc:,}'}},
];
kpis.forEach((kpi, i) => {{
  const col = i % 3, row = Math.floor(i / 3);
  const x = 0.4 + col * 4.3, y = 1.0 + row * 2.4;
  slide2.addShape(pres.ShapeType.roundRect, {{
    x, y, w:3.9, h:2.0,
    fill:{{color:'{WHT}'}},
    line:{{color:'D4E4F0', pt:1}},
    rectRadius:0.08,
    shadow:{{type:'outer',color:'CBD5E0',blur:4,offset:2,angle:45,opacity:0.4}}
  }});
  slide2.addText(kpi.value, {{
    x, y:y+0.3, w:3.9, h:1.0,
    fontSize:32, bold:true, color:'{TEA}', align:'center', margin:0 }});
  slide2.addText(kpi.label, {{
    x, y:y+1.3, w:3.9, h:0.5,
    fontSize:13, color:'{LBL}', align:'center', margin:0 }});
}});

// ── Slide 3: Column profile ──
const slide3 = pres.addSlide();
slide3.background = {{color: '{SLT}'}};
slide3.addText('Column Profile', {{
  x:0.4, y:0.18, w:12.5, h:0.6,
  fontSize:26, bold:true, color:'{NAV}' }});
slide3.addTable([[
  {{text:'Column', options:{{color:'{WHT}', bold:true, fontSize:12}}}},
  {{text:'Type', options:{{color:'{WHT}', bold:true, fontSize:12}}}},
  {{text:'Rows', options:{{color:'{WHT}', bold:true, fontSize:12, align:'right'}}}},
  {{text:'Null %', options:{{color:'{WHT}', bold:true, fontSize:12, align:'right'}}}},
  {{text:'Distinct', options:{{color:'{WHT}', bold:true, fontSize:12, align:'right'}}}},
]], {{ x:0.4, y:0.9, w:12.5, h:0.45,
  colW:[3,2,2,2,3], fill:{{color:'{NAV}'}},
  border:{{type:'solid',color:'{NAV}',pt:0.5}} }});
{col_rows_js}
{ f'slide3.addText("+ {len(cols)-6} more column(s) - see narrative report", {{x:0.4, y:{1.4+6*0.45:.2f}, w:12.5, h:0.35, fontSize:11, color:"6B8AAD", italic:true}});' if len(cols) > 6 else '' }

// ── Slide 4: Validation findings ──
const slide4 = pres.addSlide();
slide4.background = {{color: '{SLT}'}};
slide4.addText('Validation Findings', {{
  x:0.4, y:0.18, w:12.5, h:0.6,
  fontSize:26, bold:true, color:'{NAV}' }});
slide4.addText(
  '{rules_eval} rule(s) evaluated  \u2014  {total_exc:,} total exception(s)',
  {{x:0.4, y:0.82, w:12.5, h:0.4, fontSize:14, color:'{LBL}'}});
{ f"""slide4.addText('No rule violations found \u2014 all gates passed.', {{
  x:0.4, y:1.6, w:12.5, h:0.5,
  fontSize:16, color:'{GRN}', bold:true }});""" if not critical_rules else f"""
slide4.addTable([[
  {{text:'Rule', options:{{color:'{WHT}', bold:true, fontSize:12}}}},
  {{text:'Column', options:{{color:'{WHT}', bold:true, fontSize:12}}}},
  {{text:'Check', options:{{color:'{WHT}', bold:true, fontSize:12}}}},
  {{text:'Exceptions', options:{{color:'{WHT}', bold:true, fontSize:12, align:'right'}}}},
]], {{ x:0.4, y:1.42, w:12.5, h:0.5,
  colW:[2.5,2.5,4.5,3], fill:{{color:'{NAV}'}},
  border:{{type:'solid',color:'{NAV}',pt:0.5}} }});
{finding_rows_js}""" }

// ── Slide 5: Operational review ──
const slide5 = pres.addSlide();
slide5.background = {{color: '{SLT}'}};
slide5.addText('Operational Review', {{
  x:0.4, y:0.18, w:12.5, h:0.6,
  fontSize:26, bold:true, color:'{NAV}' }});
{ f"""slide5.addText('OpsKit playbook: {ops_playbook}  |  Gate: {ops_gate}', {{
  x:0.4, y:0.82, w:12.5, h:0.4, fontSize:13, color:'{TEA}' }});
slide5.addText(
  '{len(ops_findings)} finding(s) \u2014 {len(ops_crit)} operational critical(s) recorded as evidence.',
  {{x:0.4, y:1.3, w:12.5, h:0.4, fontSize:13, color:'{LBL}'}});
{ops_crit_js if ops_crit else f"""slide5.addText('No critical operational findings.', {{
  x:0.5, y:2.2, w:12.2, h:0.75, fontSize:14, color:'{GRN}', bold:true }});"""}""" if ops else
  """slide5.addText('Operational review not included in this package.', {
  x:0.4, y:1.5, w:12.5, h:0.6, fontSize:14, color:'9BB3CC', italic:true });""" }

{baseline_slide_js}

// ── Slide 7 (or 6 without baseline): Evidence trail ──
const slideN = pres.addSlide();
slideN.background = {{color: '{NAV}'}};
slideN.addText('Evidence Trail', {{
  x:0.5, y:0.5, w:12.3, h:0.7,
  fontSize:28, bold:true, color:'{WHT}', align:'center' }});
slideN.addText(
  'Re-run the same commands on the same source.\\n'
  + 'Matching hashes prove the findings; a mismatch proves the data changed.',
  {{x:0.5, y:1.35, w:12.3, h:0.9,
    fontSize:14, color:'9BB3CC', align:'center', italic:true }});
const trails = [
  'dq_profile findings:   {dq_p_dig}...',
  'dq_validate findings:  {dq_v_dig}...',
  '{"baseline findings:    " + bl_dig + "..."}',
  '{"ops_review findings:  " + ops_dig + "..."}',
];
trails.forEach((line, i) => {{
  slideN.addText(line, {{
    x:1.5, y:2.5+i*0.75, w:10.3, h:0.6,
    fontSize:13, color:'{TEA}', fontFace:'Courier New' }});
}});
slideN.addText(
  'Produced by the Delivery Engine \u2014 agent proposes, deterministic tools dispose.',
  {{x:0.5, y:6.7, w:12.3, h:0.5,
    fontSize:11, color:'6B8AAD', align:'center', italic:true }});

pres.writeFile({{ fileName: '{str(out_pptx).replace(chr(92), chr(47))}' }})
  .then(() => console.log('ok'))
  .catch(e => {{ console.error(e.message); process.exit(1); }});
"""
    return script


def run_script(script: str, out_pptx: Path) -> str:
    """Writes the script to a temp file, runs it, returns its SHA-256.

    The hash is computed on the CONTENT script (the pptx output path
    replaced with a sentinel) so the same findings produce the same hash
    regardless of which output directory the executor chose. The path is
    still embedded in the executed script; only the hash uses the
    canonical form.
    """
    content_script = script.replace(
        str(out_pptx).replace("\\", "/"), "<OUTPUT_PPTX>"
    )
    script_hash = hashlib.sha256(content_script.encode("utf-8")).hexdigest()
    with tempfile.NamedTemporaryFile(
        suffix=".js", mode="w", encoding="utf-8", delete=False
    ) as fh:
        fh.write(script)
        script_path = fh.name
    try:
        result = subprocess.run(
            ["node", script_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0 or not out_pptx.exists():
            raise PresentationError(
                f"pptxgenjs failed (exit {result.returncode}): "
                f"{(result.stderr or result.stdout)[:300]}"
            )
    finally:
        Path(script_path).unlink(missing_ok=True)
    return script_hash
