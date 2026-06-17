# Presales AI — Offline Intelligence Platform

A fully offline presales assistant that learns from your Excel data and answers questions, generates monthly reports, and runs as a native macOS app — powered by Llama 3.1 8B via Ollama.

---

## Features

- **Ask Questions** — Natural language Q&A over your presales dataset (conversion rates, regions, industries, trends)
- **Generate Reports** — Full monthly `.docx` reports with charts, tables, and AI-written observations
- **Data Overview** — Interactive dashboard with month / status / region filters
- **100% Offline** — No API keys, no cloud calls; LLM and embeddings run locally via Ollama
- **Native macOS App** — Runs as a `.app` / `.dmg` using PyQt6 + Streamlit

---

## Requirements

| Dependency | Install |
|---|---|
| Python 3.9+ | Pre-installed on macOS |
| Ollama | [ollama.com](https://ollama.com) |
| llama3.1:8b | `ollama pull llama3.1:8b` |
| nomic-embed-text | `ollama pull nomic-embed-text` |
| Node.js + npm | [nodejs.org](https://nodejs.org) (for Word report generation) |

---

## Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/presales-ai.git
cd presales-ai

# 2. Install Python deps
pip3 install pandas openpyxl chromadb streamlit requests \
             python-docx matplotlib PyQt6 PyQt6-WebEngine

# 3. Install Node deps (for .docx generation)
npm install docx

# 4. Build the ChromaDB vector store
python3 vector_store.py build

# 5. Run (browser mode)
python3 -m streamlit run app.py

# 6. Run (native macOS window)
python3 native_app.py
```

---

## Build macOS DMG

```bash
chmod +x build_app.sh
./build_app.sh
# Output: PresalesAI.dmg
```

Open the DMG → drag Presales AI to Applications → launch from Launchpad.

---

## Project Structure

```
presales-ai/
├── app.py                  # Streamlit UI
├── native_app.py           # PyQt6 native macOS window wrapper
├── dynamic_ingestion.py    # Loads any Excel/CSV, auto-classifies columns
├── data_ingestion.py       # Loads the WD Presales Excel specifically
├── vector_store.py         # ChromaDB vector store (RAG for text questions)
├── query_engine.py         # LLM + Pandas query engine
├── orchestrator.py         # Routes questions to structured/RAG/hybrid path
├── report_generator.py     # Generates .docx monthly reports via Node.js
├── chart_generator.py      # matplotlib chart generation
├── build_app.sh            # Builds PresalesAI.app + .dmg
├── install_deps.sh         # One-shot dependency installer
├── icon.svg                # App icon (source)
├── icon.png                # App icon (1024×1024 PNG)
└── AppIcon.iconset/        # macOS icon set (all sizes)
```

---

## Architecture

```
User Question
     │
     ▼
Orchestrator  ──── structured? ──▶  Pandas stats → LLM narrates
     │
     └──── text/qualitative? ──▶  ChromaDB RAG → LLM answers
```

- **LLM**: `llama3.1:8b` via Ollama at `localhost:11434`
- **Embeddings**: `nomic-embed-text` via Ollama
- **Vector store**: ChromaDB (local persistent, `chroma_db/`)
- **UI**: Streamlit (dark glassmorphism theme) wrapped in PyQt6 QWebEngineView

---

## License

MIT
