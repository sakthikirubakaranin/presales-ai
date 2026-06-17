"""
query_engine.py
---------------
Step 4: Pandas Query Engine — lets the local LLM answer structured analytics
questions by generating and executing Python/Pandas code against the presales
DataFrame.

Flow for each question:
  1. Send the question + DataFrame schema to Ollama (llama3.1:8b)
  2. LLM returns a short pandas snippet
  3. Execute the snippet safely and return the result
  4. (Optional) Ask LLM to narrate the result in plain English

Usage (CLI):
    python query_engine.py "What is the conversion rate for April?"
    python query_engine.py "Top 3 industries by deal count"
    python query_engine.py "Revenue breakdown by region"

Usage (import):
    from query_engine import ask
    result, narrative = ask("How many deals were won in March?")
"""

import re
import sys
import json
import textwrap
import requests
import pandas as pd
from pathlib import Path
from typing import Any, Optional

# ── Config ───────────────────────────────────────────────────────────────────

BASE_DIR    = Path("/Users/sakthi-3766/Claude/Projects/Local SLM")
EXCEL_PATH  = BASE_DIR / "WD Presales Demo Stats 2026.xlsx"
OLLAMA_URL  = "http://localhost:11434"
LLM_MODEL   = "llama3.1:8b"

# ── Load data once at import time ────────────────────────────────────────────

sys.path.insert(0, str(BASE_DIR))
from data_ingestion import load_data

_structured_df, _, _feature_df, _noshow_df = load_data(str(EXCEL_PATH))

# Expose as module-level for exec() context
df          = _structured_df       # main presales data
feature_df  = _feature_df          # feature requests
noshow_df   = _noshow_df           # no-show stats

# ── Schema description sent to LLM ──────────────────────────────────────────

SCHEMA = """
DataFrame name: df
Columns and sample values:
  month                      : str  — "January", "February", ..., "June"
  Date                       : datetime
  Region                     : str  — "IN", "US", "EMEA", "EU", "ANZ", "APAC", "LATAM"
  Handled by                 : str  — "Sakthi", "Janani", "Jennifer", "Rohith", ...
  Email address              : str
  Industry                   : str  — "Education", "Software", "Banking", "Food", ...
  Ticket ID                  : str  — "#152989037"
  Source                     : str  — "WorkDrive - Book a Demo (direct)", "From Sales End", ...
  Engagement Type            : str  — "New Prospect", "Already Engaged Px"
  Trial sign up              : str  — "Yes", "No", "POC", "Extended"
  Status                     : str  — "Deal Won", "Deal Lost", "In Progress",
                                      "Existing customer", "No Scope for WD",
                                      "Free user", "Partner"
  Deal Size                  : str  — raw value e.g. "50", "10-15"
  deal_size_lower            : float — numeric lower bound of Deal Size
  Revenue                    : float — actual revenue in INR (may be NaN)
  Suggested/purchased edition: str  — "Starter", "Business", "Zoho One", ...
  Follow up stages           : str  — "Do not follow", "Follow up 1", "Sales follow up 3", ...
  PSE Creation               : str  — PSE reference or NaN
  Current Platform           : str  — "Google Drive", "OneDrive", "Dropbox", ...
  Existing data size         : str  — "< 1 TB", "< 3 TB", etc.

Secondary DataFrames:
  feature_df : feature requests — columns: Date, Feature name, Description,
               Ticket Ref, Deal size, Feature Owner, ETA, status, Sprintz link
  noshow_df  : no-shows — columns: Date, Tags, Request Id, Email (Request),
               Deal Size, Region, Followup, Notes, Re-engaged
"""

# ── LLM call ────────────────────────────────────────────────────────────────

