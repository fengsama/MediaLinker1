# Linux 与 Flatpak 构建

本目录是从 Windows 原项目独立复制的 Linux 构建版，不包含 TMDB 凭证。

## Linux x86_64 便携版

在 Ubuntu 24.04 或同类发行版安装构建工具：

```bash
sudo apt install python3 python3-venv python3-tk nodejs npm
chmod +x build-linux.sh
./build-linux.sh
```

产物：`release/MediaLinker-Linux-x86_64.tar.gz`

## Flatpak

先安装 Flatpak、flatpak-builder，并配置 Flathub，然后运行：

```bash
chmod +x build-flatpak.sh
./build-flatpak.sh
```

产物：`release/MediaLinker-x86_64.flatpak`

安装：

```bash
flatpak install --user release/MediaLinker-x86_64.flatpak
flatpak run io.github.medialinker.MediaLinker
```

Flatpak 为了扫描和整理用户指定的任意媒体目录，声明了主机文件系统访问权限；为了访问 TMDB，声明了网络权限。

## GitHub 自动构建

仓库包含 `.github/workflows/build-linux.yml`。在 GitHub 的 Actions 页面手动运行工作流，即可下载 Linux 和 Flatpak 两个构建产物。
