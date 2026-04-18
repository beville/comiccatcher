#!/bin/bash
set -e

# Project root
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$BASE_DIR"

# 1. Setup Environment
echo "📦 Setting up build environment..."
python3 -m pip install --upgrade pip
python3 -m pip install build pyinstaller Pillow

# 2. Build Wheel
echo "📦 Building wheel..."
rm -rf dist/
python3 -m build --wheel --outdir dist/

# 3. Create Icon (.icns)
echo "🖼️  Creating macOS icon..."
ICON_PNG="src/comiccatcher/resources/app_256.png"
ICONSET="packaging/macos/comiccatcher.iconset"
ICON_ICNS="packaging/macos/comiccatcher.icns"

mkdir -p "$ICONSET"
sips -z 16 16   "$ICON_PNG" --out "$ICONSET/icon_16x16.png"
sips -z 32 32   "$ICON_PNG" --out "$ICONSET/icon_16x16@2x.png"
sips -z 32 32   "$ICON_PNG" --out "$ICONSET/icon_32x32.png"
sips -z 64 64   "$ICON_PNG" --out "$ICONSET/icon_32x32@2x.png"
sips -z 128 128 "$ICON_PNG" --out "$ICONSET/icon_128x128.png"
sips -z 256 256 "$ICON_PNG" --out "$ICONSET/icon_128x128@2x.png"
sips -z 256 256 "$ICON_PNG" --out "$ICONSET/icon_256x256.png"

iconutil -c icns "$ICONSET" -o "$ICON_ICNS"
rm -rf "$ICONSET"

# 4. Build .app with PyInstaller
echo "🚀 Running PyInstaller..."
# --windowed: Standard macOS app bundle
# --onefile: Bundles everything into the .app
python3 -m PyInstaller --noconfirm --windowed --onefile \
    --name "ComicCatcher" \
    --icon "$ICON_ICNS" \
    --collect-all "comiccatcher" \
    --add-data "src/comiccatcher/resources:comiccatcher/resources" \
    "src/comiccatcher/main.py"

# 5. Create DMG
echo "📦 Creating DMG..."
# Install create-dmg via brew (for GitHub runner or local)
if ! command -v create-dmg &> /dev/null; then
    echo "📥 Installing create-dmg..."
    brew install create-dmg
fi

rm -f dist/ComicCatcher-macOS.dmg
create-dmg \
  --volname "ComicCatcher" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "ComicCatcher.app" 175 190 \
  --hide-extension "ComicCatcher.app" \
  --app-drop-link 425 190 \
  "dist/ComicCatcher-macOS.dmg" \
  "dist/ComicCatcher.app"

echo "✅ macOS build complete: dist/ComicCatcher-macOS.dmg"
