"""
universal_report_generator.py
------------------------------
Generates a polished Word (.docx) report from ANY dataset.

Works by:
  1. Auto-analysing the DataFrame (numeric, categorical, date, text columns)
  2. Matching analysis to the reference template sections (if provided)
  3. Generating matplotlib charts for the most meaningful columns
  4. Asking the LLM to write observations for each section
  5. Building the .docx with python-docx

No hardcoded presales logic — works for sales, HR, finance, ops, anything.
"""

import io, os, re, tempfile, textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ── LLM config ────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL  = "llama3.1:8b"

CHART_COLORS = ["#4F8EF7","#10B981","#F59E0B","#EF4444","#8B5CF6",
                "#06B6D4","#EC4899","#84CC16","#F97316","#6366F1"]

# ── LLM helper ────────────────────────────────────────────────────────────────

def _llm(prompt: str, max_tokens: int = 300) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False,
                  "options": {"num_predict": max_tokens, "temperature": 0.3}},
            timeout=120,
        )
        return r.json()["response"].strip()
    except Exception as e:
        return f"[Observation unavailable: {e}]"


# ── DataFrame analysis ────────────────────────────────────────────────────────

def _analyze(df: pd.DataFrame) -> dict:
    """
    Inspect columns and return a structured analysis dict:
      numeric_cols, categorical_cols, date_cols, text_cols,
      key_stats, top_categoricals
    """
    numeric_cols     = []
    categorical_cols = []
    date_cols        = []
    text_cols        = []

    for col in df.columns:
        if col.startswith("_"):
            continue
        s = df[col].dropna()
        if s.empty:
            continue

        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
            continue

        # Try numeric coercion
        num = pd.to_numeric(s, errors="coerce")
        if num.notna().sum() > len(s) * 0.6:
            numeric_cols.append(col)
            continue

        avg_len  = s.astype(str).str.len().mean()
        n_unique = s.nunique()

        if avg_len > 60 or (n_unique > len(s) * 0.5 and n_unique > 20):
            text_cols.append(col)
        else:
            categorical_cols.append(col)

    # Key numeric stats
    key_stats = {}
    for col in numeric_cols[:8]:
        num = pd.to_numeric(df[col], errors="coerce")
        key_stats[col] = {
            "sum"  : round(float(num.sum()), 2),
            "mean" : round(float(num.mean()), 2),
            "max"  : round(float(num.max()), 2),
            "min"  : round(float(num.min()), 2),
            "count": int(num.notna().sum()),
        }

    # Top-N value counts for categorical cols
    top_categoricals = {}
    for col in categorical_cols[:10]:
        top_categoricals[col] = df[col].value_counts().head(10).to_dict()

    return {
        "total_rows"      : len(df),
        "numeric_cols"    : numeric_cols,
        "categorical_cols": categorical_cols,
        "date_cols"       : date_cols,
        "text_cols"       : text_cols,
        "key_stats"       : key_stats,
        "top_categoricals": top_categoricals,
    }


def _stats_summary(analysis: dict) -> str:
    """Compact text summary of the analysis for LLM prompts."""
    lines = [f"Dataset: {analysis['total_rows']} rows"]
    for col, vc in list(analysis["top_categoricals"].items())[:5]:
        top = ", ".join(f"{k}:{v}" for k,v in list(vc.items())[:5])
        lines.append(f"{col}: {top}")
    for col, s in list(analysis["key_stats"].items())[:4]:
        lines.append(f"{col}: sum={s['sum']}, mean={s['mean']}, max={s['max']}")
    return "\n".join(lines)


# ── Chart generation ──────────────────────────────────────────────────────────

def _plt_defaults():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor"  : "white",
        "axes.edgecolor"  : "#CCCCCC",
        "axes.labelcolor" : "#333333",
        "xtick.color"     : "#333333",
        "ytick.color"     : "#333333",
        "text.color"      : "#333333",
        "grid.color"      : "#EEEEEE",
        "grid.linestyle"  : "--",
        "grid.linewidth"  : 0.6,
    })


