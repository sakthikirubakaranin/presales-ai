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
                               QProgressBar, QFrame)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore    import QWebEnginePage
from PyQt6.QtCore    import QUrl, QTimer, Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui     import QIcon, QPixmap, QColor, QPainter, QFont, QAction

_ICON_PATH = BASE_DIR / "icon.png"


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
        window.webview.setUrl(QUrl(f"http://localhost:{PORT}"))

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
