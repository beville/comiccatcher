#!/bin/bash
set -e

# Project root
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$BASE_DIR"

echo "📦 Setting up Tox environment..."
python -m pip install --upgrade pip
python -m pip install tox

echo "🚀 Running Tox build for Windows..."
python -m tox r -e build_win

# Verification
if [ -f "dist/ComicCatcher.exe" ]; then
    echo "✅ Windows build complete: dist/ComicCatcher.exe"
else
    echo "❌ Error: dist/ComicCatcher.exe was not created!"
    exit 1
fi