def _save_chart(fig, chart_dir: str, name: str) -> str:
    path = os.path.join(chart_dir, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def generate_charts(df: pd.DataFrame, analysis: dict, chart_dir: str) -> dict:
    """Generate up to 6 charts. Returns {chart_name: png_path}."""
    _plt_defaults()
    charts = {}

    # 1. Bar charts for top categorical columns (max 3)
    for col in analysis["categorical_cols"][:3]:
        vc = df[col].value_counts().head(10)
        if len(vc) < 2:
            continue
        fig, ax = plt.subplots(figsize=(7, 3.5))
        bars = ax.bar(range(len(vc)), vc.values,
                      color=CHART_COLORS[:len(vc)], edgecolor="white", linewidth=0.5)
        ax.set_xticks(range(len(vc)))
        ax.set_xticklabels([str(x)[:20] for x in vc.index], rotation=30,
                           ha="right", fontsize=8)
        ax.set_ylabel("Count", fontsize=9)
        ax.set_title(col, fontsize=10, fontweight="bold", pad=8)
        for bar, val in zip(bars, vc.values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                    str(val), ha="center", va="bottom", fontsize=8)
        ax.yaxis.grid(True); ax.set_axisbelow(True)
        plt.tight_layout()
        charts[f"cat_{col[:20]}"] = _save_chart(fig, chart_dir, f"cat_{col[:20]}")

    # 2. Numeric summary bar chart
    if analysis["key_stats"]:
        cols   = list(analysis["key_stats"].keys())[:5]
        totals = [analysis["key_stats"][c]["sum"] for c in cols]
        if any(t > 0 for t in totals):
            fig, ax = plt.subplots(figsize=(7, 3.5))
            ax.bar(range(len(cols)), totals, color=CHART_COLORS[:len(cols)],
                   edgecolor="white", linewidth=0.5)
            ax.set_xticks(range(len(cols)))
            ax.set_xticklabels([c[:18] for c in cols], rotation=20, ha="right", fontsize=8)
            ax.set_title("Numeric column totals", fontsize=10, fontweight="bold", pad=8)
            ax.yaxis.grid(True); ax.set_axisbelow(True)
            plt.tight_layout()
            charts["numeric_totals"] = _save_chart(fig, chart_dir, "numeric_totals")

    # 3. Time-series if date column exists
    if analysis["date_cols"]:
        dcol = analysis["date_cols"][0]
        try:
            monthly = df.groupby(df[dcol].dt.to_period("M")).size()
            if len(monthly) > 1:
                fig, ax = plt.subplots(figsize=(7, 3))
                ax.plot(range(len(monthly)), monthly.values,
                        color=CHART_COLORS[0], linewidth=2.5, marker="o",
                        markersize=5, markerfacecolor="white",
                        markeredgecolor=CHART_COLORS[0], markeredgewidth=2)
                ax.fill_between(range(len(monthly)), monthly.values,
                                alpha=0.08, color=CHART_COLORS[0])
                ax.set_xticks(range(len(monthly)))
                ax.set_xticklabels([str(p) for p in monthly.index],
                                   rotation=30, ha="right", fontsize=7)
                ax.set_title(f"Volume over time ({dcol})", fontsize=10,
                             fontweight="bold", pad=8)
                ax.yaxis.grid(True); ax.set_axisbelow(True)
                plt.tight_layout()
                charts["time_series"] = _save_chart(fig, chart_dir, "time_series")
        except Exception:
            pass

    # 4. Pie chart for first categorical col with ≤7 values
    for col in analysis["categorical_cols"]:
        vc = df[col].value_counts()
        if 2 <= len(vc) <= 7:
            fig, ax = plt.subplots(figsize=(5, 4))
            wedges, texts, autotexts = ax.pie(
                vc.values, labels=None,
                colors=CHART_COLORS[:len(vc)],
                autopct="%1.1f%%", startangle=90,
                pctdistance=0.82,
                wedgeprops={"linewidth": 1.5, "edgecolor": "white"},
            )
            for at in autotexts:
                at.set_fontsize(8)
            ax.legend(vc.index.tolist(), loc="lower center",
                      bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=8)
            ax.set_title(col, fontsize=10, fontweight="bold", pad=8)
            plt.tight_layout()
            charts[f"pie_{col[:20]}"] = _save_chart(fig, chart_dir, f"pie_{col[:20]}")
            break

    return charts


# ── Document styling ──────────────────────────────────────────────────────────

def _hex_to_rgb(hex_color: str):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _set_cell_bg(cell, hex_color: str):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color.lstrip("#"))
    tcPr.append(shd)


