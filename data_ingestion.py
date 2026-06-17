"""
data_ingestion.py
-----------------
Step 2: Load the presales Excel workbook and produce two clean artifacts:
  1. structured_df  – numeric / categorical columns ready for Pandas queries
  2. text_df        – free-text columns that will be embedded for RAG

Usage:
    from data_ingestion import load_data
    structured_df, text_df, feature_df, noshow_df = load_data()
"""

import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# ── Column taxonomy ──────────────────────────────────────────────────────────

MONTHLY_SHEETS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

# Columns suitable for Pandas aggregation / filtering
STRUCTURED_COLS = [
    "month",            # added during load
    "Date",
    "Region",
    "Handled by",
    "Email address",
    "Industry",
    "Ticket ID",
    "Source",
    "Engagement Type",
    "Trial sign up",
    "Status",
    "Deal Size",
    "Revenue",
    "Suggested/purchased edition",
    "Follow up stages",
    "PSE Creation",
    "Current Platform",
    "Existing data size",
]

# Columns with free text → will be embedded for RAG
TEXT_COLS = [
    "month",            # kept for filtering context
    "Ticket ID",        # anchor for joining back to structured data
    "Purpose",
    "New requirements",
    "Notes",
    "Sales Notes from CRM",
    "Demo Recording",
    "Sprint link",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clean_revenue(val):
    """Coerce Revenue to float; handle strings like '15,000' or blanks."""
    if pd.isna(val):
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except ValueError:
        return None


def _clean_deal_size(val):
    """
    Deal Size is sometimes a raw integer, sometimes a range string like '10-15'.
    Return the lower bound as int for ordering / filtering.
    """
    if pd.isna(val):
        return None
    s = str(val).strip()
    try:
        return int(float(s))
    except ValueError:
        # e.g. "10-15" → take first number
        part = s.split("-")[0].split("+")[0].strip()
        try:
            return int(float(part))
        except ValueError:
            return None


# ── Main loader ──────────────────────────────────────────────────────────────

def load_data(filepath: str = "WD Presales Demo Stats 2026.xlsx"):
    """
    Returns
    -------
    structured_df : pd.DataFrame   – clean, typed, categorical columns
    text_df       : pd.DataFrame   – free-text columns for RAG embedding
    feature_df    : pd.DataFrame   – feature requests sheet
    noshow_df     : pd.DataFrame   – no-show stats sheet
    """
    xl = pd.ExcelFile(filepath)

    monthly_frames = []
    for sheet in MONTHLY_SHEETS:
        if sheet not in xl.sheet_names:
            continue
        df = xl.parse(sheet, parse_dates=["Date"])
        if df.empty:
            continue
        df["month"] = sheet
        monthly_frames.append(df)

    if not monthly_frames:
        raise ValueError("No monthly data found in the workbook.")

    raw = pd.concat(monthly_frames, ignore_index=True)

    # Normalise column names (strip whitespace)
    raw.columns = [c.strip() for c in raw.columns]

    # Handle June's extra "Source.1" duplicate column
    if "Source.1" in raw.columns:
        raw.drop(columns=["Source.1"], inplace=True)

    # ── Structured DataFrame ─────────────────────────────────────────────────
    avail_struct = [c for c in STRUCTURED_COLS if c in raw.columns]
    structured_df = raw[avail_struct].copy()

    structured_df["Revenue"]   = structured_df["Revenue"].apply(_clean_revenue) \
                                    if "Revenue" in structured_df.columns else None
    structured_df["deal_size_lower"] = structured_df["Deal Size"].apply(_clean_deal_size) \
                                    if "Deal Size" in structured_df.columns else None

    # Normalise text categoricals
    for col in ["Region", "Status", "Engagement Type", "Source", "Industry"]:
        if col in structured_df.columns:
            structured_df[col] = structured_df[col].astype(str).str.strip()

    # ── Text DataFrame ───────────────────────────────────────────────────────
    avail_text = [c for c in TEXT_COLS if c in raw.columns]
    text_df = raw[avail_text].copy()

    # Merge text columns into a single "content" field for embedding
    text_fields = [c for c in ["Purpose", "New requirements", "Notes",
                                "Sales Notes from CRM", "Demo Recording"]
                   if c in text_df.columns]

    text_df["content"] = text_df[text_fields].apply(
        lambda row: "\n".join(
            f"{col}: {val}"
            for col, val in row.items()
            if pd.notna(val) and str(val).strip() not in ("", "nan", "NaN")
        ),
        axis=1,
    )
    # Drop rows where there's nothing to embed
    text_df = text_df[text_df["content"].str.strip() != ""].copy()

    # ── Feature Requests ─────────────────────────────────────────────────────
    feature_df = pd.DataFrame()
    if "Feature Requests" in xl.sheet_names:
        feature_df = xl.parse("Feature Requests")
        feature_df.columns = [c.strip() for c in feature_df.columns]

    # ── No-Show Stats ────────────────────────────────────────────────────────
    noshow_df = pd.DataFrame()
    if "No Show Stats" in xl.sheet_names:
        noshow_df = xl.parse("No Show Stats", parse_dates=["Date"])
        noshow_df.columns = [c.strip() for c in noshow_df.columns]

    print(f"✅ Loaded {len(structured_df)} records across "
          f"{structured_df['month'].nunique()} months")
    print(f"   Structured columns : {list(structured_df.columns)}")
    print(f"   Text rows for RAG  : {len(text_df)}")
    print(f"   Feature requests   : {len(feature_df)}")
    print(f"   No-show records    : {len(noshow_df)}")

    return structured_df, text_df, feature_df, noshow_df


if __name__ == "__main__":
    import os, sys
    # Allow running from any directory
    base = "/Users/sakthi-3766/Claude/Projects/Local SLM"
    filepath = os.path.join(base, "WD Presales Demo Stats 2026.xlsx")
    structured_df, text_df, feature_df, noshow_df = load_data(filepath)

    print("\n── Structured sample ──")
    print(structured_df.head(3).to_string())

    print("\n── Text/RAG sample ──")
    print(text_df[["month", "Ticket ID", "content"]].head(2).to_string())

    print("\n── Status breakdown ──")
    print(structured_df["Status"].value_counts())

    print("\n── Region breakdown ──")
    print(structured_df["Region"].value_counts())
