"""
app.py — Presales AI  |  Offline Intelligence Platform
-------------------------------------------------------
Run:  python3 -m streamlit run app.py
"""

import io, os, sys, re, json, textwrap, tempfile, shutil
import streamlit as st
import pandas as pd
import requests
from pathlib import Path

BASE_DIR   = Path("/Users/sakthi-3766/Claude/Projects/Local SLM")
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL  = "llama3.1:8b"
sys.path.insert(0, str(BASE_DIR))

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title = "Presales AI",
    page_icon  = "🧠",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Base ─────────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: #0E1117; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #111827 0%, #0E1117 100%);
    border-right: 1px solid rgba(79,142,247,0.15);
}

/* ── Metric cards ────────────────────────────────────────────────────────── */
.metric-card {
    background: linear-gradient(135deg, rgba(79,142,247,0.12) 0%, rgba(79,142,247,0.04) 100%);
    border: 1px solid rgba(79,142,247,0.25);
    border-radius: 14px;
    padding: 20px 24px;
    text-align: center;
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
}
.metric-card:hover {
    border-color: rgba(79,142,247,0.6);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(79,142,247,0.15);
}
.metric-card .value { font-size: 32px; font-weight: 700; color: #4F8EF7; line-height: 1; }
.metric-card .label { font-size: 12px; color: #8B92A5; margin-top: 6px; text-transform: uppercase; letter-spacing: 0.8px; }
.metric-card .delta { font-size: 11px; margin-top: 4px; }
.delta-pos { color: #10B981; } .delta-neg { color: #EF4444; }

/* ── Status badge ────────────────────────────────────────────────────────── */
.badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
}
.badge-green  { background: rgba(16,185,129,0.15); color: #10B981; border: 1px solid rgba(16,185,129,0.3); }
.badge-red    { background: rgba(239,68,68,0.15);  color: #EF4444; border: 1px solid rgba(239,68,68,0.3); }
.badge-blue   { background: rgba(79,142,247,0.15); color: #4F8EF7; border: 1px solid rgba(79,142,247,0.3); }
.badge-yellow { background: rgba(245,158,11,0.15); color: #F59E0B; border: 1px solid rgba(245,158,11,0.3); }

/* ── Chat messages ───────────────────────────────────────────────────────── */
.user-msg {
    background: rgba(79,142,247,0.12);
    border: 1px solid rgba(79,142,247,0.2);
    border-radius: 14px 14px 4px 14px;
    padding: 14px 18px; margin: 8px 0; color: #E8EAF0;
}
.ai-msg {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 14px 14px 14px 4px;
    padding: 14px 18px; margin: 8px 0; color: #E8EAF0;
    line-height: 1.7;
}
.ai-msg-header {
    font-size: 11px; color: #4F8EF7; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;
}

/* ── Section headers ─────────────────────────────────────────────────────── */
.section-header {
    font-size: 13px; font-weight: 600; color: #4F8EF7;
    text-transform: uppercase; letter-spacing: 1px;
    margin-bottom: 16px; padding-bottom: 8px;
    border-bottom: 1px solid rgba(79,142,247,0.2);
}

/* ── Upload zone ─────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px dashed rgba(79,142,247,0.3) !important;
    border-radius: 10px !important;
}

/* ── Tab bar ─────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    background: rgba(255,255,255,0.04);
    border-radius: 10px; padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px; padding: 8px 20px;
    font-size: 13px; font-weight: 600; color: #8B92A5;
}
.stTabs [aria-selected="true"] {
    background: rgba(79,142,247,0.18) !important;
    color: #4F8EF7 !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4F8EF7, #3B6FD4) !important;
    border: none !important; border-radius: 10px !important;
    font-weight: 600 !important; letter-spacing: 0.3px !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 16px rgba(79,142,247,0.4) !important;
    transform: translateY(-1px) !important;
}

/* ── Template info bar ───────────────────────────────────────────────────── */
.template-bar {
    background: linear-gradient(90deg, rgba(245,158,11,0.12), rgba(245,158,11,0.04));
    border: 1px solid rgba(245,158,11,0.25);
    border-radius: 10px; padding: 10px 16px;
    font-size: 13px; color: #F59E0B;
    margin-bottom: 16px;
}

/* ── Progress bar ────────────────────────────────────────────────────────── */
.stProgress > div > div { background: linear-gradient(90deg, #4F8EF7, #10B981) !important; }

/* ── Divider ─────────────────────────────────────────────────────────────── */
hr { border-color: rgba(255,255,255,0.08) !important; }

/* ── Expander ────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
}

/* ── Dataframe ───────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* ── Suggestions ─────────────────────────────────────────────────────────── */
.suggestion-btn {
    display: inline-block;
    background: rgba(79,142,247,0.1);
    border: 1px solid rgba(79,142,247,0.25);
    border-radius: 20px; padding: 5px 14px;
    font-size: 12px; color: #4F8EF7;
    margin: 3px; cursor: pointer;
}

/* ── Logo text ───────────────────────────────────────────────────────────── */
.logo-text {
    font-size: 22px; font-weight: 700; color: #4F8EF7;
    letter-spacing: -0.5px; line-height: 1;
}
.logo-sub { font-size: 11px; color: #8B92A5; letter-spacing: 0.5px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def ollama_ok() -> bool:
    try:
        return requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).status_code == 200
    except Exception:
        return False


def llm(prompt: str, temperature: float = 0.2, max_tokens: int = 600) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False,
                  "temperature": temperature, "options": {"num_predict": max_tokens}},
            timeout=120,
        )
        return r.json()["response"].strip()
    except Exception as e:
        return f"⚠️ LLM error: {e}"


MONTH_ORDER = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]

def _demo_df(df, bundle):
    """Return only the demo rows (Jan–Jun sheets), excluding feature/noshow sheets."""
    if bundle.month_col and bundle.month_col in df.columns:
        return df[df[bundle.month_col].isin(bundle.months)].copy()
    return df.copy()


def _filter_month(df, bundle, months_list):
    """Filter dataframe to specific months."""
    if not months_list or not bundle.month_col:
        return df
    col = bundle.month_col
    if col in df.columns:
        return df[df[col].str.lower().isin([m.lower() for m in months_list])]
    return df


def compute_stats(bundle) -> str:
    """
    Pre-compute a comprehensive stats block from the dataset.
    The LLM reads this to answer questions — no code generation needed.
    """
    df   = _demo_df(bundle.df, bundle)
    mcol = bundle.month_col   # "_sheet"

    # Identify key columns (exact names from actual data)
    status_col  = next((c for c in df.columns if c == "Status"), None)
    region_col  = next((c for c in df.columns if c == "Region"), None)
    industry_col= next((c for c in df.columns if c == "Industry"), None)
    source_col  = next((c for c in df.columns if c == "Source"), None)
    eng_col     = next((c for c in df.columns if c == "Engagement Type"), None)
    rev_col     = next((c for c in df.columns if c == "Revenue"), None)
    deal_col    = next((c for c in df.columns if c == "Deal Size"), None)
    handler_col = next((c for c in df.columns if c == "Handled by"), None)
    platform_col= next((c for c in df.columns if c == "Current Platform"), None)

    lines = []
    lines.append(f"=== PRESALES DATA STATS ({len(df)} total demo records, {len(bundle.months)} months) ===")
    lines.append(f"Months covered: {', '.join(bundle.months)}")

    # Overall status
    if status_col:
        sc = df[status_col].value_counts()
        won  = sc.get("Deal Won", 0)
        lost = sc.get("Deal Lost", 0)
        prog = sc.get("In Progress", 0)
        rate = round(won / max(len(df), 1) * 100, 1)
        lines.append(f"\nOVERALL STATUS:")
        for k, v in sc.items():
            lines.append(f"  {k}: {v}")
        lines.append(f"  Conversion Rate (Deal Won / Total): {rate}%")
        lines.append(f"  Total Demos: {len(df)}, Won: {won}, Lost: {lost}, In Progress: {prog}")

    # Per-month breakdown
    lines.append(f"\nMONTH-BY-MONTH BREAKDOWN:")
    for month in bundle.months:
        mdf = df[df[mcol] == month] if mcol in df.columns else df
        n = len(mdf)
        if n == 0:
            continue
        row = f"  {month}: {n} demos"
        if status_col:
            sc_m = mdf[status_col].value_counts()
            won_m  = sc_m.get("Deal Won", 0)
            lost_m = sc_m.get("Deal Lost", 0)
            prog_m = sc_m.get("In Progress", 0)
            rate_m = round(won_m / max(n, 1) * 100, 1)
            row += f" | Won={won_m}, Lost={lost_m}, InProgress={prog_m}, Rate={rate_m}%"
        if rev_col:
            rev_m = pd.to_numeric(mdf[rev_col], errors="coerce").sum()
            row += f" | Revenue={rev_m:,.0f}"
        lines.append(row)

    # By region
    if region_col:
        lines.append(f"\nBY REGION:")
        for reg, cnt in df[region_col].value_counts().items():
            rdf = df[df[region_col] == reg]
            row = f"  {reg}: {cnt} demos"
            if status_col:
                won_r = len(rdf[rdf[status_col] == "Deal Won"])
                rate_r = round(won_r / max(cnt, 1) * 100, 1)
                row += f", Won={won_r} ({rate_r}%)"
            lines.append(row)

    # By industry (top 15)
    if industry_col:
        lines.append(f"\nTOP INDUSTRIES (by demo count):")
        for ind, cnt in df[industry_col].value_counts().head(15).items():
            lines.append(f"  {ind}: {cnt}")

    # By source
    if source_col:
        lines.append(f"\nBY LEAD SOURCE:")
        for src, cnt in df[source_col].value_counts().items():
            lines.append(f"  {src}: {cnt}")

    # By engagement type
    if eng_col:
        lines.append(f"\nBY ENGAGEMENT TYPE:")
        for et, cnt in df[eng_col].value_counts().items():
            lines.append(f"  {et}: {cnt}")

    # Revenue summary
    if rev_col:
        rev = pd.to_numeric(df[rev_col], errors="coerce")
        lines.append(f"\nREVENUE:")
        lines.append(f"  Total: {rev.sum():,.0f}")
        lines.append(f"  Average per deal: {rev.mean():,.0f}")
        lines.append(f"  Max: {rev.max():,.0f}")

    # Handler performance
    if handler_col and status_col:
        lines.append(f"\nBY PRESALES HANDLER:")
        for h, cnt in df[handler_col].value_counts().items():
            hdf = df[df[handler_col] == h]
            won_h = len(hdf[hdf[status_col] == "Deal Won"])
            rate_h = round(won_h / max(cnt, 1) * 100, 1)
            lines.append(f"  {h}: {cnt} demos, {won_h} won ({rate_h}%)")

    # Platform migration
    if platform_col:
        lines.append(f"\nEXISTING PLATFORMS (prospects migrating from):")
        for p, cnt in df[platform_col].value_counts().head(10).items():
            lines.append(f"  {p}: {cnt}")

    return "\n".join(lines)


def answer_question(question: str, bundle) -> str:
    df    = bundle.df
    demos = _demo_df(df, bundle)
    q_low = question.lower()

    # ── Detect months mentioned in question ───────────────────────────────────
    months_mentioned = [m for m in MONTH_ORDER if m.lower() in q_low]

    # ── Decide: stats question vs. text/qualitative question ─────────────────
    text_triggers = ["why", "reason", "requirement", "common", "feedback",
                     "customers say", "what did", "suggest", "complain",
                     "feature", "request", "lost deal", "example", "describe",
                     "purpose", "notes", "summary of", "tell me about"]
    is_text_q = any(t in q_low for t in text_triggers)

    # ── 1. STATS path: pre-computed context → LLM narrates ───────────────────
    if not is_text_q:
        # Build focused stats for the mentioned months (or all)
        if months_mentioned:
            subset = _filter_month(demos, bundle, months_mentioned)
            month_label = "/".join(months_mentioned)
        else:
            subset = demos
            month_label = "all months"

        # Compute focused stats block
        status_col   = next((c for c in subset.columns if c == "Status"), None)
        region_col   = next((c for c in subset.columns if c == "Region"), None)
        industry_col = next((c for c in subset.columns if c == "Industry"), None)
        source_col   = next((c for c in subset.columns if c == "Source"), None)
        rev_col      = next((c for c in subset.columns if c == "Revenue"), None)
        handler_col  = next((c for c in subset.columns if c == "Handled by"), None)

        stat_lines = [f"Dataset: {len(subset)} demo records for {month_label}"]

        if status_col:
            sc = subset[status_col].value_counts()
            won  = sc.get("Deal Won", 0)
            lost = sc.get("Deal Lost", 0)
            prog = sc.get("In Progress", 0)
            rate = round(won / max(len(subset), 1) * 100, 1)
            stat_lines.append(f"Status: Won={won}, Lost={lost}, InProgress={prog}, Rate={rate}%")
            for k, v in sc.items():
                stat_lines.append(f"  {k}: {v}")

        if region_col and status_col:
            stat_lines.append("By Region:")
            for reg, cnt in subset[region_col].value_counts().items():
                rdf = subset[subset[region_col] == reg]
                won_r = len(rdf[rdf[status_col] == "Deal Won"])
                stat_lines.append(f"  {reg}: {cnt} demos, {won_r} won ({round(won_r/max(cnt,1)*100,1)}%)")

        if industry_col:
            top_ind = subset[industry_col].value_counts().head(10)
            stat_lines.append(f"Top Industries: {dict(top_ind)}")

        if source_col:
            stat_lines.append(f"Lead Sources: {dict(subset[source_col].value_counts())}")

        if rev_col:
            rev = pd.to_numeric(subset[rev_col], errors="coerce")
            stat_lines.append(f"Revenue: Total={rev.sum():,.0f}, Avg={rev.mean():,.0f}, Max={rev.max():,.0f}")
            if months_mentioned and bundle.month_col in subset.columns:
                for m in months_mentioned:
                    mdf = subset[subset[bundle.month_col].str.lower() == m.lower()]
                    r_m = pd.to_numeric(mdf[rev_col], errors="coerce").sum()
                    stat_lines.append(f"  Revenue {m}: {r_m:,.0f}")

        if handler_col and status_col:
            stat_lines.append("By Handler:")
            for h, cnt in subset[handler_col].value_counts().items():
                hdf = subset[subset[handler_col] == h]
                won_h = len(hdf[hdf[status_col] == "Deal Won"])
                stat_lines.append(f"  {h}: {cnt} demos, {won_h} won")

        # Month breakdown if asking about all months
        if not months_mentioned and bundle.month_col in subset.columns and status_col:
            stat_lines.append("Monthly breakdown:")
            for month in bundle.months:
                mdf = subset[subset[bundle.month_col] == month]
                if len(mdf) == 0:
                    continue
                won_m = len(mdf[mdf[status_col] == "Deal Won"])
                rate_m = round(won_m / max(len(mdf), 1) * 100, 1)
                stat_lines.append(f"  {month}: {len(mdf)} demos, {won_m} won ({rate_m}%)")

        stats_ctx = "\n".join(stat_lines)

        return llm(
            f"You are a presales analyst assistant. Answer the question using ONLY the stats below. "
            f"Be specific with numbers. Write 2-4 sentences. No bullet points.\n\n"
            f"Stats:\n{stats_ctx}\n\n"
            f"Question: {question}",
            temperature=0.2,
            max_tokens=400,
        )

    # ── 2. TEXT path: RAG over notes/purpose fields ───────────────────────────
    if "_content" in df.columns:
        # Filter to mentioned months first
        if months_mentioned and bundle.month_col in df.columns:
            subset = df[df[bundle.month_col].str.lower().isin([m.lower() for m in months_mentioned])]
        else:
            subset = demos  # only demo rows, not feature/noshow

        # Score rows by keyword relevance
        keywords = [w for w in re.split(r'\W+', q_low) if len(w) > 3
                    and w not in {"what","which","when","were","that","this","with","have","from","they","their"}]
        content = subset["_content"].dropna()

        if keywords and len(content) > 0:
            scores  = content.apply(lambda t: sum(kw in t.lower() for kw in keywords))
            top_idx = scores.nlargest(15).index
            rows    = content.loc[top_idx].tolist()
        else:
            rows = content.head(15).tolist()

        ctx = "\n\n".join(f"[Record {i+1}]\n{r[:600]}" for i, r in enumerate(rows))
        return llm(
            f"You are a presales analyst. Answer the question using ONLY the records below. "
            f"Identify patterns across multiple records. Be specific. No bullet points.\n\n"
            f"Question: {question}\n\n"
            f"Records:\n{ctx}",
            temperature=0.25,
            max_tokens=500,
        )

    return "I couldn't find a relevant answer in the dataset."


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_bundle(file_bytes: bytes, filename: str):
    from dynamic_ingestion import load_file
    return load_file(io.BytesIO(file_bytes), filename)


@st.cache_resource(show_spinner=False)
def load_default_bundle():
    from dynamic_ingestion import load_file
    with open(BASE_DIR / "WD Presales Demo Stats 2026.xlsx", "rb") as f:
        return load_file(f, "WD Presales Demo Stats 2026.xlsx")


@st.cache_data(show_spinner=False)
def load_template(file_bytes: bytes):
    from dynamic_ingestion import parse_template
    return parse_template(io.BytesIO(file_bytes))


def generate_report_bytes(bundle, month: str, template_struct: dict) -> bytes:
    from chart_generator import generate_charts
    from report_generator import (
        _build_js, conversion_stats, repeat_engagement_stats,
        deal_lost_stats, case_breakdown, region_stats, source_stats,
        feature_stats, _cache,
    )
    import subprocess

    df        = bundle.df
    month_col = bundle.month_col
    mdf = df[df[month_col].astype(str).str.capitalize() == month.capitalize()].copy() \
          if month_col and month_col in df.columns else df.copy()

    if mdf.empty:
        raise ValueError(f"No data found for: {month}")

    _cache.update({"df": df, "feature_df": pd.DataFrame(), "noshow_df": pd.DataFrame()})

    tmpl_ctx = ""
    if template_struct.get("sections"):
        tmpl_ctx = f"\nTemplate sections: {', '.join(s['heading'] for s in template_struct['sections'])}"

    def _obs(ctx, instr):
        return llm(
            f"Write 3-4 concise sentences as a report observation paragraph. "
            f"Use numbers from the context. No bullets.{tmpl_ctx}\n\nContext: {ctx}\nInstruction: {instr}",
            max_tokens=220,
        )

    def safe(fn, *a, default={}):
        try: return fn(*a)
        except: return default

    cs   = safe(conversion_stats,        mdf, default={"total_demos": len(mdf), "new_prospects": 0, "already_engaged": 0, "deal_won": 0, "conversion_rate": 0, "in_progress": 0})
    rep  = safe(repeat_engagement_stats, mdf, default={"count": 0, "won": 0, "lost": 0, "in_progress": 0})
    lost = safe(deal_lost_stats,         mdf, default={"rows": [], "total_lost": 0, "loss_rate": 0})
    cb   = safe(case_breakdown,          mdf, default=[])
    reg  = safe(region_stats,            mdf, default=[])
    src  = safe(source_stats,            mdf, default=[])
    feat = safe(feature_stats,           month, default=[])

    top_region = reg[0]["Region"] if reg else "—"
    top_source = src[0]["Source"] if src else "—"
    feat_names = ", ".join(f.get("Feature name", "") for f in feat[:4])

    obs = {
        "summary"       : llm(f"Write a 2-sentence executive summary for a presales report for {month}. "
                              f"Data: {cs['total_demos']} demos, {cs['new_prospects']} new prospects, "
                              f"{cs['deal_won']} deals won, {cs['conversion_rate']}% conversion.{tmpl_ctx}", max_tokens=150),
        "conversion"    : _obs(f"Demos:{cs['total_demos']} Won:{cs['deal_won']} Rate:{cs['conversion_rate']}%", f"Conversion trends for {month}."),
        "repeat"        : _obs(f"Repeat:{rep['count']} Won:{rep['won']} Lost:{rep['lost']}", "Repeat engagement."),
        "lost"          : _obs(f"Lost:{lost['total_lost']} Rate:{lost['loss_rate']}%", "Deal loss patterns."),
        "case"          : _obs(str(cb), "Case mix."),
        "region"        : _obs(str(reg), f"Regional performance, {top_region} leads."),
        "source"        : _obs(str(src[:6]), f"Lead sources, '{top_source}' is primary."),
        "feature_intro" : f"Top feature requests discussed during {month} 2026.",
        "features"      : _obs(f"Top features: {feat_names}", "Feature demand trends."),
    }

    chart_dir = tempfile.mkdtemp()
    charts    = generate_charts(mdf, month, chart_dir)

    stats  = {"conversion": cs, "repeat": rep, "lost": lost,
               "case_breakdown": cb, "region": reg, "source": src,
               "features": feat, "observations": obs}
    out    = os.path.join(tempfile.mkdtemp(), f"Report_{month}.docx")
    js     = _build_js(month, stats, out, charts=charts)

    tmp    = Path(tempfile.mkdtemp())
    (tmp / "report.js").write_text(js)
    (tmp / "node_modules").symlink_to(BASE_DIR / "node_modules")

    r = subprocess.run(["node", str(tmp / "report.js")], capture_output=True, text=True)
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(chart_dir, ignore_errors=True)

    if r.returncode != 0:
        raise RuntimeError(r.stderr or r.stdout)

    data = open(out, "rb").read()
    os.unlink(out)
    return data


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style="padding:16px 0 8px">
        <div class="logo-text">🧠 Presales AI</div>
        <div class="logo-sub">OFFLINE INTELLIGENCE PLATFORM</div>
    </div>
    """, unsafe_allow_html=True)

    # Ollama status
    alive = ollama_ok()
    status_html = (
        '<span class="badge badge-green">● OLLAMA ONLINE</span>' if alive
        else '<span class="badge badge-red">● OLLAMA OFFLINE</span>'
    )
    st.markdown(status_html, unsafe_allow_html=True)
    if not alive:
        st.caption("Run `ollama serve` in Terminal")

    st.markdown("---")

    # ── Dataset ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Dataset</div>', unsafe_allow_html=True)
    dataset_file = st.file_uploader("Upload Excel / CSV", type=["xlsx","xls","csv"],
                                     label_visibility="collapsed")
    use_default = st.checkbox("Use default WD Presales dataset",
                               value=(dataset_file is None))

    st.markdown("---")

    # ── Template ──────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Reference Template</div>', unsafe_allow_html=True)
    st.caption("Upload a sample .docx — the AI learns its structure")
    template_file = st.file_uploader("Upload .docx template", type=["docx"],
                                      label_visibility="collapsed")

    st.markdown("---")
    st.markdown('<div style="font-size:11px;color:#8B92A5">v1.0 · Built with Llama 3.1 8B<br>All data stays on your machine</div>',
                unsafe_allow_html=True)


# ── Load ──────────────────────────────────────────────────────────────────────

with st.spinner("Loading dataset…"):
    if dataset_file is not None:
        bundle = load_bundle(dataset_file.read(), dataset_file.name)
    elif use_default:
        try:
            bundle = load_default_bundle()
        except Exception as e:
            st.error(f"Default dataset not found: {e}")
            st.stop()
    else:
        st.markdown("""
        <div style="text-align:center;padding:80px 20px;color:#8B92A5">
            <div style="font-size:48px">📂</div>
            <div style="font-size:18px;font-weight:600;margin-top:16px;color:#E8EAF0">Upload a dataset to begin</div>
            <div style="margin-top:8px">Use the sidebar to upload an Excel or CSV file</div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

template_struct = {"title": "Report", "sections": [], "raw_text": ""}
if template_file is not None:
    template_struct = load_template(template_file.read())

fname = dataset_file.name if dataset_file else "WD Presales Demo Stats 2026.xlsx"


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════

df = bundle.df

# Derive key KPIs
status_col = next((c for c in df.columns if c.lower() == "status"), None)
won  = len(df[df[status_col] == "Deal Won"])  if status_col else 0
lost = len(df[df[status_col] == "Deal Lost"]) if status_col else 0
prog = len(df[df[status_col] == "In Progress"]) if status_col else 0
rate = round(won / max(len(df), 1) * 100, 1)

header_col, badge_col = st.columns([3, 1])
with header_col:
    st.markdown(f"""
    <div style="padding:8px 0 20px">
        <div style="font-size:26px;font-weight:700;color:#E8EAF0">
            Presales Intelligence Dashboard
        </div>
        <div style="font-size:13px;color:#8B92A5;margin-top:4px">
            📁 {fname} &nbsp;·&nbsp; {len(df):,} records &nbsp;·&nbsp;
            {len(bundle.months)} months
        </div>
    </div>
    """, unsafe_allow_html=True)

with badge_col:
    if template_struct["sections"]:
        st.markdown(
            f'<div class="template-bar" style="margin-top:8px">📄 Template: '
            f'<b>{len(template_struct["sections"])} sections</b></div>',
            unsafe_allow_html=True,
        )

# KPI row
k1, k2, k3, k4, k5 = st.columns(5)
kpis = [
    (str(len(df)), "Total Records",     None),
    (str(won),     "Deals Won",         "badge-green"),
    (str(lost),    "Deals Lost",        "badge-red"),
    (str(prog),    "In Progress",       "badge-yellow"),
    (f"{rate}%",   "Conversion Rate",   "badge-blue"),
]
for col, (val, label, badge) in zip([k1,k2,k3,k4,k5], kpis):
    col.markdown(f"""
    <div class="metric-card">
        <div class="value">{val}</div>
        <div class="label">{label}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════════

tab_qa, tab_report, tab_data = st.tabs([
    "💬  Ask Questions",
    "📝  Generate Report",
    "📊  Data Overview",
])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Q&A
# ─────────────────────────────────────────────────────────────────────────────

with tab_qa:
    st.markdown('<div class="section-header">Ask anything about your data</div>', unsafe_allow_html=True)

    # Suggestions
    suggestions = [
        "What is the overall conversion rate?",
        "Top 5 industries by deal count",
        "Which region has the most deal wins?",
        "What were common enterprise requirements?",
        "Revenue breakdown by month",
        "Why do deals get lost?",
    ]
    st.markdown("**Quick questions:**")
    s_cols = st.columns(3)
    for i, s in enumerate(suggestions):
        if s_cols[i % 3].button(s, key=f"sug_{i}", use_container_width=True):
            if "pending_question" not in st.session_state:
                st.session_state.pending_question = s

    st.markdown("---")

    # Chat history
    if "chat" not in st.session_state:
        st.session_state.chat = []

    for entry in st.session_state.chat:
        st.markdown(f'<div class="user-msg">🙋 {entry["q"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-msg"><div class="ai-msg-header">🧠 Presales AI</div>{entry["a"]}</div>', unsafe_allow_html=True)

    # Input
    q = st.chat_input("Ask about your dataset…")
    if not q and "pending_question" in st.session_state:
        q = st.session_state.pop("pending_question")

    if q:
        if not alive:
            st.error("Ollama is offline. Start it with `ollama serve`.")
        else:
            st.markdown(f'<div class="user-msg">🙋 {q}</div>', unsafe_allow_html=True)
            with st.spinner(""):
                ans = answer_question(q, bundle)
            st.markdown(f'<div class="ai-msg"><div class="ai-msg-header">🧠 Presales AI</div>{ans}</div>', unsafe_allow_html=True)
            st.session_state.chat.append({"q": q, "a": ans})

    if st.session_state.chat:
        if st.button("🗑 Clear history", key="clr"):
            st.session_state.chat = []
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — REPORT GENERATION
# ─────────────────────────────────────────────────────────────────────────────

with tab_report:
    left, right = st.columns([1, 2], gap="large")

    with left:
        st.markdown('<div class="section-header">Report Settings</div>', unsafe_allow_html=True)

        month_opts = [str(m) for m in bundle.months if str(m).lower() != "nan"] \
                     if bundle.months else \
                     ["January","February","March","April","May","June",
                      "July","August","September","October","November","December"]

        sel_month = st.selectbox("Month", month_opts, label_visibility="visible")

        if template_struct["sections"]:
            sec_names = [s["heading"] for s in template_struct["sections"]]
            st.markdown(f"""
            <div class="template-bar">
                📄 Template loaded<br>
                <span style="font-size:11px;opacity:0.8">{" · ".join(sec_names[:3])}{"…" if len(sec_names)>3 else ""}</span>
            </div>
            """, unsafe_allow_html=True)

        gen_btn = st.button("🚀 Generate Report", type="primary", use_container_width=True)

    with right:
        st.markdown('<div class="section-header">Report Contents</div>', unsafe_allow_html=True)
        sections_info = [
            ("📊", "Conversion Performance", "Table + Deal Won/Lost chart"),
            ("🔄", "Repeat Engagement",       "Repeat prospects + Deal Size Distribution"),
            ("📉", "Deal Lost Analysis",       "Loss categories table + Status donut"),
            ("🗂", "Case Breakdown",           "New vs repeat vs existing org"),
            ("🌍", "Region-Wise Performance",  "Table + grouped bar chart"),
            ("🔗", "Lead Source Analysis",     "Source table + horizontal bar chart"),
            ("⚙️", "Feature Demand",           "Top requested features table"),
            ("✍️", "LLM Observations",         "AI-written insights for each section"),
        ]
        for icon, title, desc in sections_info:
            st.markdown(f"""
            <div style="display:flex;align-items:flex-start;gap:12px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06)">
                <span style="font-size:18px;line-height:1.4">{icon}</span>
                <div>
                    <div style="font-size:13px;font-weight:600;color:#E8EAF0">{title}</div>
                    <div style="font-size:11px;color:#8B92A5;margin-top:2px">{desc}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    if gen_btn:
        if not alive:
            st.error("Ollama is offline. Start it with `ollama serve`.")
        else:
            prog_bar = st.progress(0)
            status_el = st.empty()

            steps = [
                (15, "📊 Computing statistics…"),
                (35, "📊 Generating charts…"),
                (60, "✍️ Writing AI observations (30–60 sec)…"),
                (85, "📝 Building document…"),
                (100, "✅ Done!"),
            ]
            try:
                for pct, msg in steps[:-1]:
                    prog_bar.progress(pct, text=msg)
                    status_el.info(msg)

                docx_bytes = generate_report_bytes(bundle, sel_month, template_struct)

                prog_bar.progress(100, text="✅ Done!")
                status_el.success(f"Report ready — {len(docx_bytes)//1024} KB")

                st.download_button(
                    label     = f"⬇️  Download Presales Report – {sel_month} 2026.docx",
                    data      = docx_bytes,
                    file_name = f"Presales_Report_{sel_month}_2026.docx",
                    mime      = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type      = "primary",
                    use_container_width = True,
                )
            except Exception as e:
                prog_bar.empty()
                status_el.error(f"Generation failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — DATA OVERVIEW
# ─────────────────────────────────────────────────────────────────────────────

with tab_data:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor" : "#161B27",
        "axes.facecolor"   : "#161B27",
        "axes.edgecolor"   : "#2D3748",
        "axes.labelcolor"  : "#8B92A5",
        "xtick.color"      : "#8B92A5",
        "ytick.color"      : "#8B92A5",
        "text.color"       : "#E8EAF0",
        "grid.color"       : "#2D3748",
        "grid.linestyle"   : "--",
        "grid.linewidth"   : 0.6,
        "font.family"      : "DejaVu Sans",
    })

    # ── Column detection ──────────────────────────────────────────────────────
    region_col   = next((c for c in df.columns if c == "Region"), None)
    industry_col = next((c for c in df.columns if c == "Industry"), None)
    source_col   = next((c for c in df.columns if c == "Source"), None)
    handler_col  = next((c for c in df.columns if c == "Handled by"), None)

    ACCENT  = "#4F8EF7"
    GREEN   = "#10B981"
    RED     = "#EF4444"
    ORANGE  = "#F59E0B"
    PALETTE = [ACCENT, GREEN, ORANGE, RED, "#8B5CF6", "#06B6D4", "#EC4899", "#84CC16"]

    # ── FILTER BAR ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">Dashboard Filters</div>', unsafe_allow_html=True)

    # Work only with demo months (exclude feature/noshow sheets)
    demo_base = _demo_df(df, bundle)

    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 2, 2, 1])

    with fcol1:
        all_months = [m for m in MONTH_ORDER if m in bundle.months]
        sel_months = st.multiselect(
            "Month", all_months, default=all_months,
            placeholder="All months", key="ov_months"
        )

    with fcol2:
        if status_col:
            all_statuses = sorted(demo_base[status_col].dropna().unique().tolist())
            sel_statuses = st.multiselect(
                "Status", all_statuses, default=all_statuses,
                placeholder="All statuses", key="ov_status"
            )
        else:
            sel_statuses = []

    with fcol3:
        if region_col:
            all_regions = sorted(demo_base[region_col].dropna().unique().tolist())
            sel_regions = st.multiselect(
                "Region", all_regions, default=all_regions,
                placeholder="All regions", key="ov_region"
            )
        else:
            sel_regions = []

    with fcol4:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("↺ Reset", key="ov_reset", use_container_width=True):
            for k in ["ov_months","ov_status","ov_region"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    # Apply filters
    fdf = demo_base.copy()
    if sel_months and bundle.month_col in fdf.columns:
        fdf = fdf[fdf[bundle.month_col].isin(sel_months)]
    if sel_statuses and status_col:
        fdf = fdf[fdf[status_col].isin(sel_statuses)]
    if sel_regions and region_col:
        fdf = fdf[fdf[region_col].isin(sel_regions)]

    # KPI mini row for filtered slice
    f_won  = len(fdf[fdf[status_col] == "Deal Won"])  if status_col else 0
    f_lost = len(fdf[fdf[status_col] == "Deal Lost"]) if status_col else 0
    f_prog = len(fdf[fdf[status_col] == "In Progress"]) if status_col else 0
    f_rate = round(f_won / max(len(fdf), 1) * 100, 1)

    mk1, mk2, mk3, mk4, mk5 = st.columns(5)
    for col_w, (val, lbl) in zip(
        [mk1, mk2, mk3, mk4, mk5],
        [(str(len(fdf)),"Filtered Records"),(str(f_won),"Won"),
         (str(f_lost),"Lost"),(str(f_prog),"In Progress"),(f"{f_rate}%","Conv. Rate")]
    ):
        col_w.markdown(
            f'<div class="metric-card" style="padding:12px 16px">'
            f'<div class="value" style="font-size:22px">{val}</div>'
            f'<div class="label" style="font-size:10px">{lbl}</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── CHARTS ────────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2, gap="medium")

    # Chart 1 — Status breakdown
    with c1:
        st.markdown('<div class="section-header">Status Breakdown</div>', unsafe_allow_html=True)
        if status_col and not fdf.empty:
            sc = fdf[status_col].value_counts().head(7)
            fig, ax = plt.subplots(figsize=(5, 3.4))
            colors = [GREEN if "Won" in k else RED if "Lost" in k else ACCENT for k in sc.index]
            bars = ax.barh(sc.index[::-1], sc.values[::-1], color=colors[::-1], height=0.6)
            for bar, val in zip(bars, sc.values[::-1]):
                ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                        str(val), va="center", ha="left", fontsize=9, color="#E8EAF0")
            ax.set_xlim(0, sc.max() * 1.25)
            ax.set_xlabel("Count", fontsize=9)
            ax.tick_params(labelsize=9)
            ax.xaxis.grid(True); ax.set_axisbelow(True)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True); plt.close(fig)

    # Chart 2 — Region Won vs Lost
    with c2:
        st.markdown('<div class="section-header">Region: Won vs Lost</div>', unsafe_allow_html=True)
        if region_col and status_col and not fdf.empty:
            rw = fdf[fdf[status_col] == "Deal Won"].groupby(region_col).size()
            rl = fdf[fdf[status_col] == "Deal Lost"].groupby(region_col).size()
            regions = sorted(set(rw.index) | set(rl.index))
            x = range(len(regions))
            fig, ax = plt.subplots(figsize=(5, 3.4))
            ax.bar([i - 0.2 for i in x], [rw.get(r, 0) for r in regions],
                   0.35, label="Won", color=GREEN, alpha=0.9)
            ax.bar([i + 0.2 for i in x], [rl.get(r, 0) for r in regions],
                   0.35, label="Lost", color=RED, alpha=0.9)
            ax.set_xticks(list(x)); ax.set_xticklabels(regions, fontsize=8, rotation=20)
            ax.legend(fontsize=9, framealpha=0.2)
            ax.yaxis.grid(True); ax.set_axisbelow(True)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True); plt.close(fig)

    c3, c4 = st.columns(2, gap="medium")

    # Chart 3 — Industry
    with c3:
        st.markdown('<div class="section-header">Top Industries</div>', unsafe_allow_html=True)
        if industry_col and not fdf.empty:
            ic = fdf[industry_col].value_counts().head(10)
            fig, ax = plt.subplots(figsize=(5, 3.4))
            cols_i = [PALETTE[i % len(PALETTE)] for i in range(len(ic))]
            ax.barh(ic.index[::-1], ic.values[::-1], color=cols_i[::-1], height=0.6)
            ax.set_xlabel("Count", fontsize=9)
            ax.tick_params(labelsize=8)
            ax.xaxis.grid(True); ax.set_axisbelow(True)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True); plt.close(fig)

    # Chart 4 — Monthly trend (always shows all months for context, highlights filter)
    with c4:
        st.markdown('<div class="section-header">Monthly Volume Trend</div>', unsafe_allow_html=True)
        if bundle.month_col and bundle.month_col in demo_base.columns:
            mc_all = demo_base.groupby(bundle.month_col).size()
            mc_sel = fdf.groupby(bundle.month_col).size() if bundle.month_col in fdf.columns else pd.Series()
            ordered = [m for m in MONTH_ORDER if m in mc_all.index]
            mc_all  = mc_all.reindex(ordered).fillna(0)
            mc_sel  = mc_sel.reindex(ordered).fillna(0)
            fig, ax = plt.subplots(figsize=(5, 3.4))
            ax.fill_between(range(len(ordered)), mc_all.values, alpha=0.08, color=ACCENT)
            ax.plot(range(len(ordered)), mc_all.values, color=ACCENT, linewidth=1.5,
                    linestyle="--", label="All", alpha=0.5)
            ax.plot(range(len(ordered)), mc_sel.values, color=GREEN, linewidth=2.5,
                    marker="o", markersize=6, markerfacecolor="#161B27",
                    markeredgecolor=GREEN, markeredgewidth=2, label="Filtered")
            ax.set_xticks(range(len(ordered)))
            ax.set_xticklabels(ordered, rotation=30, fontsize=8)
            ax.legend(fontsize=9, framealpha=0.2)
            ax.yaxis.grid(True); ax.set_axisbelow(True)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True); plt.close(fig)

    # Chart 5 — Source breakdown
    if source_col and not fdf.empty:
        st.markdown('<div class="section-header">Lead Source Breakdown</div>', unsafe_allow_html=True)
        src_data = fdf[source_col].value_counts()
        fig, ax = plt.subplots(figsize=(10, 2.8))
        cols_s = [PALETTE[i % len(PALETTE)] for i in range(len(src_data))]
        ax.barh(src_data.index[::-1], src_data.values[::-1], color=cols_s[::-1], height=0.5)
        for i, (idx, val) in enumerate(zip(src_data.index[::-1], src_data.values[::-1])):
            ax.text(val + 0.3, i, str(val), va="center", fontsize=9, color="#E8EAF0")
        ax.set_xlim(0, src_data.max() * 1.2)
        ax.set_xlabel("Count", fontsize=9)
        ax.tick_params(labelsize=9)
        ax.xaxis.grid(True); ax.set_axisbelow(True)
        plt.tight_layout()
        st.pyplot(fig, use_container_width=True); plt.close(fig)

    # Chart 6 — Handler performance (if multiple handlers)
    if handler_col and status_col and not fdf.empty and fdf[handler_col].nunique() > 1:
        st.markdown('<div class="section-header">Handler Performance</div>', unsafe_allow_html=True)
        h_won  = fdf[fdf[status_col] == "Deal Won"].groupby(handler_col).size()
        h_lost = fdf[fdf[status_col] == "Deal Lost"].groupby(handler_col).size()
        handlers = sorted(set(h_won.index) | set(h_lost.index))
        x = range(len(handlers))
        fig, ax = plt.subplots(figsize=(10, 3))
        ax.bar([i - 0.2 for i in x], [h_won.get(h, 0) for h in handlers],
               0.35, label="Won", color=GREEN, alpha=0.9)
        ax.bar([i + 0.2 for i in x], [h_lost.get(h, 0) for h in handlers],
               0.35, label="Lost", color=RED, alpha=0.9)
        ax.set_xticks(list(x)); ax.set_xticklabels(handlers, fontsize=9, rotation=20)
        ax.legend(fontsize=9, framealpha=0.2)
        ax.yaxis.grid(True); ax.set_axisbelow(True)
        plt.tight_layout()
        st.pyplot(fig, use_container_width=True); plt.close(fig)

    st.markdown("---")

    # ── DATA TABLE ────────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        st.markdown('<div class="section-header">Data Table</div>', unsafe_allow_html=True)
    with col_b:
        show_all = st.toggle("Show all columns", value=False)
    with col_c:
        st.caption(f"{len(fdf):,} rows shown")

    display_cols = (fdf.columns.tolist() if show_all
                    else [c for c in ["_sheet","Status","Region","Industry","Source",
                                      "Handled by","Engagement Type","Deal Size","Revenue"]
                          if c in fdf.columns])
    st.dataframe(fdf[display_cols].reset_index(drop=True),
                 use_container_width=True, height=320)

    with st.expander("Column Classification"):
        cc1, cc2 = st.columns(2)
        cc1.markdown("**Structured** (analytics)")
        for c in bundle.structured:
            cc1.markdown(f"<span class='badge badge-blue'>{c}</span>", unsafe_allow_html=True)
        cc2.markdown("**Text** (Q&A / RAG)")
        for c in bundle.text_cols:
            cc2.markdown(f"<span class='badge badge-yellow'>{c}</span>", unsafe_allow_html=True)
