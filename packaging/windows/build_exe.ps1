# ComicCatcher Windows Build Script
$ErrorActionPreference = "Stop"

# Project root (packaging/windows/build_exe.ps1 -> project root)
$BASE_DIR = (Get-Item "$PSScriptRoot\..\..").FullName
cd $BASE_DIR
echo "📍 Working directory: $BASE_DIR"

# 1. Setup Environment (Isolated Venv)
echo "📦 Setting up isolated build environment..."
if (Test-Path "build_venv") { Remove-Item -Recurse -Force "build_venv" }
python -m venv build_venv
& ".\build_venv\Scripts\Activate.ps1"

# Upgrade pip and install tools in the venv
python -m pip install --upgrade pip
python -m pip install build pyinstaller Pillow

# 2. Build Wheel
echo "📦 Building wheel..."
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
python -m build --wheel --outdir dist/

# 3. Create Icon
echo "🖼️  Creating Windows icon..."
$ICON_PNG = "src/comiccatcher/resources/app_256.png"
$ICON_ICO = "packaging/windows/comiccatcher.ico"

# Simple python script to convert png to ico using Pillow
python -c @"
from PIL import Image
img = Image.open('$ICON_PNG')
img.save('$ICON_ICO', format='ICO', sizes=[(16,16), (32,32), (48,48), (64,64), (128,128), (256,256)])
"@

# 4. Build EXE with PyInstaller
echo "🚀 Running PyInstaller..."
python -m PyInstaller --noconfirm --windowed --onefile `
    --name "ComicCatcher" `
    --icon "$ICON_ICO" `
    --collect-all "comiccatcher" `
    --add-data "src/comiccatcher/resources;comiccatcher/resources" `
    "src/comiccatcher/main.py"

# 5. Verification
if (Test-Path "dist/ComicCatcher.exe") {
    echo "✅ Windows build complete: dist/ComicCatcher.exe"
} else {
    echo "❌ Error: dist/ComicCatcher.exe was not created!"
    exit 1
}