def _style_doc(doc: Document):
    """Apply professional styling to the document."""
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    for h_style, size, bold in [
        ("Heading 1", 16, True),
        ("Heading 2", 13, True),
        ("Heading 3", 11, True),
    ]:
        s = doc.styles[h_style]
        s.font.name  = "Calibri"
        s.font.size  = Pt(size)
        s.font.bold  = bold
        r, g, b = _hex_to_rgb("#2E4057")
        s.font.color.rgb = RGBColor(r, g, b)

    # Narrow margins
    for section in doc.sections:
        section.top_margin    = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)


def _add_table(doc: Document, df_table: pd.DataFrame,
               header_color: str = "#2E4057", max_rows: int = 30):
    """Add a styled table to the document."""
    df_t = df_table.head(max_rows)
    table = doc.add_table(rows=1, cols=len(df_t.columns))
    table.style = "Table Grid"

    # Header row
    hdr = table.rows[0]
    for i, col in enumerate(df_t.columns):
        cell = hdr.cells[i]
        cell.text = str(col)
        _set_cell_bg(cell, header_color)
        for para in cell.paragraphs:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in para.runs:
                run.font.bold  = True
                run.font.size  = Pt(9)
                run.font.color.rgb = RGBColor(255, 255, 255)

    # Data rows
    for idx, (_, row) in enumerate(df_t.iterrows()):
        tr = table.add_row()
        bg = "F2F2F2" if idx % 2 == 0 else "FFFFFF"
        for i, val in enumerate(row):
            cell = tr.cells[i]
            cell.text = str(val) if pd.notna(val) else "—"
            _set_cell_bg(cell, bg)
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(9)

    doc.add_paragraph()


def _add_chart(doc: Document, png_path: str, width_inches: float = 6.0):
    if os.path.exists(png_path):
        doc.add_picture(png_path, width=Inches(width_inches))
        last_para = doc.paragraphs[-1]
        last_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()


# ── Section builders ──────────────────────────────────────────────────────────

