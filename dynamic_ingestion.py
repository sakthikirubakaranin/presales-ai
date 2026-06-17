"""
dynamic_ingestion.py
--------------------
Flexible data loader that works with ANY Excel or CSV file.
Auto-detects column types, sheet structure, and builds a schema
description for the LLM — no hardcoded column names needed.

Returns:
  DataBundle — a named container with:
    .df          : combined DataFrame (all data rows)
    .sheets      : dict of {sheet_name: DataFrame} for Excel files
    .structured  : columns suitable for Pandas queries
    .text_cols   : columns suitable for RAG embedding
    .schema_desc : human-readable schema string sent to the LLM
    .months      : list of detected month values (if any date/month column exists)
    .month_col   : name of the month column (or None)
"""

import io
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

MONTH_NAMES = [
    "january","february","march","april","may","june",
    "july","august","september","october","november","december",
]

# Columns that are almost certainly IDs/links — skip from both layers
SKIP_PATTERNS = ["link", "url", "sprint", "recording", "http"]


@dataclass
class DataBundle:
    df          : pd.DataFrame
    sheets      : dict
    structured  : list          # column names
    text_cols   : list          # column names
    schema_desc : str
    months      : list
    month_col   : Optional[str] = None


def _is_text_col(series: pd.Series, name: str) -> bool:
    """True if column looks like free-running text (not a short categorical)."""
    name_l = name.lower()
    if any(p in name_l for p in SKIP_PATTERNS):
        return False
    if series.dtype != object:
        return False
    avg_len = series.dropna().astype(str).str.len().mean()
    n_unique = series.nunique()
    n_total  = len(series.dropna())
    # High average length OR very high cardinality → text
    return avg_len > 40 or (n_unique > n_total * 0.6 and n_unique > 20)


def _is_structured_col(series: pd.Series, name: str) -> bool:
    """True if column is categorical, numeric, or date — good for Pandas queries."""
    if series.dtype in ["int64", "float64", "datetime64[ns]"]:
        return True
    if series.dtype == object:
        n_unique = series.nunique()
        n_total  = max(len(series.dropna()), 1)
        avg_len  = series.dropna().astype(str).str.len().mean()
        # Low cardinality short strings → categorical
        return n_unique <= 50 or avg_len <= 30
    return False


def _detect_month_col(df: pd.DataFrame) -> Optional[str]:
    """Find a column whose values look like month names or have 'month' in the name."""
    for col in df.columns:
        if "month" in col.lower():
            return col
    for col in df.columns:
        vals = df[col].dropna().astype(str).str.lower().unique()
        if any(v in MONTH_NAMES for v in vals[:20]):
            return col
    # Fall back to Date column — derive month from it
    for col in df.columns:
        if "date" in col.lower() and pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
    return None


def _build_schema(df: pd.DataFrame, structured: list, text_cols: list) -> str:
    lines = ["DataFrame name: df", f"Total rows: {len(df)}", "", "Columns:"]
    for col in df.columns:
        dtype = str(df[col].dtype)
        n_unique = df[col].nunique()
        sample = df[col].dropna().astype(str).head(3).tolist()
        sample_str = ", ".join(f'"{s[:40]}"' for s in sample)
        layer = "structured" if col in structured else ("text/RAG" if col in text_cols else "skip")
        lines.append(f"  {col} [{dtype}, {n_unique} unique, layer={layer}]")
        lines.append(f"    sample: {sample_str}")
    return "\n".join(lines)


