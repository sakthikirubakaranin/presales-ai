#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build_dmg.sh — Builds Presales AI.dmg  (macOS)
#
# Requirements:
#   pip3 install pyinstaller pyqt6 pyqt6-webengine streamlit   (all others
#   should already be installed from the project setup)
#
# Usage:
#   cd "/Users/sakthi-3766/Claude/Projects/Local SLM"
#   chmod +x build_dmg.sh
#   ./build_dmg.sh
#
# Output: PresalesAI.dmg  (same directory)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PROJECT_DIR="/Users/sakthi-3766/Claude/Projects/Local SLM"
APP_NAME="PresalesAI"
DMG_NAME="${APP_NAME}.dmg"
VOLUME_NAME="Presales AI"
DIST_DIR="${PROJECT_DIR}/dist"
APP_PATH="${DIST_DIR}/${APP_NAME}.app"

cd "$PROJECT_DIR"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║      Presales AI  —  DMG Builder         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Check dependencies ──────────────────────────────────────────────────
echo "▶  Checking dependencies…"

check_cmd() {
    command -v "$1" &>/dev/null || {
        echo "✗ '$1' not found. Install it with: pip3 install $2"
        exit 1
    }
}

check_cmd pyinstaller pyinstaller
python3 -c "import PyQt6.QtWebEngineWidgets" 2>/dev/null || {
    echo "✗ PyQt6-WebEngine not found. Run: pip3 install pyqt6-webengine --break-system-packages"
    exit 1
}
echo "✓ Dependencies OK"

# ── 2. Build .app with PyInstaller ─────────────────────────────────────────
echo ""
echo "▶  Generating AppIcon.icns from iconset…"
if [ -d "${PROJECT_DIR}/AppIcon.iconset" ]; then
    iconutil -c icns "${PROJECT_DIR}/AppIcon.iconset" -o "${PROJECT_DIR}/AppIcon.icns"
    echo "✓ AppIcon.icns created"
fi

echo "▶  Building ${APP_NAME}.app with PyInstaller…"
echo "   (This takes 2–5 minutes on first run)"

rm -rf "${DIST_DIR}/${APP_NAME}" "${APP_PATH}"
pyinstaller --clean --noconfirm "${PROJECT_DIR}/PresalesAI.spec"

if [ ! -d "$APP_PATH" ]; then
    echo "✗ PyInstaller did not produce ${APP_PATH}"
    exit 1
fi
echo "✓ ${APP_NAME}.app built at: ${APP_PATH}"

# ── 3. Create DMG with hdiutil ─────────────────────────────────────────────
echo ""
echo "▶  Creating ${DMG_NAME}…"

DMG_TMP="${DIST_DIR}/${APP_NAME}_tmp.dmg"
DMG_OUT="${PROJECT_DIR}/${DMG_NAME}"

# Remove old artifacts
rm -f "$DMG_TMP" "$DMG_OUT"

# Calculate required size (app size + 20% buffer, minimum 200MB)
APP_MB=$(du -sm "$APP_PATH" | awk '{print $1}')
DMG_MB=$(( APP_MB * 12 / 10 ))   # +20%
[ "$DMG_MB" -lt 200 ] && DMG_MB=200

echo "   App size: ${APP_MB}MB  →  DMG size: ${DMG_MB}MB"

# Create writable image
hdiutil create \
    -srcfolder "$APP_PATH" \
    -volname   "$VOLUME_NAME" \
    -fs        HFS+ \
    -fsargs    "-c c=65536,a=16,b=16" \
    -format    UDRW \
    -size      "${DMG_MB}m" \
    "$DMG_TMP"

# Mount it
MOUNT_DIR="/Volumes/${VOLUME_NAME}"
hdiutil attach "$DMG_TMP" -readwrite -noverify -noautoopen

sleep 2  # wait for mount

# Add Applications symlink for drag-to-install UX
ln -sf /Applications "${MOUNT_DIR}/Applications" 2>/dev/null || true

# Set background & icon positions with AppleScript
osascript <<APPLESCRIPT
tell application "Finder"
    tell disk "${VOLUME_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 100, 760, 460}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 128
        set position of item "${APP_NAME}.app"  of container window to {160, 200}
        set position of item "Applications"     of container window to {400, 200}
        close
        open
        update without registering applications
        delay 3
    end tell
end tell
APPLESCRIPT

# Unmount
hdiutil detach "${MOUNT_DIR}" -quiet || true
sleep 2

# Convert to compressed read-only DMG
hdiutil convert "$DMG_TMP" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "$DMG_OUT"

rm -f "$DMG_TMP"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ✅  DMG ready:  ${DMG_NAME}            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "   Size: $(du -sh "$DMG_OUT" | awk '{print $1}')"
echo "   Path: $DMG_OUT"
echo ""
echo "   To install: open the DMG, drag Presales AI to Applications."
echo ""
