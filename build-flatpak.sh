#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

command -v flatpak >/dev/null || { echo "未找到 flatpak"; exit 1; }
command -v flatpak-builder >/dev/null || { echo "未找到 flatpak-builder"; exit 1; }
command -v zip >/dev/null || { echo "未找到 zip"; exit 1; }

EXPECTED_VERSION="$(sed -n 's/^__version__ = "\([^"]*\)"/\1/p' backend/app/version.py)"
BUILT_VERSION="$(cat dist/MediaLinker/VERSION 2>/dev/null || true)"
if [[ ! -x dist/MediaLinker/MediaLinker || "$BUILT_VERSION" != "$EXPECTED_VERSION" ]]; then
  echo "正在重新构建 MediaLinker v$EXPECTED_VERSION，避免复用旧版程序……"
  bash build-linux.sh
fi

flatpak-builder --user --force-clean --install-deps-from=flathub --repo=flatpak-repo flatpak-build flatpak/io.github.medialinker.MediaLinker.yml
mkdir -p release
flatpak build-bundle flatpak-repo release/MediaLinker-x86_64.flatpak io.github.medialinker.MediaLinker \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo

rm -rf release/MediaLinker-Flatpak
mkdir -p release/MediaLinker-Flatpak
cp release/MediaLinker-x86_64.flatpak release/MediaLinker-Flatpak/
cp flatpak/install-or-upgrade.sh release/MediaLinker-Flatpak/
cp flatpak/FLATPAK-UPGRADE-README.txt release/MediaLinker-Flatpak/使用说明.txt
printf '%s\n' "$EXPECTED_VERSION" > release/MediaLinker-Flatpak/VERSION
(
  cd release
  zip -qr MediaLinker-Flatpak-x86_64.zip MediaLinker-Flatpak
)

echo "Flatpak 安装包：$PROJECT_ROOT/release/MediaLinker-x86_64.flatpak"
echo "Flatpak 一键升级包：$PROJECT_ROOT/release/MediaLinker-Flatpak-x86_64.zip"
