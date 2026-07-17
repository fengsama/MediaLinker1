#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

command -v flatpak >/dev/null || { echo "未找到 flatpak"; exit 1; }
command -v flatpak-builder >/dev/null || { echo "未找到 flatpak-builder"; exit 1; }

if [[ ! -x dist/MediaLinker/MediaLinker ]]; then
  bash build-linux.sh
fi

flatpak-builder --user --force-clean --install-deps-from=flathub --repo=flatpak-repo flatpak-build flatpak/io.github.medialinker.MediaLinker.yml
mkdir -p release
flatpak build-bundle flatpak-repo release/MediaLinker-x86_64.flatpak io.github.medialinker.MediaLinker \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo

echo "Flatpak 安装包：$PROJECT_ROOT/release/MediaLinker-x86_64.flatpak"
