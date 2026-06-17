#!/bin/bash
# install_deps.sh — Install all Python dependencies for Presales AI
#
# Usage:
#   cd "/Users/sakthi-3766/Claude/Projects/Local SLM"
#   chmod +x install_deps.sh
#   ./install_deps.sh

set -euo pipefail

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║   Presales AI  —  Dependency Installer    ║"
echo "╚═══════════════════════════════════════════╝"
echo ""

PIP="pip3 install"

echo "▶  Installing core data packages…"
$PIP pandas openpyxl xlrd numpy requests tqdm

echo ""
echo "▶  Installing AI/ML packages…"
$PIP chromadb sentence-transformers

echo ""
echo "▶  Installing document/chart packages…"
$PIP python-docx matplotlib

echo ""
echo "▶  Installing Streamlit UI…"
$PIP streamlit

echo ""
echo "▶  Installing native app packages…"
$PIP pyinstaller
$PIP PyQt6 pyqt6-webengine || {
    echo "  PyQt6-WebEngine install failed — trying alternate package name…"
    $PIP PyQt6-WebEngine
}

echo ""
echo "✅  All Python dependencies installed."
echo ""
echo "▶  Verifying Ollama…"
if command -v ollama &>/dev/null; then
    echo "✓ Ollama found: $(ollama --version)"
else
    echo "⚠  Ollama not found. Download from: https://ollama.com"
    echo "   Then run:  ollama pull llama3.1:8b && ollama pull nomic-embed-text"
fi

echo ""
echo "▶  Verifying Node.js / npm (for Word report generation)…"
if command -v npm &>/dev/null; then
    echo "✓ npm found: $(npm --version)"
    cd "/Users/sakthi-3766/Claude/Projects/Local SLM"
    npm install docx --save 2>/dev/null && echo "✓ docx npm package installed"
else
    echo "⚠  npm not found. Install Node.js from: https://nodejs.org"
fi

echo ""
echo "Done!  Run the app with:"
echo ""
echo "  # Option A — Streamlit browser:"
echo "  python3 -m streamlit run app.py"
echo ""
echo "  # Option B — Native macOS window:"
echo "  python3 native_app.py"
echo ""
echo "  # Option C — Build DMG:"
echo "  chmod +x build_dmg.sh && ./build_dmg.sh"
echo ""
