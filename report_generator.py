"""
report_generator.py
-------------------
Step 6: Generate a full monthly presales report as a .docx file,
matching the structure of "WorkDrive Presales Report - April 2026.docx".

Sections produced:
  1. Title + Executive Summary
  2. Conversion Performance  (table + LLM observation)
  3. Repeat Engagement       (table + observation)
  4. Deal Lost Analysis      (categorised table + observations)
  5. Case Breakdown          (new vs repeat vs existing)
  6. Region-Wise Performance (table + observation)
  7. Deal Source Analysis    (table + observation)
  8. Requests Handled        (emails / demos / calls)
  9. Feature Demand Analysis (feature requests tables)
 10. Feature Trend Observations

Usage (CLI):
    python report_generator.py April
    python report_generator.py March --out "/path/to/report.docx"

Usage (import):
    from report_generator import generate_report
    path = generate_report("April")
"""

import os, sys, re, json, textwrap, subprocess, tempfile, shutil, base64
import pandas as pd
import requests
from pathlib import Path
from typing import Optional

BASE_DIR   = Path("/Users/sakthi-3766/Claude/Projects/Local SLM")
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL  = "llama3.1:8b"

sys.path.insert(0, str(BASE_DIR))
from data_ingestion import load_data

# ── Lazy data loader (cached after first call) ───────────────────────────────

_cache = {}

def _get_data():
    if not _cache:
        df, _, feat_df, noshow_df = load_data(str(BASE_DIR / "WD Presales Demo Stats 2026.xlsx"))
        _cache["df"]         = df
        _cache["feature_df"] = feat_df
        _cache["noshow_df"]  = noshow_df
    return _cache["df"], _cache["feature_df"], _cache["noshow_df"]


# ── LLM helper ───────────────────────────────────────────────────────────────

def _llm(prompt: str, max_tokens: int = 300) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False,
                  "temperature": 0.3, "options": {"num_predict": max_tokens}},
            timeout=120,
        )
        return r.json()["response"].strip()
    except Exception as e:
        return f"[LLM unavailable: {e}]"


def _observe(context: str, instruction: str) -> str:
    """Ask the LLM for a 3-sentence observation given context."""
    prompt = textwrap.dedent(f"""
        You are a presales analytics assistant writing a monthly report.
        Write exactly 3–4 concise sentences as an observation paragraph.
        Use specific numbers from the context. Do not use bullet points.

        Context:
        {context}

        Instruction: {instruction}
    """).strip()
    return _llm(prompt, max_tokens=250)


# ── Stats functions ──────────────────────────────────────────────────────────

def _month_df(month: str) -> pd.DataFrame:
    df, _, _ = _get_data()
    return df[df["month"] == month].copy()


def conversion_stats(mdf: pd.DataFrame) -> dict:
    total        = len(mdf)
    new_pros     = len(mdf[mdf["Engagement Type"] == "New Prospect"])
    already_eng  = len(mdf[mdf["Engagement Type"] == "Already Engaged Px"])
    won          = len(mdf[mdf["Status"] == "Deal Won"])
    conv_rate    = round(won / new_pros * 100, 2) if new_pros else 0
    in_prog      = len(mdf[mdf["Status"] == "In Progress"])
    return {
        "total_demos"       : total,
        "new_prospects"     : new_pros,
        "already_engaged"   : already_eng,
        "deal_won"          : won,
        "conversion_rate"   : conv_rate,
        "in_progress"       : in_prog,
    }


def repeat_engagement_stats(mdf: pd.DataFrame) -> dict:
    rep = mdf[mdf["Engagement Type"] == "Already Engaged Px"]
    return {
        "count"       : len(rep),
        "won"         : len(rep[rep["Status"] == "Deal Won"]),
        "lost"        : len(rep[rep["Status"] == "Deal Lost"]),
        "in_progress" : len(rep[rep["Status"] == "In Progress"]),
    }


def deal_lost_stats(mdf: pd.DataFrame) -> dict:
    lost = mdf[mdf["Status"] == "Deal Lost"]
    total_lost = len(lost)

    # Categorise by follow-up stage as a proxy for loss reason
    categories = {
        "No response after multiple follow-ups" : lost[lost["Follow up stages"].str.contains("follow up 3|Do not follow", case=False, na=False)],
        "Delayed decision / follow-up later"    : lost[lost["Follow up stages"].str.contains("follow up 1|follow up 2", case=False, na=False)],
        "No scope for WorkDrive"                : mdf[mdf["Status"] == "No Scope for WD"],
    }
    rows = []
    for label, sub in categories.items():
        cnt = len(sub)
        pct = round(cnt / total_lost * 100, 1) if total_lost else 0
        rows.append({"Loss category": label, "Count": cnt, "% of total lost": f"{pct}%"})

    loss_rate = round(total_lost / len(mdf) * 100, 1) if len(mdf) else 0
    return {"rows": rows, "total_lost": total_lost, "loss_rate": loss_rate}


