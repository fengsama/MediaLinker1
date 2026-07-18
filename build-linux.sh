#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

command -v python3 >/dev/null || { echo "未找到 python3"; exit 1; }
command -v npm >/dev/null || { echo "未找到 npm"; exit 1; }

python3 -m venv backend/.venv-linux
backend/.venv-linux/bin/python -m pip install --upgrade pip
backend/.venv-linux/bin/python -m pip install -r backend/requirements.txt pyinstaller

(
  cd backend
  .venv-linux/bin/python -m unittest discover -s tests -v
)

(
  cd frontend
  npm ci
  npm run build
)

backend/.venv-linux/bin/python -m PyInstaller --noconfirm --clean MediaLinker.spec
cp PORTABLE-README.txt dist/MediaLinker/使用说明.txt
mkdir -p release
tar -C dist -czf release/MediaLinker-Linux-x86_64.tar.gz MediaLinker

echo "Linux 便携包：$PROJECT_ROOT/release/MediaLinker-Linux-x86_64.tar.gz"
