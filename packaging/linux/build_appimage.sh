#!/bin/bash
set -ex

# Project root
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$BASE_DIR"

# 1. Prepare Metadata
echo "📂 Preparing metadata..."
METADATA_DIR="packaging/metadata"
rm -rf "$METADATA_DIR"
mkdir -p "$METADATA_DIR/usr/share/applications"
mkdir -p "$METADATA_DIR/usr/share/icons/hicolor/256x256/apps"

cp packaging/linux/comiccatcher.desktop "$METADATA_DIR/usr/share/applications/"
cp src/comiccatcher/resources/app_256.png "$METADATA_DIR/usr/share/icons/hicolor/256x256/apps/comiccatcher.png"

# 2. Build Base AppDir
echo "🚀 Building Base AppDir..."
BUILD_DIR="comiccatcher-x86_64"
rm -rf "$BUILD_DIR"
python3 -m python_appimage build app . \
    --python-version 3.12 \
    --name ComicCatcher \
    --no-packaging \
    -x "$METADATA_DIR"

# 3. Manually install project and dependencies into AppDir
echo "📥 Installing project and dependencies into AppDir..."
./"$BUILD_DIR/opt/python3.12/bin/python3.12" -m pip install . --prefix "$BASE_DIR/$BUILD_DIR/opt/python3.12"

# 4. Prune and Optimize (Size Reduction)
echo "✂️  Optimizing AppDir size..."

# A. Remove bytecode and caches
find "$BUILD_DIR" -name "*.pyc" -delete
find "$BUILD_DIR" -name "__pycache__" -type d -exec rm -rf {} +
find "$BUILD_DIR" -name "*.a" -delete # Static libs
find "$BUILD_DIR" -name "*.h" -delete # Headers

# B. Strip shared libraries (remove debug symbols)
find "$BUILD_DIR" -name "*.so*" -exec strip --strip-unneeded {} + || true

# C. Prune Unused Qt6 Libraries (PyQt6 bundles the kitchen sink)
QT_LIB_DIR="$BUILD_DIR/opt/python3.12/lib/python3.12/site-packages/PyQt6/Qt6/lib"
if [ -d "$QT_LIB_DIR" ]; then
    echo "📦 Pruning PyQt6 libraries..."
    # We keep: Core, Gui, Widgets, Network, Svg
    # We remove the rest (Bluetooth, Multimedia, NFC, Positioning, Sensors, etc.)
    find "$QT_LIB_DIR" -name "libQt6Bluetooth*" -delete
    find "$QT_LIB_DIR" -name "libQt6Multimedia*" -delete
    find "$QT_LIB_DIR" -name "libQt6Nfc*" -delete
    find "$QT_LIB_DIR" -name "libQt6Positioning*" -delete
    find "$QT_LIB_DIR" -name "libQt6RemoteObjects*" -delete
    find "$QT_LIB_DIR" -name "libQt6Sensors*" -delete
    find "$QT_LIB_DIR" -name "libQt6SerialPort*" -delete
    find "$QT_LIB_DIR" -name "libQt6Sql*" -delete
    find "$QT_LIB_DIR" -name "libQt6Test*" -delete
    find "$QT_LIB_DIR" -name "libQt6WebChannel*" -delete
    find "$QT_LIB_DIR" -name "libQt6Xml*" -delete
fi

# 5. Hijack AppDir structure (overwrite tool defaults)
echo "🛠️  Hijacking AppDir structure..."
rm -f "$BUILD_DIR/AppRun"
cat > "$BUILD_DIR/AppRun" << 'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/opt/python3.12/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/opt/python3.12/lib:${LD_LIBRARY_PATH}"
export PYTHONPATH="${HERE}/opt/python3.12/lib/python3.12/site-packages:${PYTHONPATH}"
# Launch using python -m
exec "${HERE}/opt/python3.12/bin/python3.12" -m comiccatcher.main "$@"
EOF
chmod +x "$BUILD_DIR/AppRun"

cp packaging/comiccatcher.desktop "$BUILD_DIR/comiccatcher.desktop"
cp src/comiccatcher/resources/app_256.png "$BUILD_DIR/comiccatcher.png"
rm -f "$BUILD_DIR/python3.12.12.desktop" "$BUILD_DIR/python.png"

# 6. Fetch appimagetool if missing
if ! command -v appimagetool &> /dev/null; then
    if [ ! -f packaging/appimagetool ]; then
        echo "📥 Downloading appimagetool..."
        TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
        curl -L "$TOOL_URL" -o packaging/appimagetool
        chmod +x packaging/appimagetool
    fi
    APPIMAGETOOL="./packaging/appimagetool --appimage-extract-and-run"
else
    APPIMAGETOOL="appimagetool"
fi

# 7. Finalize and Pack
echo "📦 Packaging AppImage..."
mkdir -p dist
ARCH=x86_64 $APPIMAGETOOL -n "$BUILD_DIR" dist/ComicCatcher-x86_64.AppImage

# Cleanup large build directory
rm -rf "$BUILD_DIR"

echo "✅ AppImage build complete: dist/ComicCatcher-x86_64.AppImage"