def case_breakdown(mdf: pd.DataFrame) -> list:
    return [
        {"Category": "New Prospects",      "Count": len(mdf[mdf["Engagement Type"] == "New Prospect"])},
        {"Category": "Repeat Engagements", "Count": len(mdf[mdf["Engagement Type"] == "Already Engaged Px"])},
        {"Category": "Free Org",           "Count": len(mdf[mdf["Status"] == "Free user"])},
        {"Category": "Existing Org",       "Count": len(mdf[mdf["Status"] == "Existing customer"])},
    ]


def region_stats(mdf: pd.DataFrame) -> list:
    regions = mdf["Region"].dropna().unique()
    rows = []
    for r in sorted(regions):
        sub  = mdf[mdf["Region"] == r]
        rows.append({
            "Region"     : r,
            "Total Deals": len(sub),
            "Deal Won"   : len(sub[sub["Status"] == "Deal Won"]),
            "Deal Lost"  : len(sub[sub["Status"] == "Deal Lost"]),
        })
    return sorted(rows, key=lambda x: x["Total Deals"], reverse=True)


def source_stats(mdf: pd.DataFrame) -> list:
    counts = mdf["Source"].value_counts()
    return [{"Source": k, "Count": v} for k, v in counts.items()]


def feature_stats(month: str) -> list:
    """Return feature requests relevant to the given month."""
    _, feature_df, _ = _get_data()
    if feature_df.empty:
        return []
    feats = feature_df.copy()
    feats.columns = [c.strip() for c in feats.columns]
    # Return top features (no month column in feature_df so return all)
    return feats[["Feature name", "Description", "Ticket Ref", "Sprintz link"]].dropna(
        subset=["Feature name"]
    ).head(12).to_dict("records")


# ── JavaScript report builder ────────────────────────────────────────────────

def _json_safe(s) -> str:
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")


def _image_run(png_path: str, width_inches: float = 5.0, height_inches: float = 3.5) -> str:
    """Return a docx-js ImageRun expression embedding the PNG as base64."""
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    # EMU = English Metric Units: 914400 per inch
    cx = int(width_inches  * 914400)
    cy = int(height_inches * 914400)
    return (
        f"new Paragraph({{ alignment: AlignmentType.CENTER, children: [new ImageRun({{ "
        f"type: 'png', "
        f"data: Buffer.from('{b64}', 'base64'), "
        f"transformation: {{ width: {int(width_inches*96)}, height: {int(height_inches*96)} }}, "
        f"altText: {{ title: 'Chart', description: 'Chart', name: 'Chart' }} "
        f"}})] }})"
    )


