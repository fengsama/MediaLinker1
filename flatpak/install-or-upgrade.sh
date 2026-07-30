#!/usr/bin/env bash
set -Eeuo pipefail

APP_ID="io.github.medialinker.MediaLinker"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_PATH="${1:-$SCRIPT_DIR/MediaLinker-x86_64.flatpak}"
EXPECTED_VERSION="$(tr -d '[:space:]' < "$SCRIPT_DIR/VERSION" 2>/dev/null || true)"

fail() {
  printf '\n安装失败：%s\n' "$1" >&2
  printf 'MediaLinker 配置数据没有被删除，可以修复问题后重新运行本脚本。\n' >&2
  exit 1
}

command -v flatpak >/dev/null 2>&1 || fail "系统没有安装 Flatpak"
[[ -f "$BUNDLE_PATH" ]] || fail "找不到安装包：$BUNDLE_PATH"

printf 'MediaLinker Flatpak 安装/升级工具\n'
printf '安装包：%s\n\n' "$BUNDLE_PATH"

# 旧版可能仍在后台占用文件或端口。先强制停止，避免卸载/升级失败。
flatpak kill "$APP_ID" >/dev/null 2>&1 || true

if flatpak info --system "$APP_ID" >/dev/null 2>&1; then
  OLD_SYSTEM_VERSION="$(flatpak info --system --show-version "$APP_ID" 2>/dev/null || echo 未知)"
  printf '发现系统级旧版本：%s。为避免桌面继续启动旧版，需要管理员权限移除。\n' "$OLD_SYSTEM_VERSION"
  command -v sudo >/dev/null 2>&1 || fail "请先手动执行：flatpak uninstall --system $APP_ID"
  sudo flatpak uninstall --system -y "$APP_ID" || fail "无法移除系统级旧版本"
fi

if flatpak info --user "$APP_ID" >/dev/null 2>&1; then
  OLD_USER_VERSION="$(flatpak info --user --show-version "$APP_ID" 2>/dev/null || echo 未知)"
  printf '发现用户级旧版本：%s，正在移除程序（保留配置数据）……\n' "$OLD_USER_VERSION"
  flatpak uninstall --user -y "$APP_ID" || fail "无法移除用户级旧版本"
fi

printf '正在安装新的用户级版本……\n'
flatpak install --user -y "$BUNDLE_PATH" || fail "Flatpak 返回安装错误"

ACTUAL_VERSION="$(flatpak run --user "$APP_ID" --version 2>/dev/null | tail -n 1 | tr -d '[:space:]')"
[[ -n "$ACTUAL_VERSION" ]] || fail "安装完成，但无法读取程序真实版本"
if [[ -n "$EXPECTED_VERSION" && "$ACTUAL_VERSION" != "$EXPECTED_VERSION" ]]; then
  fail "版本核对失败：期望 v$EXPECTED_VERSION，实际启动的是 v$ACTUAL_VERSION"
fi

printf '\n安装成功：MediaLinker v%s\n' "$ACTUAL_VERSION"
printf '请关闭仍然打开的旧版网页，再从应用菜单重新启动 MediaLinker。\n'
printf '启动命令：flatpak run --user %s\n' "$APP_ID"
