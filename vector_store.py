"""
vector_store.py
---------------
Step 3: Embed the free-text presales data and store in ChromaDB (local, offline).

Two modes:
  - build  : reads the Excel, embeds all rows, persists to ./chroma_db/
  - query  : retrieves the top-k most relevant records for a given question

Embedding model : nomic-embed-text  (via Ollama, running on localhost:11434)
Vector store    : ChromaDB          (persisted on disk, no server needed)

Usage (CLI):
    python vector_store.py build
    python vector_store.py query "What were the common workflow requirements?"

Usage (import):
    from vector_store import build_store, query_store
"""

import os
import sys
import json
import hashlib
import requests
import chromadb
import pandas as pd
from pathlib import Path
from typing import Optional

# ── Config ───────────────────────────────────────────────────────────────────

BASE_DIR      = Path("/Users/sakthi-3766/Claude/Projects/Local SLM")
EXCEL_PATH    = BASE_DIR / "WD Presales Demo Stats 2026.xlsx"
CHROMA_DIR    = BASE_DIR / "chroma_db"
COLLECTION    = "presales_notes"
OLLAMA_URL    = "http://localhost:11434"
EMBED_MODEL   = "nomic-embed-text"
BATCH_SIZE    = 50   # rows per embedding batch (avoids timeout on large files)


# ── Ollama embedding ─────────────────────────────────────────────────────────

def _embed(texts: list[str]) -> list[list[float]]:
    """Call Ollama's /api/embed endpoint and return vectors."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def _check_ollama():
    """Raise a clear error if Ollama isn't reachable or model is missing."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Ollama is not running. Start it with: ollama serve"
        )
    if not any(EMBED_MODEL in m for m in models):
        raise RuntimeError(
            f"Model '{EMBED_MODEL}' not found. Run: ollama pull {EMBED_MODEL}"
        )


# ── Stable row ID ────────────────────────────────────────────────────────────

def _row_id(month: str, ticket: str, content: str, idx: int) -> str:
    """Deterministic ID so re-building doesn't duplicate rows."""
    key = f"{month}|{ticket}|{idx}|{content[:80]}"
    return hashlib.md5(key.encode()).hexdigest()


# ── Build ────────────────────────────────────────────────────────────────────

def build_store(force_rebuild: bool = False) -> chromadb.Collection:
    """
    Embed all text rows and persist to ChromaDB.

    Parameters
    ----------
    force_rebuild : if True, drops and recreates the collection from scratch.
    """
    _check_ollama()

    # Import here so the module is usable even if data_ingestion isn't in PATH
    sys.path.insert(0, str(BASE_DIR))
    from data_ingestion import load_data

    _, text_df, _, _ = load_data(str(EXCEL_PATH))

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    if force_rebuild:
        try:
            client.delete_collection(COLLECTION)
            print(f"🗑  Dropped existing collection '{COLLECTION}'")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # Skip rows already in the store
    existing_ids = set(collection.get(include=[])["ids"])
    rows_to_add = [
        (i, row) for i, (_, row) in enumerate(text_df.iterrows())
        if _row_id(row.get("month", ""), str(row.get("Ticket ID", "")), row["content"], i)
           not in existing_ids
    ]

    if not rows_to_add:
        print(f"✅ Collection '{COLLECTION}' is already up to date "
              f"({len(existing_ids)} vectors).")
        return collection

    print(f"📥 Embedding {len(rows_to_add)} rows in batches of {BATCH_SIZE}…")

    ids, embeddings, documents, metadatas = [], [], [], []

    for i in range(0, len(rows_to_add), BATCH_SIZE):
        batch    = rows_to_add[i : i + BATCH_SIZE]
        contents = [row["content"] for _, row in batch]

        batch_vecs = _embed(contents)

        for (row_idx, row), vec in zip(batch, batch_vecs):
            month   = str(row.get("month", ""))
            ticket  = str(row.get("Ticket ID", ""))
            content = row["content"]
            row_id  = _row_id(month, ticket, content, row_idx)

            ids.append(row_id)
            embeddings.append(vec)
            documents.append(content)
            metadatas.append({"month": month, "ticket_id": ticket})

        pct = min(100, int((i + len(batch)) / len(rows_to_add) * 100))
        print(f"   [{pct:>3}%] {i + len(batch)}/{len(rows_to_add)} rows embedded")

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    print(f"\n✅ Vector store built — {collection.count()} vectors "
          f"stored at {CHROMA_DIR}")
    return collection


# ── Query ────────────────────────────────────────────────────────────────────

def query_store(
    question: str,
    month: Optional[str] = None,
    top_k: int = 5,
) -> list[dict]:
    """
    Retrieve the top-k most semantically similar records.

    Parameters
    ----------
    question : natural-language query
    month    : optional filter, e.g. "April"
    top_k    : number of results to return

    Returns
    -------
    list of dicts with keys: content, month, ticket_id, distance
    """
    _check_ollama()

    client     = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection(COLLECTION)

    query_vec = _embed([question])[0]

    where = {"month": month} if month else None

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "content"   : doc,
            "month"     : meta.get("month"),
            "ticket_id" : meta.get("ticket_id"),
            "distance"  : round(dist, 4),
        })

    return output


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "build":
        force = "--force" in sys.argv
        build_store(force_rebuild=force)

    elif cmd == "query":
        if len(sys.argv) < 3:
            print("Usage: python vector_store.py query \"your question\" [--month April]")
            sys.exit(1)
        question = sys.argv[2]
        month    = None
        if "--month" in sys.argv:
            idx   = sys.argv.index("--month")
            month = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None

        hits = query_store(question, month=month)
        print(f"\n🔍 Top {len(hits)} results for: \"{question}\"\n")
        for i, h in enumerate(hits, 1):
            print(f"── Result {i} [{h['month']} | {h['ticket_id']} | dist={h['distance']}]")
            print(h["content"][:400])
            print()

    else:
        print(f"Unknown command '{cmd}'. Use: build | query")
        sys.exit(1)