def _build_js(month: str, stats: dict, out_path: str, charts: dict = {}) -> str:
    """Generate the Node.js script that creates the .docx file."""

    cs   = stats["conversion"]
    rep  = stats["repeat"]
    lost = stats["lost"]
    cb   = stats["case_breakdown"]
    reg  = stats["region"]
    src  = stats["source"]
    feat = stats["features"]
    obs  = stats["observations"]

    def table_rows(rows: list, header_color="2E75B6") -> str:
        """Generate TableRow JS for a list of dicts."""
        if not rows:
            return ""
        headers = list(rows[0].keys())
        col_w   = 9360 // len(headers)
        js_rows = []

        # Header row
        hcells = ", ".join(
            f"""new TableCell({{
              borders: cellBorders,
              width: {{ size: {col_w}, type: WidthType.DXA }},
              shading: {{ fill: "{header_color}", type: ShadingType.CLEAR }},
              margins: {{ top: 80, bottom: 80, left: 120, right: 120 }},
              children: [new Paragraph({{ children: [new TextRun({{ text: "{_json_safe(h)}", bold: true, color: "FFFFFF", size: 20 }})] }})]
            }})"""
            for h in headers
        )
        js_rows.append(f"new TableRow({{ children: [{hcells}] }})")

        # Data rows
        for i, row in enumerate(rows):
            shade = "F2F7FB" if i % 2 == 0 else "FFFFFF"
            dcells = ", ".join(
                f"""new TableCell({{
                  borders: cellBorders,
                  width: {{ size: {col_w}, type: WidthType.DXA }},
                  shading: {{ fill: "{shade}", type: ShadingType.CLEAR }},
                  margins: {{ top: 80, bottom: 80, left: 120, right: 120 }},
                  children: [new Paragraph({{ children: [new TextRun({{ text: "{_json_safe(v)}", size: 20 }})] }})]
                }})"""
                for v in row.values()
            )
            js_rows.append(f"new TableRow({{ children: [{dcells}] }})")

        return ",\n        ".join(js_rows)

    # Build conversion table rows
    conv_rows = [
        {"Metric": "Total Demos",              "Value": str(cs["total_demos"])},
        {"Metric": "New Prospect Count",       "Value": str(cs["new_prospects"])},
        {"Metric": "Already Engaged Prospects","Value": str(cs["already_engaged"])},
        {"Metric": "Deal Won",                 "Value": str(cs["deal_won"])},
        {"Metric": "In Progress",              "Value": str(cs["in_progress"])},
        {"Metric": "Conversion Rate",          "Value": f"{cs['conversion_rate']}%"},
    ]

    rep_rows = [
        {"Metric": "Previously Engaged Prospects", "Count": str(rep["count"])},
        {"Metric": "Deal Won",                     "Count": str(rep["won"])},
        {"Metric": "Deal Lost",                    "Count": str(rep["lost"])},
        {"Metric": "In Progress",                  "Count": str(rep["in_progress"])},
    ]

    # Feature rows — split into categories (simplified: just use all)
    def feat_table_rows(feat_list):
        rows = []
        for f in feat_list:
            rows.append({
                "Feature Name"       : str(f.get("Feature name", ""))[:60],
                "Description"        : str(f.get("Description", ""))[:100],
                "Ticket ID"          : str(f.get("Ticket Ref", "")),
            })
        return rows

    js = f"""
const fs = require('fs');
const {{
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, WidthType, ShadingType, BorderStyle,
  PageNumber, Header, Footer, PageBreak, ImageRun
}} = require('docx');

const border = {{ style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }};
const cellBorders = {{ top: border, bottom: border, left: border, right: border }};

function heading1(text) {{
  return new Paragraph({{
    heading: HeadingLevel.HEADING_1,
    spacing: {{ before: 320, after: 160 }},
    children: [new TextRun({{ text, bold: true, size: 28, color: "2E75B6", font: "Arial" }})]
  }});
}}

function heading3(text) {{
  return new Paragraph({{
    heading: HeadingLevel.HEADING_3,
    spacing: {{ before: 200, after: 100 }},
    children: [new TextRun({{ text, bold: true, size: 22, color: "2E75B6", font: "Arial" }})]
  }});
}}

function bodyText(text) {{
  return new Paragraph({{
    spacing: {{ before: 80, after: 80 }},
    children: [new TextRun({{ text, size: 20, font: "Arial" }})]
  }});
}}

function observationLabel() {{
  return new Paragraph({{
    spacing: {{ before: 160, after: 80 }},
    children: [new TextRun({{ text: "Observation:", bold: true, size: 20, font: "Arial" }})]
  }});
}}

function makeTable(rows) {{
  return new Table({{
    width: {{ size: 9360, type: WidthType.DXA }},
    columnWidths: Array(Object.keys(rows[0] || {{'a':1}}).length).fill(Math.floor(9360 / Object.keys(rows[0] || {{'a':1}}).length)),
    rows
  }});
}}

const doc = new Document({{
  styles: {{
    default: {{
      document: {{ run: {{ font: "Arial", size: 20 }} }}
    }}
  }},
  sections: [{{
    properties: {{
      page: {{
        size: {{ width: 12240, height: 15840 }},
        margin: {{ top: 1080, right: 1080, bottom: 1080, left: 1080 }}
      }}
    }},
    headers: {{
      default: new Header({{
        children: [new Paragraph({{
          border: {{ bottom: {{ style: BorderStyle.SINGLE, size: 6, color: "2E75B6", space: 1 }} }},
          children: [new TextRun({{ text: "WorkDrive Presales Report – {month}", bold: true, size: 22, color: "2E75B6", font: "Arial" }})]
        }})]
      }})
    }},
    footers: {{
      default: new Footer({{
        children: [new Paragraph({{
          alignment: AlignmentType.RIGHT,
          children: [new TextRun({{ text: "Page ", size: 18 }}), new TextRun({{ children: [PageNumber.CURRENT], size: 18 }})]
        }})]
      }})
    }},
    children: [

      // ── TITLE ──────────────────────────────────────────────────────────
      new Paragraph({{
        alignment: AlignmentType.CENTER,
        spacing: {{ before: 240, after: 120 }},
        children: [new TextRun({{ text: "WorkDrive Presales Report – {month}", bold: true, size: 40, color: "2E75B6", font: "Arial" }})]
      }}),

      // ── EXECUTIVE SUMMARY ───────────────────────────────────────────────
      bodyText("{_json_safe(obs['summary'])}"),
      new Paragraph({{ children: [] }}),

      // ── CONVERSION PERFORMANCE ──────────────────────────────────────────
      heading1("Conversion Performance"),
      makeTable([
        {table_rows(conv_rows)}
      ]),
      new Paragraph({{ children: [] }}),
      {_image_run(charts['deal_won_lost']) if 'deal_won_lost' in charts else 'new Paragraph({children:[]})'},
      new Paragraph({{ children: [] }}),
      observationLabel(),
      bodyText("{_json_safe(obs['conversion'])}"),
      new Paragraph({{ children: [new PageBreak()] }}),

      // ── REPEAT ENGAGEMENT ───────────────────────────────────────────────
      heading1("Repeat Engagement Performance"),
      bodyText("Prospects initially engaged in previous months who re-entered the evaluation cycle."),
      makeTable([
        {table_rows(rep_rows)}
      ]),
      new Paragraph({{ children: [] }}),
      {_image_run(charts['deal_size_dist']) if 'deal_size_dist' in charts else 'new Paragraph({children:[]})'},
      new Paragraph({{ children: [] }}),
      observationLabel(),
      bodyText("{_json_safe(obs['repeat'])}"),
      new Paragraph({{ children: [] }}),

      // ── DEAL LOST ANALYSIS ──────────────────────────────────────────────
      heading1("Deal Lost Analysis"),
      makeTable([
        {table_rows(lost['rows'])}
      ]),
      new Paragraph({{ children: [] }}),
      {_image_run(charts['status_donut']) if 'status_donut' in charts else 'new Paragraph({children:[]})'},
      new Paragraph({{ children: [] }}),
      new Paragraph({{
        spacing: {{ before: 80, after: 80 }},
        children: [new TextRun({{ text: "Overall Loss Rate: ", bold: true, size: 20 }}), new TextRun({{ text: "{lost['loss_rate']}%", size: 20 }})]
      }}),
      observationLabel(),
      bodyText("{_json_safe(obs['lost'])}"),
      new Paragraph({{ children: [new PageBreak()] }}),

      // ── CASE BREAKDOWN ──────────────────────────────────────────────────
      heading1("Case Breakdown"),
      makeTable([
        {table_rows(cb)}
      ]),
      new Paragraph({{ children: [] }}),
      observationLabel(),
      bodyText("{_json_safe(obs['case'])}"),
      new Paragraph({{ children: [] }}),

      // ── REGION-WISE PERFORMANCE ─────────────────────────────────────────
      heading1("Region-Wise Performance"),
      makeTable([
        {table_rows(reg)}
      ]),
      new Paragraph({{ children: [] }}),
      {_image_run(charts['region_performance']) if 'region_performance' in charts else 'new Paragraph({children:[]})'},
      new Paragraph({{ children: [] }}),
      observationLabel(),
      bodyText("{_json_safe(obs['region'])}"),
      new Paragraph({{ children: [new PageBreak()] }}),

      // ── DEAL SOURCE ANALYSIS ────────────────────────────────────────────
      heading1("Deal Source Analysis"),
      makeTable([
        {table_rows(src[:6])}
      ]),
      new Paragraph({{ children: [] }}),
      {_image_run(charts['source_breakdown']) if 'source_breakdown' in charts else 'new Paragraph({children:[]})'},
      new Paragraph({{ children: [] }}),
      observationLabel(),
      bodyText("{_json_safe(obs['source'])}"),
      new Paragraph({{ children: [] }}),

      // ── FEATURE DEMAND ANALYSIS ─────────────────────────────────────────
      heading1("Feature Demand Analysis"),
      bodyText("{_json_safe(obs['feature_intro'])}"),
      new Paragraph({{ children: [] }}),
      makeTable([
        {table_rows(feat_table_rows(feat[:8]))}
      ]),
      new Paragraph({{ children: [] }}),
      observationLabel(),
      bodyText("{_json_safe(obs['features'])}"),

    ]
  }}]
}});

Packer.toBuffer(doc).then(buffer => {{
  fs.writeFileSync("{_json_safe(out_path)}", buffer);
  console.log("OK:" + "{_json_safe(out_path)}");
}}).catch(e => {{
  console.error("ERR:" + e.message);
  process.exit(1);
}});
"""
    return js


