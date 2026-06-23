"""
native_app.py — Presales AI  |  Native macOS App
-------------------------------------------------
Starts the Streamlit server on a local port, then opens it
in a native macOS window using PyQt6 QWebEngineView.

Feels and behaves like a real Mac app — no browser needed.
"""

import sys, os, time, socket, subprocess, signal
from pathlib import Path

BASE_DIR = Path(__file__).parent
PORT     = 8501

# ── Ensure we can import our modules ─────────────────────────────────────────
sys.path.insert(0, str(BASE_DIR))

from PyQt6.QtWidgets  import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QSplashScreen,
                               QProgressBar, QFrame, QFileDialog)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore    import QWebEnginePage, QWebEngineProfile, QWebEngineDownloadRequest
from PyQt6.QtCore    import QUrl, QTimer, Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui     import QIcon, QPixmap, QColor, QPainter, QFont, QAction

_ICON_PATH = BASE_DIR / "icon.png"

# ── Ollama onboarding HTML ────────────────────────────────────────────────────
ONBOARDING_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0E1117; color: #E8EAF0;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh;
  }
  .card {
    background: #161B27; border: 1px solid rgba(79,142,247,0.25);
    border-radius: 20px; padding: 48px 56px; max-width: 620px;
    width: 90%; text-align: center;
  }
  .icon { font-size: 64px; margin-bottom: 24px; }
  h1 { font-size: 26px; font-weight: 700; color: #E8EAF0; margin-bottom: 10px; }
  .subtitle { color: #8B92A5; font-size: 15px; margin-bottom: 36px; line-height: 1.6; }
  .step {
    background: rgba(79,142,247,0.08); border: 1px solid rgba(79,142,247,0.2);
    border-radius: 12px; padding: 18px 22px; margin-bottom: 14px;
    display: flex; align-items: flex-start; gap: 16px; text-align: left;
  }
  .step-num {
    background: #4F8EF7; color: #fff; font-weight: 700; font-size: 13px;
    width: 28px; height: 28px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  .step-content h3 { font-size: 14px; font-weight: 600; color: #E8EAF0; margin-bottom: 4px; }
  .step-content p  { font-size: 13px; color: #8B92A5; line-height: 1.5; }
  code {
    background: rgba(255,255,255,0.08); border-radius: 5px;
    padding: 2px 7px; font-family: monospace; font-size: 12px; color: #4F8EF7;
  }
  .btn-primary {
    display: inline-block; margin-top: 28px;
    background: linear-gradient(135deg, #4F8EF7, #3B6FD4);
    color: #fff; font-size: 15px; font-weight: 600;
    padding: 13px 36px; border-radius: 10px; border: none;
    cursor: pointer; text-decoration: none; transition: opacity 0.2s;
  }
  .btn-primary:hover { opacity: 0.88; }
  .btn-secondary {
    display: inline-block; margin-top: 14px; margin-left: 12px;
    background: rgba(79,142,247,0.12); color: #4F8EF7;
    border: 1px solid rgba(79,142,247,0.3);
    font-size: 14px; font-weight: 500;
    padding: 12px 28px; border-radius: 10px; border: none;
    cursor: pointer; text-decoration: none; transition: all 0.2s;
  }
  .btn-secondary:hover { background: rgba(79,142,247,0.25); }
  #status { margin-top: 20px; font-size: 13px; color: #8B92A5; min-height: 20px; }
  .checking { color: #F59E0B; }
  .ok { color: #10B981; font-weight: 600; }
  .err { color: #EF4444; }
</style>
</head>
<body>
<div class="card">
  <div class="icon">🧠</div>
  <h1>Welcome to Presales AI</h1>
  <p class="subtitle">
    This app needs <strong>Ollama</strong> to run the AI engine locally.<br>
    Ollama is free, runs entirely on your Mac, and keeps all your data private.
  </p>

  <div class="step">
    <div class="step-num">1</div>
    <div class="step-content">
      <h3>Download & Install Ollama</h3>
      <p>Free macOS app — takes about 2 minutes to install.</p>
    </div>
  </div>

  <div class="step">
    <div class="step-num">2</div>
    <div class="step-content">
      <h3>Download the AI models</h3>
      <p>Open Terminal and run:<br>
        <code>ollama pull llama3.1:8b</code><br>
        <code>ollama pull nomic-embed-text</code><br>
        (about 5 GB total — download once, runs forever offline)
      </p>
    </div>
  </div>

  <div class="step">
    <div class="step-num">3</div>
    <div class="step-content">
      <h3>Start Ollama, then click Continue</h3>
      <p>Ollama runs in your menu bar. Once the icon appears, click Continue below.</p>
    </div>
  </div>

  <div>
    <a class="btn-primary"
       href="https://ollama.com/download/mac"
       onclick="this.textContent='Opening download page…'">
      ⬇  Download Ollama for Mac
    </a>
    <button class="btn-secondary" onclick="checkOllama()">
      ▶  Continue (Ollama is ready)
    </button>
  </div>
  <div id="status"></div>
</div>

<script>
function checkOllama() {
  var el = document.getElementById('status');
  el.className = 'checking';
  el.textContent = 'Checking Ollama… please wait';

  fetch('http://localhost:11434/api/tags')
    .then(function(r) {
      if (r.ok) {
        el.className = 'ok';
        el.textContent = '✓ Ollama is running! Loading Presales AI…';
        setTimeout(function() {
          window.location.href = 'http://localhost:8501';
        }, 1200);
      } else {
        throw new Error('not running');
      }
    })
    .catch(function() {
      el.className = 'err';
      el.textContent = '✗ Ollama is not running. Start it from your Applications folder, then try again.';
    });
}

// Auto-check every 8 seconds
setInterval(function() {
  fetch('http://localhost:11434/api/tags')
    .then(function(r) {
      if (r.ok) {
        var el = document.getElementById('status');
        el.className = 'ok';
        el.textContent = '✓ Ollama detected! Loading Presales AI…';
        setTimeout(function() {
          window.location.href = 'http://localhost:8501';
        }, 1200);
      }
    })
    .catch(function() {});
}, 8000);
</script>
</body>
</html>
"""


# ── Check port free ───────────────────────────────────────────────────────────

def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def _wait_for_server(port: int, timeout: int = 30) -> bool:
    """Block until Streamlit is accepting connections."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_in_use(port):
            return True
        time.sleep(0.3)
    return False


# ── Streamlit launcher thread ─────────────────────────────────────────────────

class StreamlitThread(QThread):
    ready   = pyqtSignal()
    failed  = pyqtSignal(str)

    def __init__(self, app_path: str, port: int):
        super().__init__()
        self.app_path = app_path
        self.port     = port
        self.process  = None

    def run(self):
        # Kill any existing server on this port first
        if _port_in_use(self.port):
            self.ready.emit()
            return

        env = os.environ.copy()
        env["STREAMLIT_SERVER_HEADLESS"]            = "true"
        env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

        self.process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run",
             self.app_path,
             f"--server.port={self.port}",
             "--server.headless=true",
             "--browser.gatherUsageStats=false"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(BASE_DIR),
        )

        if _wait_for_server(self.port, timeout=40):
            self.ready.emit()
        else:
            self.failed.emit("Streamlit server failed to start within 40 seconds.")

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()


# ── Custom Web Page (suppress JS errors) ─────────────────────────────────────

class SilentPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        pass  # suppress browser console noise


# ── Splash screen ─────────────────────────────────────────────────────────────

def _make_splash() -> QSplashScreen:
    pix = QPixmap(480, 300)
    pix.fill(QColor("#0E1117"))

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background gradient card
    painter.setBrush(QColor("#161B27"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(40, 40, 400, 220, 20, 20)

    # Border
    from PyQt6.QtGui import QPen
    pen = QPen(QColor("#4F8EF7"))
    pen.setWidth(1)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(40, 40, 400, 220, 20, 20)

    # Icon
    painter.setPen(QColor("#4F8EF7"))
    font = QFont("Arial", 40)
    painter.setFont(font)
    painter.drawText(195, 130, "🧠")

    # Title
    painter.setPen(QColor("#E8EAF0"))
    font = QFont("Arial", 22, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(100, 185, "Presales AI")

    # Subtitle
    painter.setPen(QColor("#8B92A5"))
    font = QFont("Arial", 11)
    painter.setFont(font)
    painter.drawText(110, 210, "Offline Intelligence Platform")

    # Loading text
    painter.setPen(QColor("#4F8EF7"))
    font = QFont("Arial", 10)
    painter.setFont(font)
    painter.drawText(165, 240, "Starting up…")

    painter.end()
    return QSplashScreen(pix, Qt.WindowType.WindowStaysOnTopHint)


# ── Main window ───────────────────────────────────────────────────────────────

class PresalesAIWindow(QMainWindow):
    def __init__(self, streamlit_thread: StreamlitThread):
        super().__init__()
        self._thread = streamlit_thread
        self._url    = f"http://localhost:{PORT}"

        self.setWindowTitle("Presales AI")
        self.setMinimumSize(QSize(1280, 800))
        self.resize(1440, 900)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Title bar ─────────────────────────────────────────────────────────
        bar = QFrame()
        bar.setFixedHeight(42)
        bar.setStyleSheet("""
            QFrame {
                background: #111827;
                border-bottom: 1px solid rgba(79,142,247,0.2);
            }
        """)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(16, 0, 12, 0)

        title_lbl = QLabel("🧠  Presales AI")
        title_lbl.setStyleSheet("color:#4F8EF7; font-size:14px; font-weight:700; font-family:Arial;")
        bar_layout.addWidget(title_lbl)

        bar_layout.addStretch()

        # Ollama indicator
        self.ollama_lbl = QLabel("● Checking Ollama…")
        self.ollama_lbl.setStyleSheet("color:#8B92A5; font-size:11px;")
        bar_layout.addWidget(self.ollama_lbl)

        # Refresh button
        refresh_btn = QPushButton("⟳  Refresh")
        refresh_btn.setFixedHeight(26)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(79,142,247,0.15);
                color: #4F8EF7; border: 1px solid rgba(79,142,247,0.3);
                border-radius: 6px; font-size: 11px; padding: 0 10px;
            }
            QPushButton:hover { background: rgba(79,142,247,0.3); }
        """)
        refresh_btn.clicked.connect(lambda: self.webview.reload())
        bar_layout.addWidget(refresh_btn)

        layout.addWidget(bar)

        # ── WebView ────────────────────────────────────────────────────────────
        self.webview = QWebEngineView()
        self.webview.setPage(SilentPage(self.webview))
        self.webview.setUrl(QUrl(self._url))
        self.webview.setStyleSheet("background:#0E1117;")
        layout.addWidget(self.webview)

        # ── Download handler — saves .docx and any file downloads ────────────
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self._on_download_requested)

        # Poll Ollama status every 5s
        self._ollama_timer = QTimer()
        self._ollama_timer.timeout.connect(self._check_ollama)
        self._ollama_timer.start(5000)
        self._check_ollama()

    def _check_ollama(self):
        try:
            import requests
            ok = requests.get("http://localhost:11434/api/tags", timeout=2).status_code == 200
        except Exception:
            ok = False
        if ok:
            self.ollama_lbl.setText("● Ollama online")
            self.ollama_lbl.setStyleSheet("color:#10B981; font-size:11px;")
        else:
            self.ollama_lbl.setText("● Ollama offline")
            self.ollama_lbl.setStyleSheet("color:#EF4444; font-size:11px;")

    def _on_download_requested(self, download: QWebEngineDownloadRequest):
        """Handle all file downloads from the WebView (reports, exports, etc.)."""
        suggested = download.suggestedFileName() or "download"

        # Default save path: ~/Downloads/<suggested filename>
        downloads_dir = Path.home() / "Downloads"
        downloads_dir.mkdir(exist_ok=True)
        default_path  = str(downloads_dir / suggested)

        # Show native macOS save dialog
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            default_path,
        )

        if save_path:
            download.setDownloadDirectory(str(Path(save_path).parent))
            download.setDownloadFileName(Path(save_path).name)
            download.accept()
        else:
            download.cancel()

    def closeEvent(self, event):
        self._thread.stop()
        event.accept()

    # Menu bar
    def _add_menus(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("QMenuBar { background:#111827; color:#E8EAF0; }")

        app_menu = menubar.addMenu("App")
        quit_act  = QAction("Quit Presales AI", self)
        quit_act.setShortcut("Ctrl+Q")
        quit_act.triggered.connect(QApplication.quit)
        app_menu.addAction(quit_act)

        view_menu = menubar.addMenu("View")
        reload_act = QAction("Reload", self)
        reload_act.setShortcut("Ctrl+R")
        reload_act.triggered.connect(self.webview.reload)
        view_menu.addAction(reload_act)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Presales AI")
    app.setOrganizationName("Zoho")
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))

    # Splash
    splash = _make_splash()
    splash.show()
    app.processEvents()

    # Start Streamlit in background thread
    app_py = str(BASE_DIR / "app.py")
    thread = StreamlitThread(app_py, PORT)

    window = PresalesAIWindow(thread)

    def on_ready():
        splash.finish(window)
        window._add_menus()
        window.show()
        # Show onboarding if Ollama not installed, else go straight to app
        try:
            import requests as _req
            ollama_up = _req.get("http://localhost:11434/api/tags", timeout=2).status_code == 200
        except Exception:
            ollama_up = False

        if ollama_up:
            window.webview.setUrl(QUrl(f"http://localhost:{PORT}"))
        else:
            window.webview.setHtml(ONBOARDING_HTML, QUrl("http://localhost:8501"))

    def on_failed(msg):
        splash.close()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Startup Error", f"Failed to start server:\n\n{msg}")
        sys.exit(1)

    thread.ready.connect(on_ready)
    thread.failed.connect(on_failed)
    thread.start()

    signal.signal(signal.SIGINT, lambda *_: app.quit())
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