def _build_overview_table(df: pd.DataFrame, analysis: dict) -> pd.DataFrame:
    """One-row-per-column summary."""
    rows = []
    for col in df.columns:
        if col.startswith("_"):
            continue
        s = df[col].dropna()
        if s.empty:
            continue
        rows.append({
            "Column"  : col,
            "Type"    : ("Numeric" if col in analysis["numeric_cols"]
                         else "Date" if col in analysis["date_cols"]
                         else "Text" if col in analysis["text_cols"]
                         else "Category"),
            "Count"   : int(s.count()),
            "Unique"  : int(s.nunique()),
            "Sample"  : str(s.iloc[0])[:50] if len(s) > 0 else "—",
        })
    return pd.DataFrame(rows)


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_universal_report(
    bundle,
    scope       : str,           # "sheet" | "month" | "all"
    scope_value : Optional[str], # sheet name, month name, or None
    template_struct: dict,
    out_path    : Optional[str] = None,
) -> str:
    """
    Generate a Word report for any dataset.

    Parameters
    ----------
    bundle       : DataBundle from dynamic_ingestion.load_file()
    scope        : "sheet" — one tab | "month" — one month | "all" — everything
    scope_value  : name of sheet/month (None for "all")
    template_struct : parsed template from dynamic_ingestion.parse_template()
    out_path     : where to save the .docx (auto-generated if None)

    Returns
    -------
    str  : path to the generated .docx file
    """

    # ── 1. Get the data for this scope ────────────────────────────────────────
    df = _get_scope_df(bundle, scope, scope_value)
    if df.empty:
        raise ValueError(f"No data found for scope='{scope}' value='{scope_value}'")

    # ── 2. Analyse ────────────────────────────────────────────────────────────
    analysis  = _analyze(df)
    stats_txt = _stats_summary(analysis)

    # ── 3. Generate charts ────────────────────────────────────────────────────
    chart_dir = tempfile.mkdtemp()
    charts    = generate_charts(df, analysis, chart_dir)

    # ── 4. Resolve title / scope label ───────────────────────────────────────
    template_title = template_struct.get("title", "Report")
    if scope == "all":
        scope_label = "Full Dataset"
    elif scope_value:
        scope_label = scope_value
    else:
        scope_label = "All Data"

    report_title = f"{template_title} — {scope_label}"
    date_str     = datetime.now().strftime("%B %d, %Y")

    # ── 5. Determine sections ─────────────────────────────────────────────────
    # Use template sections if provided, otherwise auto-generate
    tmpl_sections = template_struct.get("sections", [])
    tmpl_context  = ""
    if tmpl_sections:
        tmpl_context = "\nReference template sections: " + \
                       ", ".join(s["heading"] for s in tmpl_sections)

    # ── 6. Generate LLM content ───────────────────────────────────────────────
    def observe(instruction: str, extra_ctx: str = "", tokens: int = 250) -> str:
        return _llm(
            f"You are a professional report writer. Write 3-4 concise sentences "
            f"as a business report observation. Use numbers. No bullet points.\n\n"
            f"Dataset stats:\n{stats_txt}\n"
            f"{extra_ctx}\n"
            f"{tmpl_context}\n\n"
            f"Instruction: {instruction}",
            max_tokens=tokens,
        )

    exec_summary = observe(
        f"Write an executive summary for a report titled '{report_title}' "
        f"covering {analysis['total_rows']} records.",
        tokens=200,
    )

    # ── 7. Build Word document ────────────────────────────────────────────────
    doc = Document()
    _style_doc(doc)

    # ── Cover ─────────────────────────────────────────────────────────────────
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title_para.add_run(report_title)
    title_run.font.size  = Pt(22)
    title_run.font.bold  = True
    r, g, b = _hex_to_rgb("#2E4057")
    title_run.font.color.rgb = RGBColor(r, g, b)

    sub_para = doc.add_paragraph()
    sub_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_run = sub_para.add_run(f"Generated on {date_str}  ·  {analysis['total_rows']:,} records")
    sub_run.font.size  = Pt(11)
    sub_run.font.color.rgb = RGBColor(100, 100, 100)

    doc.add_paragraph()

    # ── Executive Summary ─────────────────────────────────────────────────────
    doc.add_heading("Executive Summary", level=1)
    doc.add_paragraph(exec_summary)
    doc.add_paragraph()

    # ── Data Overview table ───────────────────────────────────────────────────
    doc.add_heading("Data Overview", level=1)
    overview_df = _build_overview_table(df, analysis)
    _add_table(doc, overview_df)

    # ── Template-driven sections (if template provided) ───────────────────────
    if tmpl_sections:
        for section in tmpl_sections:
            heading = section.get("heading", "")
            if not heading or heading == template_title:
                continue

            doc.add_heading(heading, level=1)

            # Find the most relevant categorical col for this section heading
            heading_lower = heading.lower()
            relevant_col  = None
            for col in analysis["categorical_cols"]:
                if any(w in col.lower() for w in heading_lower.split()):
                    relevant_col = col
                    break

            if relevant_col and relevant_col in analysis["top_categoricals"]:
                vc = analysis["top_categoricals"][relevant_col]
                tbl_df = pd.DataFrame(
                    [(k, v) for k, v in vc.items()],
                    columns=[relevant_col, "Count"]
                )
                _add_table(doc, tbl_df)

            # Add chart if one matches
            for chart_name, chart_path in charts.items():
                if any(w in chart_name.lower()
                       for w in heading_lower.split() if len(w) > 3):
                    _add_chart(doc, chart_path)
                    break

            if section.get("has_observation", False) or True:
                obs = observe(
                    f"Write an observation for the '{heading}' section.",
                    extra_ctx=f"Relevant data: {list(analysis['top_categoricals'].items())[:2]}",
                )
                doc.add_heading("Observation", level=2)
                doc.add_paragraph(obs)

            doc.add_paragraph()

    else:
        # ── Auto-generated sections (no template) ────────────────────────────

        # Categorical breakdowns
        if analysis["categorical_cols"]:
            doc.add_heading("Category Breakdown", level=1)
            for col in analysis["categorical_cols"][:4]:
                doc.add_heading(col, level=2)
                vc = df[col].value_counts().head(10)
                tbl_df = pd.DataFrame({"Value": vc.index, "Count": vc.values})
                tbl_df["Percentage"] = (tbl_df["Count"] / tbl_df["Count"].sum() * 100).round(1).astype(str) + "%"
                _add_table(doc, tbl_df)
                # Insert matching chart
                chart_key = f"cat_{col[:20]}"
                if chart_key in charts:
                    _add_chart(doc, charts[chart_key])
                elif f"pie_{col[:20]}" in charts:
                    _add_chart(doc, charts[f"pie_{col[:20]}"])

            obs_cat = observe(
                "Summarise the key patterns in the categorical/segment breakdown.",
                extra_ctx=str(list(analysis["top_categoricals"].items())[:3]),
            )
            doc.add_heading("Observations", level=2)
            doc.add_paragraph(obs_cat)
            doc.add_paragraph()

        # Numeric analysis
        if analysis["key_stats"]:
            doc.add_heading("Numeric Analysis", level=1)
            rows = []
            for col, s in analysis["key_stats"].items():
                rows.append({"Metric": col, "Total": f"{s['sum']:,.2f}",
                             "Average": f"{s['mean']:,.2f}",
                             "Max": f"{s['max']:,.2f}", "Min": f"{s['min']:,.2f}"})
            _add_table(doc, pd.DataFrame(rows))
            if "numeric_totals" in charts:
                _add_chart(doc, charts["numeric_totals"])
            obs_num = observe(
                "Summarise the key findings from the numeric data.",
                extra_ctx=str(analysis["key_stats"]),
            )
            doc.add_heading("Observations", level=2)
            doc.add_paragraph(obs_num)
            doc.add_paragraph()

        # Time trend
        if "time_series" in charts:
            doc.add_heading("Trend Over Time", level=1)
            _add_chart(doc, charts["time_series"])
            obs_time = observe(
                f"Summarise the trend over time shown in the {analysis['date_cols'][0]} column.",
            )
            doc.add_heading("Observations", level=2)
            doc.add_paragraph(obs_time)
            doc.add_paragraph()

    # ── Remaining charts not yet inserted ─────────────────────────────────────
    inserted_charts = set()
    for section in tmpl_sections:
        for cn, cp in charts.items():
            if any(w in cn.lower() for w in section.get("heading","").lower().split() if len(w)>3):
                inserted_charts.add(cn)

    leftover = {k: v for k, v in charts.items() if k not in inserted_charts
                and "numeric_totals" not in k and "time_series" not in k}
    if leftover and not tmpl_sections:
        pass  # already inserted above in auto mode

    # ── Recommendations ───────────────────────────────────────────────────────
    doc.add_heading("Recommendations", level=1)
    recs = observe(
        f"Based on the data for '{scope_label}', provide 3 actionable business recommendations.",
        tokens=300,
    )
    doc.add_paragraph(recs)

    # ── Save ──────────────────────────────────────────────────────────────────
    if out_path is None:
        safe_label = re.sub(r"[^\w\-_]", "_", scope_label)
        out_path   = os.path.join(tempfile.mkdtemp(), f"Report_{safe_label}.docx")

    doc.save(out_path)

    # Cleanup charts
    import shutil
    shutil.rmtree(chart_dir, ignore_errors=True)

    return out_path


# ── Scope helper ──────────────────────────────────────────────────────────────

def _get_scope_df(bundle, scope: str, scope_value: Optional[str]) -> pd.DataFrame:
    """Return the right slice of data for the requested scope."""
    df = bundle.df

    if scope == "all":
        # All rows (exclude feature/noshow-type sheets if month_col present)
        if bundle.month_col and bundle.month_col in df.columns and bundle.months:
            return df[df[bundle.month_col].isin(bundle.months)].copy()
        return df.copy()

    if scope == "sheet" and scope_value:
        if scope_value in bundle.sheets:
            return bundle.sheets[scope_value].copy()
        # Fallback: filter by _sheet column
        if "_sheet" in df.columns:
            return df[df["_sheet"] == scope_value].copy()
        return df.copy()

    if scope == "month" and scope_value:
        if bundle.month_col and bundle.month_col in df.columns:
            mask = df[bundle.month_col].astype(str).str.lower() == scope_value.lower()
            return df[mask].copy()
        return df.copy()

    return df.copy()
