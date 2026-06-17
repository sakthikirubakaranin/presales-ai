"""
orchestrator.py
---------------
Step 5: The central brain — receives any natural-language question, decides
which layer answers it best, executes the query, and returns a combined answer.

Routing logic:
  STRUCTURED  → numbers, counts, rates, breakdowns, rankings, trends over time
  RAG         → "why", themes, requirements, summaries of notes/purpose/feedback
  HYBRID      → questions that need both (e.g. "What are the top deal-won
                 reasons and what did the sales notes say about them?")

Usage (CLI):
    python orchestrator.py "What is the conversion rate for April?"
    python orchestrator.py "What were the common requirements from enterprise deals?"
    python orchestrator.py "Summarise deal lost patterns in March"

Usage (import):
    from orchestrator import answer
    response = answer("How many deals were won in the US region?")
"""

import sys
import textwrap
import requests
from pathlib import Path
from typing import Optional

BASE_DIR   = Path("/Users/sakthi-3766/Claude/Projects/Local SLM")
OLLAMA_URL = "http://localhost:11434"
LLM_MODEL  = "llama3.1:8b"

sys.path.insert(0, str(BASE_DIR))

# ── Route classifier ─────────────────────────────────────────────────────────

STRUCTURED_KEYWORDS = [
    "how many", "count", "total", "rate", "percentage", "%", "revenue",
    "breakdown", "distribution", "top", "highest", "lowest", "average",
    "by region", "by month", "by industry", "by status", "by source",
    "deal won", "deal lost", "conversion", "trend", "compare", "rank",
    "in progress", "no show", "trial", "deal size", "won", "lost",
]

RAG_KEYWORDS = [
    "what were", "what are", "common", "theme", "requirement", "feature",
    "why", "reason", "feedback", "notes", "summary", "summarise", "summarize",
    "describe", "explain", "pattern", "issue", "concern", "request",
    "enterprise", "prospect said", "sales note", "purpose", "use case",
    "migration", "integration", "pain point", "challenge",
]


def _classify(question: str) -> str:
    """
    Returns: "structured", "rag", or "hybrid"
    Uses keyword heuristics first; falls back to LLM for ambiguous cases.
    """
    q = question.lower()

    struct_score = sum(1 for kw in STRUCTURED_KEYWORDS if kw in q)
    rag_score    = sum(1 for kw in RAG_KEYWORDS if kw in q)

    if struct_score > 0 and rag_score == 0:
        return "structured"
    if rag_score > 0 and struct_score == 0:
        return "rag"
    if struct_score > 0 and rag_score > 0:
        return "hybrid"

    # Ambiguous — ask the LLM
    prompt = textwrap.dedent(f"""
        Classify this question into exactly one category:
        - "structured"  : needs counts, numbers, rates, filters on tabular data
        - "rag"         : needs reading free-text notes, requirements, or summaries
        - "hybrid"      : needs both

        Question: {question}

        Reply with ONLY one word: structured, rag, or hybrid.
    """).strip()

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": LLM_MODEL, "prompt": prompt, "stream": False,
                  "temperature": 0.0, "options": {"num_predict": 10}},
            timeout=30,
        )
        route = resp.json()["response"].strip().lower()
        if "struct" in route:
            return "structured"
        if "hybrid" in route:
            return "hybrid"
        return "rag"
    except Exception:
        # Safe default
        return "hybrid"


# ── Month extractor ──────────────────────────────────────────────────────────

MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]


def _extract_month(question: str) -> Optional[str]:
    q = question.lower()
    for m in MONTHS:
        if m in q:
            return m.capitalize()
    return None


# ── Main answer() ────────────────────────────────────────────────────────────

def answer(question: str, verbose: bool = False) -> str:
    """
    Route the question, execute the right layer(s), return a plain-English answer.

    Parameters
    ----------
    question : any natural-language question about the presales data
    verbose  : if True, print routing decisions to stdout

    Returns
    -------
    str — plain-English answer with numbers where relevant
    """
    route = _classify(question)
    month = _extract_month(question)

    if verbose:
        print(f"  [router] route={route}  month={month}")

    structured_result = None
    rag_chunks        = []
    struct_narrative  = ""

    # ── Structured layer ─────────────────────────────────────────────────────
    if route in ("structured", "hybrid"):
        try:
            from query_engine import ask as struct_ask
            raw, struct_narrative = struct_ask(question, narrate=True)
            structured_result = raw
        except Exception as e:
            struct_narrative = f"[structured query failed: {e}]"

    # ── RAG layer ────────────────────────────────────────────────────────────
    if route in ("rag", "hybrid"):
        try:
            from vector_store import query_store
            rag_chunks = query_store(question, month=month, top_k=6)
        except Exception as e:
            rag_chunks = []
            if verbose:
                print(f"  [rag] failed: {e}")

    # ── Combine into final answer ────────────────────────────────────────────
    if route == "structured":
        return struct_narrative

    if route == "rag" and rag_chunks:
        context = "\n\n".join(
            f"[{c['month']} | {c['ticket_id']}]\n{c['content'][:400]}"
            for c in rag_chunks
        )
        synthesise_prompt = textwrap.dedent(f"""
            You are a presales analytics assistant. Answer the question below
            using ONLY the context provided. Be concise (3-5 sentences).
            Include specific examples from the context where relevant.
            Do not use bullet points.

            Question: {question}

            Context:
            {context}
        """).strip()
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": LLM_MODEL, "prompt": synthesise_prompt,
                      "stream": False, "temperature": 0.3,
                      "options": {"num_predict": 400}},
                timeout=120,
            )
            return resp.json()["response"].strip()
        except Exception as e:
            return f"[synthesis failed: {e}]"

    if route == "hybrid":
        rag_summary = ""
        if rag_chunks:
            context = "\n\n".join(
                f"[{c['month']} | {c['ticket_id']}]\n{c['content'][:300]}"
                for c in rag_chunks
            )
            hybrid_prompt = textwrap.dedent(f"""
                You are a presales analytics assistant. Combine the quantitative
                finding and the qualitative context below into a single, cohesive
                answer (4-6 sentences). Be specific. Do not use bullet points.

                Question: {question}

                Quantitative finding:
                {struct_narrative or structured_result}

                Qualitative context from notes:
                {context}
            """).strip()
            try:
                resp = requests.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={"model": LLM_MODEL, "prompt": hybrid_prompt,
                          "stream": False, "temperature": 0.3,
                          "options": {"num_predict": 500}},
                    timeout=120,
                )
                return resp.json()["response"].strip()
            except Exception as e:
                return struct_narrative or f"[hybrid synthesis failed: {e}]"

        return struct_narrative or "No data found for this question."

    return "Could not answer — no relevant data found."


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    question = " ".join(sys.argv[1:])
    route    = _classify(question)
    month    = _extract_month(question)

    print(f"\n❓ Question : {question}")
    print(f"   Route    : {route}")
    print(f"   Month    : {month or 'all months'}")
    print("\n── Answer ──────────────────────────────────────────")
    print(answer(question, verbose=True))
    print()
