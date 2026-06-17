"""
chart_generator.py
------------------
Generates chart PNGs for the presales report using matplotlib.

Charts produced per month:
  1. deal_won_lost.png       — vertical bar: Deal Won vs Deal Lost
  2. deal_size_dist.png      — horizontal bar: deal size band distribution
  3. region_performance.png  — horizontal bar: total deals by region
  4. source_breakdown.png    — horizontal bar: lead source counts
  5. status_breakdown.png    — donut chart: all status categories

Usage:
    from chart_generator import generate_charts
    paths = generate_charts(month_df, month="April", out_dir="/tmp/charts_april")
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from typing import Optional

# ── Style ────────────────────────────────────────────────────────────────────

BLUE    = "#2E75B6"
GREEN   = "#70AD47"
RED     = "#FF7070"
ORANGE  = "#ED7D31"
PURPLE  = "#7030A0"
YELLOW  = "#FFC000"
GREY    = "#A6A6A6"
PALETTE = [BLUE, GREEN, ORANGE, YELLOW, PURPLE, RED, GREY,
           "#4BACC6", "#F79646", "#9DC3E6"]

plt.rcParams.update({
    "font.family"       : "DejaVu Sans",
    "axes.spines.top"   : False,
    "axes.spines.right" : False,
    "axes.grid"         : True,
    "grid.color"        : "#E5E5E5",
    "grid.linestyle"    : "-",
    "grid.linewidth"    : 0.8,
    "figure.dpi"        : 150,
})


# ── 1. Deal Won / Lost ────────────────────────────────────────────────────────

def chart_deal_won_lost(mdf: pd.DataFrame, month: str, out_path: str) -> str:
    won  = len(mdf[mdf["Status"] == "Deal Won"])
    lost = len(mdf[mdf["Status"] == "Deal Lost"])

    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(["Deal Won", "Deal Lost"], [won, lost],
                  color=[GREEN, RED], width=0.45, zorder=3)

    for bar, val in zip(bars, [won, lost]):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5, str(val),
                ha="center", va="bottom", fontsize=13, fontweight="bold")

    ax.set_title(f"{month} Deal Won/Lost", fontsize=14, fontweight="bold", pad=12)
    ax.set_ylabel("Count", fontsize=10)
    ax.set_ylim(0, max(won, lost) * 1.25)
    ax.tick_params(axis="x", labelsize=11)
    ax.tick_params(axis="y", labelsize=9)
    ax.yaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)

    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# ── 2. Deal Size Distribution ────────────────────────────────────────────────

def chart_deal_size_dist(mdf: pd.DataFrame, month: str, out_path: str) -> str:
    def band(val):
        try:
            v = float(str(val).split("-")[0].split("+")[0].strip())
            if v <= 10:   return "1-10"
            if v <= 50:   return "11-50"
            if v <= 100:  return "51-100"
            if v <= 500:  return "101-500"
            if v <= 1000: return "501-1000"
            return "1000+"
        except Exception:
            return "Not Confirmed"

    bands_order = ["1-10", "11-50", "51-100", "101-500", "501-1000", "1000+", "Not Confirmed"]
    counts = mdf["Deal Size"].apply(band).value_counts()
    counts = counts.reindex(bands_order, fill_value=0)
    counts = counts[counts > 0]

    colors = [BLUE, GREEN, YELLOW, ORANGE, PURPLE, RED, GREY][:len(counts)]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.barh(counts.index[::-1], counts.values[::-1],
                   color=colors[::-1], height=0.55, zorder=3)

    for bar, val in zip(bars, counts.values[::-1]):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", fontsize=10, fontweight="bold")

    ax.set_title("Deal Size Distribution", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Count", fontsize=10)
    ax.set_xlim(0, counts.max() * 1.2)
    ax.tick_params(axis="y", labelsize=10)
    ax.tick_params(axis="x", labelsize=9)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)

    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# ── 3. Region Performance ────────────────────────────────────────────────────

def chart_region_performance(mdf: pd.DataFrame, month: str, out_path: str) -> str:
    reg = mdf.groupby("Region").agg(
        Won=("Status", lambda x: (x == "Deal Won").sum()),
        Lost=("Status", lambda x: (x == "Deal Lost").sum()),
        Total=("Status", "count"),
    ).sort_values("Total", ascending=True)

    fig, ax = plt.subplots(figsize=(5, 3.5))
    y = range(len(reg))
    ax.barh([i + 0.2 for i in y], reg["Won"],  height=0.35, color=GREEN,  label="Won",  zorder=3)
    ax.barh([i - 0.2 for i in y], reg["Lost"], height=0.35, color=RED,    label="Lost", zorder=3)
    ax.set_yticks(list(y))
    ax.set_yticklabels(reg.index, fontsize=10)
    ax.set_title("Region-Wise Performance", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Count", fontsize=10)
    ax.legend(fontsize=9)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)

    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# ── 4. Lead Source Breakdown ─────────────────────────────────────────────────

def chart_source_breakdown(mdf: pd.DataFrame, month: str, out_path: str) -> str:
    src = mdf["Source"].value_counts().head(6)
    # Shorten long labels
    labels = [s[:35] + "…" if len(s) > 35 else s for s in src.index]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    ax.barh(labels[::-1], src.values[::-1],
            color=PALETTE[:len(src)][::-1], height=0.55, zorder=3)

    for i, (lbl, val) in enumerate(zip(labels[::-1], src.values[::-1])):
        ax.text(val + 0.2, i, str(val), va="center", ha="left",
                fontsize=10, fontweight="bold")

    ax.set_title("Lead Source Breakdown", fontsize=14, fontweight="bold", pad=12)
    ax.set_xlabel("Count", fontsize=10)
    ax.set_xlim(0, src.max() * 1.25)
    ax.tick_params(axis="y", labelsize=9)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)

    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# ── 5. Status Donut ──────────────────────────────────────────────────────────

def chart_status_donut(mdf: pd.DataFrame, month: str, out_path: str) -> str:
    status = mdf["Status"].value_counts()
    # Keep top 6, group rest as "Other"
    if len(status) > 6:
        top   = status.head(6)
        other = pd.Series({"Other": status.iloc[6:].sum()})
        status = pd.concat([top, other])

    colors = PALETTE[:len(status)]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    wedges, texts, autotexts = ax.pie(
        status.values,
        labels=None,
        autopct=lambda p: f"{p:.1f}%" if p > 4 else "",
        colors=colors,
        startangle=140,
        wedgeprops={"width": 0.55},   # donut
        pctdistance=0.75,
    )
    for t in autotexts:
        t.set_fontsize(8)
        t.set_fontweight("bold")

    legend_labels = [f"{k} ({v})" for k, v in status.items()]
    ax.legend(legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.22),
              ncol=2, fontsize=8, frameon=False)
    ax.set_title(f"Status Breakdown", fontsize=14, fontweight="bold", pad=12)

    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# ── Master function ──────────────────────────────────────────────────────────

def generate_charts(mdf: pd.DataFrame, month: str, out_dir: Optional[str] = None) -> dict:
    """
    Generate all charts for the given month DataFrame.

    Returns
    -------
    dict of { chart_name: absolute_path_to_png }
    """
    if out_dir is None:
        import tempfile
        out_dir = tempfile.mkdtemp(prefix=f"charts_{month.lower()}_")
    os.makedirs(out_dir, exist_ok=True)

    paths = {}
    jobs = [
        ("deal_won_lost",        chart_deal_won_lost,        "deal_won_lost.png"),
        ("deal_size_dist",       chart_deal_size_dist,       "deal_size_dist.png"),
        ("region_performance",   chart_region_performance,   "region_performance.png"),
        ("source_breakdown",     chart_source_breakdown,     "source_breakdown.png"),
        ("status_donut",         chart_status_donut,         "status_donut.png"),
    ]
    for key, fn, fname in jobs:
        p = os.path.join(out_dir, fname)
        fn(mdf, month, p)
        paths[key] = p
        print(f"  📊 {key} → {p}")

    return paths


# ── CLI test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from data_ingestion import load_data

    base  = Path("/Users/sakthi-3766/Claude/Projects/Local SLM")
    df, _, _, _ = load_data(str(base / "WD Presales Demo Stats 2026.xlsx"))

    month = sys.argv[1] if len(sys.argv) > 1 else "April"
    mdf   = df[df["month"] == month]
    out   = str(base / f"charts_{month.lower()}")

    print(f"Generating charts for {month}…")
    paths = generate_charts(mdf, month, out)
    print(f"\n✅ {len(paths)} charts saved to {out}/")
