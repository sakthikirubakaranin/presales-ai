#!/bin/bash
# =============================================================================
# build_app.sh  —  Builds PresalesAI.app + PresalesAI.dmg
#
# No PyInstaller needed. Creates a native macOS .app bundle that uses the
# Python already installed on your machine (with all deps already present).
#
# Usage:
#   cd "/Users/sakthi-3766/Claude/Projects/Local SLM"
#   chmod +x build_app.sh
#   ./build_app.sh
#
# Output:  PresalesAI.dmg  (in this folder)
# =============================================================================

set -euo pipefail

PROJECT_DIR="/Users/sakthi-3766/Claude/Projects/Local SLM"
APP_NAME="PresalesAI"
APP_BUNDLE="${PROJECT_DIR}/${APP_NAME}.app"
DMG_OUT="${PROJECT_DIR}/${APP_NAME}.dmg"
VOLUME_NAME="Presales AI"

# Find the ARM64-native Python that has PyQt6 installed
PYTHON3=$(python3 -c "
import sys, subprocess, platform

candidates = [
    '/usr/bin/python3',
    '/usr/local/bin/python3',
    '/opt/homebrew/bin/python3',
    sys.executable,
    '/Library/Developer/CommandLineTools/usr/bin/python3',
]

for p in candidates:
    try:
        # Check architecture
        r_arch = subprocess.run(
            ['arch', '-arm64', p, '-c', 'import platform; print(platform.machine())'],
            capture_output=True, text=True
        )
        arch = r_arch.stdout.strip()
        # Try importing PyQt6 as arm64
        r = subprocess.run(
            ['arch', '-arm64', p, '-c', 'import PyQt6'],
            capture_output=True
        )
        if r.returncode == 0:
            print(p)
            break
    except: pass
" 2>/dev/null || echo "/usr/bin/python3")

cd "$PROJECT_DIR"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         Presales AI  —  App Builder              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Python : $PYTHON3"
echo "  Project: $PROJECT_DIR"
echo ""

# ── Step 1: Generate AppIcon.icns ─────────────────────────────────────────────
echo "▶  [1/5] Generating AppIcon.icns…"
if [ -d "${PROJECT_DIR}/AppIcon.iconset" ]; then
    iconutil -c icns "${PROJECT_DIR}/AppIcon.iconset" -o "${PROJECT_DIR}/AppIcon.icns"
    echo "   ✓ AppIcon.icns ready"
else
    echo "   ⚠  AppIcon.iconset not found — app will have no custom icon"
fi

# ── Step 2: Create .app bundle structure ──────────────────────────────────────
echo ""
echo "▶  [2/5] Building ${APP_NAME}.app bundle…"

rm -rf "$APP_BUNDLE"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"

# Copy icon
if [ -f "${PROJECT_DIR}/AppIcon.icns" ]; then
    cp "${PROJECT_DIR}/AppIcon.icns" "${APP_BUNDLE}/Contents/Resources/AppIcon.icns"
fi

# ── Info.plist ────────────────────────────────────────────────────────────────
cat > "${APP_BUNDLE}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Presales AI</string>

  <key>CFBundleDisplayName</key>
  <string>Presales AI</string>

  <key>CFBundleIdentifier</key>
  <string>com.zoho.presales-ai</string>

  <key>CFBundleVersion</key>
  <string>1.0.0</string>

  <key>CFBundleShortVersionString</key>
  <string>1.0</string>

  <key>CFBundleExecutable</key>
  <string>PresalesAI</string>

  <key>CFBundleIconFile</key>
  <string>AppIcon</string>

  <key>CFBundlePackageType</key>
  <string>APPL</string>

  <key>CFBundleSignature</key>
  <string>????</string>

  <key>NSHighResolutionCapable</key>
  <true/>

  <key>NSRequiresAquaSystemAppearance</key>
  <false/>

  <key>LSApplicationCategoryType</key>
  <string>public.app-category.business</string>

  <key>NSHumanReadableCopyright</key>
  <string>© 2026 Zoho Corporation. All rights reserved.</string>

  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>

  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

# ── Launcher script ────────────────────────────────────────────────────────────
# This is the actual executable inside the .app
cat > "${APP_BUNDLE}/Contents/MacOS/${APP_NAME}" << LAUNCHER
#!/bin/bash
# Presales AI Launcher

PROJECT_DIR="${PROJECT_DIR}"
LOG="\${HOME}/Library/Logs/PresalesAI.log"
mkdir -p "\$(dirname "\$LOG")"
exec > "\$LOG" 2>&1
echo "=== Presales AI started: \$(date) ==="

# ── Full PATH so Dock launches find everything ─────────────────────────────
export PATH="/usr/local/bin:/opt/homebrew/bin:/opt/homebrew/sbin"
export PATH="\$PATH:/Library/Developer/CommandLineTools/usr/bin"
export PATH="\$PATH:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH="\$PATH:\${HOME}/Library/Python/3.9/bin"
export PATH="\$PATH:\${HOME}/Library/Python/3.10/bin"
export PATH="\$PATH:\${HOME}/Library/Python/3.11/bin"

# ── Add user site-packages so pip-installed packages are visible ───────────
export PYTHONPATH="\${HOME}/Library/Python/3.9/lib/python/site-packages:\$PYTHONPATH"
export PYTHONPATH="\${HOME}/Library/Python/3.10/lib/python/site-packages:\$PYTHONPATH"
export PYTHONPATH="\${HOME}/Library/Python/3.11/lib/python/site-packages:\$PYTHONPATH"

# ── Find a Python that runs as ARM64 and has PyQt6 ─────────────────────────
PYTHON=""
for CANDIDATE in "${PYTHON3}" /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
    if [ -f "\$CANDIDATE" ]; then
        # Force ARM64 and test PyQt6
        if arch -arm64 "\$CANDIDATE" -c "import PyQt6" 2>/dev/null; then
            PYTHON="\$CANDIDATE"
            echo "Using ARM64 Python: \$PYTHON"
            break
        else
            echo "Skipping \$CANDIDATE"
        fi
    fi
done

if [ -z "\$PYTHON" ]; then
    osascript -e 'display alert "Presales AI" message "PyQt6 not found.\n\nRun in Terminal:\n\npip3 install PyQt6 PyQt6-WebEngine" as critical'
    exit 1
fi

# ── Start Ollama if not running ────────────────────────────────────────────
if ! pgrep -x "ollama" > /dev/null 2>&1; then
    echo "Starting Ollama..."
    for OLLAMA_BIN in /usr/local/bin/ollama /opt/homebrew/bin/ollama; do
        if [ -x "\$OLLAMA_BIN" ]; then
            "\$OLLAMA_BIN" serve > /dev/null 2>&1 &
            sleep 3
            break
        fi
    done
fi

# ── Launch app as ARM64 ────────────────────────────────────────────────────
cd "\$PROJECT_DIR"
echo "Running: arch -arm64 \$PYTHON \$PROJECT_DIR/native_app.py"
arch -arm64 "\$PYTHON" "\$PROJECT_DIR/native_app.py"
EXIT_CODE=\$?

if [ \$EXIT_CODE -ne 0 ]; then
    echo "App exited with code \$EXIT_CODE"
    osascript -e "display alert \"Presales AI crashed\" message \"Exit code: \$EXIT_CODE\n\nCheck log: \$LOG\" as critical"
fi
LAUNCHER

chmod +x "${APP_BUNDLE}/Contents/MacOS/${APP_NAME}"
echo "   ✓ ${APP_NAME}.app created"

# ── Step 3: Verify the .app ────────────────────────────────────────────────────
echo ""
echo "▶  [3/5] Verifying bundle…"
echo "   $(du -sh "$APP_BUNDLE" | cut -f1)  ${APP_NAME}.app"
ls "${APP_BUNDLE}/Contents/MacOS/"
ls "${APP_BUNDLE}/Contents/Resources/" 2>/dev/null || true

# ── Step 4: Create DMG ────────────────────────────────────────────────────────
echo ""
echo "▶  [4/5] Creating ${APP_NAME}.dmg…"

rm -f "$DMG_OUT"
DMG_TMP="${PROJECT_DIR}/${APP_NAME}_tmp.dmg"
rm -f "$DMG_TMP"

# Create writable DMG (80 MB — launcher + icon only, deps stay on disk)
hdiutil create \
    -size 80m \
    -fs HFS+ \
    -volname "$VOLUME_NAME" \
    "$DMG_TMP"

# Mount it
MOUNT_DIR="/Volumes/${VOLUME_NAME}"

# Unmount if already mounted
hdiutil detach "${MOUNT_DIR}" -quiet 2>/dev/null || true

hdiutil attach "$DMG_TMP" -readwrite -noverify -noautoopen -quiet
sleep 2

# Copy app bundle
cp -R "$APP_BUNDLE" "${MOUNT_DIR}/${APP_NAME}.app"

# Applications symlink (for drag-to-install)
ln -sf /Applications "${MOUNT_DIR}/Applications"

# Customize DMG appearance with AppleScript
osascript << APPLESCRIPT
tell application "Finder"
    tell disk "${VOLUME_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 100, 740, 480}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 120
        set position of item "${APP_NAME}.app" of container window to {160, 200}
        set position of item "Applications"    of container window to {400, 200}
        close
        open
        update without registering applications
        delay 2
    end tell
end tell
APPLESCRIPT

sync
hdiutil detach "${MOUNT_DIR}" -quiet
sleep 2

# Convert to compressed read-only DMG
hdiutil convert "$DMG_TMP" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "$DMG_OUT" \
    -quiet

rm -f "$DMG_TMP"

# ── Step 5: Done ───────────────────────────────────────────────────────────────
echo ""
echo "▶  [5/5] Verifying DMG…"
DMG_SIZE=$(du -sh "$DMG_OUT" | cut -f1)
echo "   ✓ ${DMG_SIZE}  ${DMG_OUT}"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  ✅  PresalesAI.dmg is ready!                               ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  To install:                                                 ║"
echo "║    1. Open PresalesAI.dmg                                   ║"
echo "║    2. Drag Presales AI  →  Applications                     ║"
echo "║    3. Launch from Launchpad or Applications folder          ║"
echo "║                                                              ║"
echo "║  Requirements (must be installed separately):               ║"
echo "║    • Ollama  →  https://ollama.com                          ║"
echo "║    • llama3.1:8b + nomic-embed-text (ollama pull …)         ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Log file: ~/Library/Logs/PresalesAI.log"
echo ""