def _llm(prompt: str, temperature: float = 0.1) -> str:
    """Send a prompt to Ollama and return the response text."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model"       : LLM_MODEL,
            "prompt"      : prompt,
            "stream"      : False,
            "temperature" : temperature,
            "options"     : {"num_predict": 512},
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"].strip()


def _check_ollama():
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Ollama not running. Start with: ollama serve")
    if not any(LLM_MODEL.split(":")[0] in m for m in models):
        raise RuntimeError(f"Model '{LLM_MODEL}' not found. Run: ollama pull {LLM_MODEL}")


# ── Code extraction ──────────────────────────────────────────────────────────

def _extract_code(text: str) -> str:
    """Pull the first Python code block out of an LLM response."""
    # Try ```python ... ``` block first
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fall back: look for lines starting with df / result / pd
    lines = [
        l for l in text.splitlines()
        if l.strip() and not l.strip().startswith("#")
        and not l.strip().startswith("Here")
        and not l.strip().startswith("The")
    ]
    return "\n".join(lines).strip()


# ── Safe execution ───────────────────────────────────────────────────────────

def _safe_exec(code: str) -> Any:
    """
    Execute pandas code in a restricted namespace.
    The variable `result` must be set by the code.
    """
    namespace = {
        "df"         : df,
        "feature_df" : feature_df,
        "noshow_df"  : noshow_df,
        "pd"         : pd,
    }
    exec(code, namespace)           # noqa: S102
    if "result" not in namespace:
        raise ValueError("LLM code did not assign to `result`.")
    return namespace["result"]


# ── Main ask() function ──────────────────────────────────────────────────────

def ask(question: str, narrate: bool = True) -> tuple[Any, str]:
    """
    Answer a structured analytics question about the presales data.

    Parameters
    ----------
    question : natural-language question
    narrate  : if True, ask the LLM to explain the result in plain English

    Returns
    -------
    (raw_result, narrative)
      raw_result : whatever the pandas code produces (DataFrame, Series, scalar)
      narrative  : plain-English explanation from the LLM
    """
    _check_ollama()

    # ── Step 1: generate pandas code ────────────────────────────────────────
    code_prompt = textwrap.dedent(f"""
        You are a Python/Pandas expert. Use the DataFrame described below to answer
        the question. Write ONLY executable Python code — no explanation, no markdown,
        no comments. The last line MUST assign the answer to a variable called `result`.

        {SCHEMA}

        Question: {question}

        Rules:
        - Use only: df, feature_df, noshow_df, pd
        - Always assign the final answer to `result`
        - For percentages, round to 2 decimal places
        - For counts, use .value_counts() or groupby
        - Do NOT import anything
        - Output only the code, nothing else
    """).strip()

    raw_code = _llm(code_prompt, temperature=0.05)
    code     = _extract_code(raw_code)

    # ── Step 2: execute ──────────────────────────────────────────────────────
    try:
        raw_result = _safe_exec(code)
    except Exception as e:
        # Retry once with the error fed back to the LLM
        fix_prompt = textwrap.dedent(f"""
            The following Python code raised an error. Fix it and return only
            the corrected code. Assign the answer to `result`.

            Code:
            {code}

            Error: {e}

            Schema:
            {SCHEMA}
        """).strip()
        fixed_code = _extract_code(_llm(fix_prompt, temperature=0.1))
        raw_result = _safe_exec(fixed_code)
        code = fixed_code

    # ── Step 3: narrate ──────────────────────────────────────────────────────
    narrative = ""
    if narrate:
        narrate_prompt = textwrap.dedent(f"""
            You are a presales analytics assistant. The user asked:
            "{question}"

            The data result is:
            {raw_result}

            Write a concise 2-4 sentence insight in plain English. Be specific —
            include numbers. Do not repeat the question. Do not use bullet points.
        """).strip()
        narrative = _llm(narrate_prompt, temperature=0.3)

    return raw_result, narrative


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    question = " ".join(sys.argv[1:])
    print(f"\n❓ Question: {question}\n")

    result, narrative = ask(question)

    print("── Raw result ──────────────────────────────────────")
    print(result)
    print("\n── Insight ─────────────────────────────────────────")
    print(narrative)
    print()