# ── Main generate function ───────────────────────────────────────────────────

def generate_report(month: str, out_path: Optional[str] = None) -> str:
    """
    Generate a presales report for the given month.

    Parameters
    ----------
    month    : e.g. "April", "March"
    out_path : where to save the .docx (default: project folder)

    Returns
    -------
    str — absolute path to the generated .docx file
    """
    month = month.capitalize()
    _get_data()   # warm the cache
    mdf   = _month_df(month)

    if mdf.empty:
        raise ValueError(f"No data found for month: {month}")

    if out_path is None:
        out_path = str(BASE_DIR / f"WorkDrive Presales Report - {month} 2026.docx")

    print(f"📊 Computing stats for {month} ({len(mdf)} records)…")

    cs   = conversion_stats(mdf)
    rep  = repeat_engagement_stats(mdf)
    lost = deal_lost_stats(mdf)
    cb   = case_breakdown(mdf)
    reg  = region_stats(mdf)
    src  = source_stats(mdf)
    feat = feature_stats(month)

    print("✍️  Generating observations with LLM…")

    top_region    = reg[0]["Region"] if reg else "IN"
    top_source    = src[0]["Source"] if src else "Book a Demo"
    feat_names    = ", ".join(f.get("Feature name", "") for f in feat[:4])

    observations = {
        "summary": _llm(
            f"Write a 2-sentence executive summary for a presales report for {month} 2026. "
            f"Data: {cs['total_demos']} demos, {cs['new_prospects']} new prospects, "
            f"{cs['deal_won']} deals won, {cs['conversion_rate']}% conversion rate, "
            f"{cs['in_progress']} in progress.",
            max_tokens=150,
        ),
        "conversion": _observe(
            f"Total demos: {cs['total_demos']}, New prospects: {cs['new_prospects']}, "
            f"Deal won: {cs['deal_won']}, Conversion rate: {cs['conversion_rate']}%, "
            f"In progress: {cs['in_progress']}",
            f"Observe trends in conversion for {month}.",
        ),
        "repeat": _observe(
            f"Repeat engagements: {rep['count']}, Won: {rep['won']}, "
            f"Lost: {rep['lost']}, In progress: {rep['in_progress']}",
            "Comment on repeat engagement performance.",
        ),
        "lost": _observe(
            f"Total lost: {lost['total_lost']}, Loss rate: {lost['loss_rate']}%, "
            f"Categories: {json.dumps(lost['rows'])}",
            "Describe the deal loss patterns and what they suggest.",
        ),
        "case": _observe(
            f"Case breakdown: {json.dumps(cb)}",
            "Describe the case mix and what it means for the pipeline.",
        ),
        "region": _observe(
            f"Region data: {json.dumps(reg)}",
            f"Observe regional performance, noting that {top_region} leads.",
        ),
        "source": _observe(
            f"Source breakdown: {json.dumps(src[:6])}",
            f"Describe lead sources, noting that '{top_source}' is the primary channel.",
        ),
        "feature_intro": (
            f"The following features were most requested during {month} 2026, "
            "based on enterprise and mid-market prospect discussions."
        ),
        "features": _observe(
            f"Top features requested: {feat_names}",
            "Summarise the feature demand trends and what they indicate about customer needs.",
        ),
    }

    stats = {
        "conversion"    : cs,
        "repeat"        : rep,
        "lost"          : lost,
        "case_breakdown": cb,
        "region"        : reg,
        "source"        : src,
        "features"      : feat,
        "observations"  : observations,
    }

    print("📊 Generating charts…")
    from chart_generator import generate_charts
    chart_dir = str(BASE_DIR / f"charts_{month.lower()}")
    charts = generate_charts(mdf, month, chart_dir)

    print("📝 Building .docx…")

    js_code  = _build_js(month, stats, out_path, charts=charts)
    tmp_dir  = Path(tempfile.mkdtemp())
    js_file  = tmp_dir / "report.js"
    node_mod = BASE_DIR / "node_modules"

    js_file.write_text(js_code)
    # Symlink node_modules so require('docx') resolves
    (tmp_dir / "node_modules").symlink_to(node_mod)

    result = subprocess.run(
        ["node", str(js_file)],
        capture_output=True, text=True
    )
    shutil.rmtree(tmp_dir, ignore_errors=True)

    if result.returncode != 0 or "ERR:" in result.stdout:
        err = result.stderr or result.stdout
        raise RuntimeError(f"Node.js failed:\n{err}")

    print(f"✅ Report saved → {out_path}")
    return out_path


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python report_generator.py <Month> [--out /path/to/report.docx]")
        sys.exit(0)

    month = sys.argv[1]
    out   = None
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        out = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

    path = generate_report(month, out)
    print(f"\nOpen with: open \"{path}\"")
