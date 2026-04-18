# ComicCatcher Windows Build Script
$ErrorActionPreference = "Stop"

# Project root
$BASE_DIR = Resolve-Path "$PSScriptRoot\..\.."
cd $BASE_DIR

# 1. Setup Environment
echo "📦 Setting up build environment..."
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
# --windowed: No console window
# --onefile: Single EXE
# --name: Result filename
# --icon: Path to ico
# --collect-all: Ensure all submodules and data are included
# --add-data: Include resources folder
pyinstaller --noconfirm --windowed --onefile `
    --name "ComicCatcher" `
    --icon "$ICON_ICO" `
    --collect-all "comiccatcher" `
    --add-data "src/comiccatcher/resources;comiccatcher/resources" `
    "src/comiccatcher/main.py"

echo "✅ Windows build complete: dist/ComicCatcher.exe"