def load_file(
    file_obj,           # file-like object (from Streamlit uploader or open())
    filename: str,
) -> DataBundle:
    """
    Load an Excel or CSV file and return a DataBundle.

    Parameters
    ----------
    file_obj : file-like object
    filename : original filename (used to detect .xlsx vs .csv)
    """
    fname = filename.lower()
    sheets = {}
    frames = []

    if fname.endswith(".csv"):
        df_raw = pd.read_csv(file_obj)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        sheets["Sheet1"] = df_raw
        frames.append(df_raw)

    else:
        # Excel — load all non-empty sheets
        xl = pd.ExcelFile(file_obj)
        for sheet in xl.sheet_names:
            try:
                df_s = xl.parse(sheet)
                df_s.columns = [c.strip() for c in df_s.columns]
                if df_s.empty or len(df_s.columns) < 2:
                    continue
                # Skip sheets that look like dashboards (mostly unnamed cols)
                unnamed = sum(1 for c in df_s.columns if "Unnamed" in str(c))
                if unnamed > len(df_s.columns) * 0.5:
                    continue
                df_s["_sheet"] = sheet
                sheets[sheet] = df_s
                frames.append(df_s)
            except Exception:
                continue

    if not frames:
        raise ValueError("No readable data found in the uploaded file.")

    df = pd.concat(frames, ignore_index=True)

    # Try to parse date-like columns
    for col in df.columns:
        if "date" in col.lower() and df[col].dtype == object:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce")
            except Exception:
                pass

    # Detect month column — add synthetic 'month' column if from Date
    month_col = _detect_month_col(df)
    if month_col and "date" in month_col.lower() and pd.api.types.is_datetime64_any_dtype(df[month_col]):
        df["month"] = df[month_col].dt.strftime("%B")
        month_col = "month"
    elif month_col is None and "_sheet" in df.columns:
        # Use sheet name as month if they look like month names
        if df["_sheet"].str.lower().isin(MONTH_NAMES).any():
            df["month"] = df["_sheet"].str.capitalize()
            month_col = "month"

    # Classify columns
    skip = {"_sheet"}
    structured = []
    text_cols  = []

    for col in df.columns:
        if col in skip:
            continue
        name_l = col.lower()
        if any(p in name_l for p in SKIP_PATTERNS):
            continue
        if _is_text_col(df[col], col):
            text_cols.append(col)
        elif _is_structured_col(df[col], col):
            structured.append(col)

    # Build merged text content column
    if text_cols:
        df["_content"] = df[text_cols].apply(
            lambda row: "\n".join(
                f"{c}: {v}" for c, v in row.items()
                if pd.notna(v) and str(v).strip() not in ("", "nan", "NaN")
            ),
            axis=1,
        )

    months = []
    if month_col and month_col in df.columns:
        all_vals = df[month_col].dropna().astype(str).unique().tolist()
        # Keep only values that are actual month names
        months = [m for m in all_vals if m.lower() in MONTH_NAMES]
        if not months:
            months = sorted(all_vals)

    schema = _build_schema(df, structured, text_cols)

    print(f"✅ Loaded {len(df)} rows | {len(sheets)} sheet(s) | "
          f"{len(structured)} structured cols | {len(text_cols)} text cols")

    return DataBundle(
        df          = df,
        sheets      = sheets,
        structured  = structured,
        text_cols   = text_cols,
        schema_desc = schema,
        months      = months,
        month_col   = month_col,
    )


def parse_template(docx_file) -> dict:
    """
    Read a .docx reference template and extract its structure:
    headings, table column names, and section order.

    Returns a dict with keys:
      title    : document title
      sections : list of {heading, has_table, table_headers, has_observation}
      raw_text : full text for LLM context
    """
    try:
        from docx import Document
        doc = Document(docx_file)
    except Exception as e:
        return {"title": "Report", "sections": [], "raw_text": str(e)}

    sections  = []
    current   = None
    full_text = []

    for para in doc.paragraphs:
        t = para.text.strip()
        if not t:
            continue
        full_text.append(t)
        style = para.style.name

        if "Heading 1" in style or "Title" in style:
            if current:
                sections.append(current)
            current = {
                "heading"         : t,
                "has_table"       : False,
                "table_headers"   : [],
                "has_observation" : False,
                "body_text"       : [],
            }
        elif "Heading" in style and current:
            if "observation" in t.lower():
                current["has_observation"] = True
            else:
                current["body_text"].append(t)
        elif current:
            current["body_text"].append(t)

    if current:
        sections.append(current)

    # Mark tables
    for table in doc.tables:
        if sections:
            headers = [cell.text.strip() for cell in table.rows[0].cells if cell.text.strip()]
            # Associate with last section that doesn't have a table yet
            for s in reversed(sections):
                if not s["has_table"]:
                    s["has_table"]       = True
                    s["table_headers"]   = headers
                    break

    title = doc.paragraphs[0].text.strip() if doc.paragraphs else "Report"

    return {
        "title"    : title,
        "sections" : sections,
        "raw_text" : "\n".join(full_text[:200]),   # cap for LLM context
    }
