<div align="center">

# MediaLinker

### 影视硬链接整理工具

将下载目录中的电影、电视剧和字幕整理为适合 Emby / Kodi 刮削的媒体库结构，同时保留原始文件与做种能力。

![Vue 3](https://img.shields.io/badge/Vue-3-42b883?logo=vuedotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-安装版%20%7C%20绿色版-0078d4?logo=windows)
![Linux](https://img.shields.io/badge/Linux-构建支持-fcc624?logo=linux&logoColor=black)
![Flatpak](https://img.shields.io/badge/Flatpak-构建支持-4a90d9?logo=flatpak&logoColor=white)

</div>

## 项目简介

MediaLinker 是一个运行在本地的影视文件整理 Web 工具，面向 NAS、Emby、Kodi、PT 和磁力下载场景。

它不会尝试取代媒体服务器，而是作为下载目录与媒体库之间的整理层：扫描已有视频、自动关联字幕、搜索中文影视资料、生成规范文件名，并根据用户选择创建硬链接或直接移动重命名原文件。

```text
下载目录 / PT 做种目录
          │
          ▼
     MediaLinker
          │
          ├── 创建硬链接（保留原文件，推荐）
          └── 移动并重命名原文件
          │
          ▼
   Emby / Kodi 媒体库
```

## 主要功能

- 使用网页完成全部整理流程。
- 调用系统原生文件夹选择窗口，无需手动复制路径。
- 递归扫描 MKV、MP4、AVI、MOV、WMV、M4V、TS、WEBM。
- 扫描后手动勾选需要整理的视频，支持全选和取消全选。
- 自动关联同目录、同名的 SRT 字幕。
- 支持 `.chs`、`.zh-CN` 等字幕语言后缀。
- 通过 TMDB 搜索简体中文电影和电视剧资料。
- 搜索结果以悬浮列表展示，选择后自动填充名称、年份和类型。
- 自动生成电视剧季目录、集数编号和规范文件名。
- 执行前预览所有视频与字幕的目标名称。
- 支持创建真正的文件系统硬链接。
- 支持移动并重命名原文件，并提供风险确认。
- 自动记住上次选择的输出目录。
- 启动时自动查询 GitHub 最新 Release。
- 右上角设置中心提供软件信息和手动检查更新。
- Windows 与 Linux 便携版支持下载、完整性校验、自动替换和重启。
- 已提供 Windows 标准 EXE 安装包和免安装绿色版。
- 已提供 Linux x86_64 和 Flatpak 自动构建配置。
- Windows、Linux 与 Flatpak 均可通过系统窗口选择本地文件夹。
- Windows 客户端后台运行，不再显示命令行窗口。
- 关闭所有 MediaLinker 网页后，打包版后台服务会自动退出；刷新页面不会误关闭。

## 命名规则

### 电影

```text
Movies/
└── 星际穿越 (2014)/
    ├── 星际穿越 (2014).mkv
    └── 星际穿越 (2014).zh-CN.srt
```

### 电视剧与动漫

```text
TV Shows/
└── 进击的巨人 (2013)/
    └── Season 01/
        ├── 进击的巨人 S01E01.mkv
        ├── 进击的巨人 S01E01.chs.srt
        ├── 进击的巨人 S01E02.mkv
        └── 进击的巨人 S01E02.chs.srt
```

## 字幕自动关联

扫描视频时，MediaLinker 会在视频所在目录查找同名 SRT 字幕：

```text
Movie.mkv          → Movie.srt
Movie.mkv          → Movie.chs.srt
Movie.mkv          → Movie.zh-CN.srt
```

无关字幕不会自动关联。生成链接或移动文件时，字幕会跟随对应视频使用相同的新名称，并保留语言后缀。

## 硬链接说明

硬链接不是快捷方式，也不是文件复制。两个路径指向同一份文件数据：

- 不会再次占用完整视频容量，仅增加很小的目录记录。
- 两个文件在资源管理器中都会显示完整文件大小。
- 删除其中一个路径不会删除数据，最后一个硬链接被删除后才会释放空间。
- 修改任意路径中的文件内容会影响所有硬链接。
- 来源与目标必须处于同一磁盘分区或同一 NAS 文件系统。

Windows 可以使用以下命令查看文件的全部硬链接：

```powershell
fsutil hardlink list "完整文件路径"
```

## Windows 安装版（推荐）

1. 下载 `MediaLinker-Setup-x64.exe`。
2. 双击安装包，按安装向导完成安装。
3. 从开始菜单或桌面快捷方式启动 MediaLinker。
4. 如需移除，可在 Windows“设置 → 应用”中正常卸载。

安装版默认安装到当前用户目录，不需要管理员权限。检测到新版本后，会下载新的 EXE 安装包、静默更新并重新启动。

## Windows 绿色版

Windows 便携版不需要安装 Python、Node.js 或其他依赖。

1. 下载并完整解压 `MediaLinker-Windows-x64.zip`。
2. 进入 `MediaLinker` 文件夹。
3. 双击 `MediaLinker.exe`。
4. 程序会自动打开默认浏览器。
5. 关闭运行窗口即可停止服务。

请复制整个 `MediaLinker` 文件夹，不要只复制 EXE。建议将程序放在普通可写目录，避免放入 `Program Files`。

## 软件更新

MediaLinker 启动后会自动比较本地版本和 GitHub 最新 Release，也可以通过右上角的齿轮按钮进入“软件信息”，手动查询更新。

- Windows 安装版、绿色版和 Linux 便携版发现新版本后会自动下载对应平台的发布包。
- 下载完成后会核对 GitHub 提供的文件大小与 SHA-256 摘要，再替换程序并重新启动。
- 更新时保留本地 `config` 配置目录。
- 源码开发模式不会覆盖源码，只显示版本状态与 Release 链接。
- Flatpak 版目前显示新版本和下载入口，由用户安装新的 Flatpak 包。

## Linux 与 Flatpak 文件夹选择

Linux 便携版和 Flatpak 版的“选择文件夹”按钮会直接打开桌面环境提供的文件夹选择窗口，无需复制路径：

- Flatpak 优先使用 XDG Desktop Portal，兼容 GNOME、KDE 等主流桌面。
- 普通 Linux 依次使用系统门户、Zenity、KDialog 或 Tk 作为回退。
- 程序仍支持手动输入本地路径或已挂载的 SMB 路径。

自动更新依赖公开可访问的 GitHub Release，并要求程序所在目录具有写入权限。

## 从源码运行

### 环境要求

- Python 3.11 或更高版本
- Node.js 20 或更高版本
- Windows 10/11，或带图形桌面的 Linux

### 启动后端

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Linux：

```bash
cd backend
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问地址：

- 前端：<http://localhost:5173>
- 后端接口文档：<http://localhost:8000/docs>

## TMDB 中文资料配置

影视搜索使用 TMDB，并固定请求简体中文 `zh-CN` 资料。

1. 注册并登录 [TMDB](https://www.themoviedb.org/signup)。
2. 打开 [TMDB API 设置](https://www.themoviedb.org/settings/api)。
3. 申请 Developer API 访问权限。
4. 复制较长的 `API Read Access Token`，通常以 `eyJ...` 开头。
5. 在 MediaLinker 的匹配信息页面点击“配置 TMDB”。
6. 粘贴 Token，点击“验证并保存”。

请勿把 Token 上传到 GitHub、提交到 Git，或发送到公开聊天。项目的 `.gitignore` 已忽略本地配置和环境文件。

## Linux 便携版构建

独立 Linux 构建工程提供 `build-linux.sh`：

```bash
sudo apt install python3 python3-venv python3-tk nodejs npm
chmod +x build-linux.sh
./build-linux.sh
```

输出文件：

```text
release/MediaLinker-Linux-x86_64.tar.gz
```

## Flatpak 构建

安装 Flatpak、`flatpak-builder` 并配置 Flathub 后运行：

```bash
chmod +x build-flatpak.sh
./build-flatpak.sh
```

输出文件：

```text
release/MediaLinker-x86_64.flatpak
```

安装与运行：

```bash
flatpak install --user release/MediaLinker-x86_64.flatpak
flatpak run io.github.medialinker.MediaLinker
```

Flatpak 版本需要网络权限访问 TMDB，也需要主机文件系统权限扫描和整理用户选择的媒体目录。

## GitHub Actions 自动构建

Linux 构建工程包含：

```text
.github/workflows/build-linux.yml
```

支持在 GitHub Actions 页面手动触发，或推送 `v*` 标签后自动生成：

- `MediaLinker-Linux-x86_64.tar.gz`
- `MediaLinker-x86_64.flatpak`

## 项目结构

```text
MediaLinker/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── files.py       # 文件扫描与目录选择
│   │   │   ├── metadata.py    # TMDB 中文资料
│   │   │   ├── organizer.py   # 硬链接与移动重命名
│   │   │   ├── updates.py     # GitHub 版本检查与自动更新
│   │   │   └── health.py      # 健康检查
│   │   ├── main.py
│   │   ├── models.py
│   │   └── version.py          # 当前软件版本
│   ├── requirements.txt
│   └── run.py                 # 便携版入口
├── frontend/
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.js
│   │   └── style.css
│   ├── package.json
│   └── vite.config.js
├── flatpak/                   # Flatpak manifest 与桌面文件
├── MediaLinker.spec           # PyInstaller 配置
├── build-linux.sh
├── build-flatpak.sh
└── README.md
```

## 主要 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/health` | 服务健康检查 |
| `POST` | `/api/files/pick-directory` | 打开系统文件夹选择窗口 |
| `POST` | `/api/files/scan` | 扫描视频并关联字幕 |
| `GET` | `/api/metadata/config/status` | 检查 TMDB 配置 |
| `POST` | `/api/metadata/config` | 验证并保存 TMDB Token |
| `GET` | `/api/metadata/search` | 搜索中文影视资料 |
| `POST` | `/api/organizer/execute` | 创建硬链接或移动重命名 |
| `GET` | `/api/update/check` | 比较本地与 GitHub 最新版本 |
| `POST` | `/api/update/apply` | 下载、校验并安装便携版更新 |

## 安全设计

- 默认使用硬链接模式，不修改原始下载文件。
- 移动并重命名模式需要额外风险确认。
- 目标文件已存在时拒绝覆盖。
- 批量处理中途失败时尝试回滚本次操作。
- 目录和文件名经过 Windows 非法字符检查。
- TMDB Token 只保存在本地配置中。
- 服务默认仅监听 `127.0.0.1`，不会直接暴露到局域网或互联网。
- 自动更新只接受 GitHub Release 中与当前平台名称完全匹配的附件，并校验大小与 SHA-256。

## 已知限制

- 硬链接无法跨磁盘分区或跨文件系统创建。
- SMB/NAS 是否支持硬链接取决于服务器文件系统和共享配置。
- 系统文件夹选择窗口要求程序运行在图形桌面会话中。
- 当前只自动关联 SRT 字幕。
- Flatpak 为整理任意媒体目录需要较宽的主机文件访问权限。
- Flatpak 暂不直接替换自身，发现更新后需要安装新的 Flatpak 发布包。

## 路线图

- [ ] 支持 ASS、SSA、SUP 等更多字幕格式。
- [ ] 从原文件名自动识别季、集数和版本信息。
- [ ] 支持逐集手动调整编号。
- [ ] 下载海报、背景图并生成 NFO。
- [ ] 任务历史、撤销与操作日志。
- [ ] qBittorrent 下载完成后自动整理。
- [ ] NAS/服务器端网页目录浏览器。
- [ ] Docker 部署版本。

## 贡献

欢迎通过 Issue 提交问题、功能建议和兼容性反馈。提交代码前，请确保：

- 不提交 TMDB Token、媒体路径或个人配置。
- 前端能够完成 `npm run build`。
- 后端新增行为包含基本验证。
- 涉及文件修改或移动时，优先保证不覆盖和可回滚。

## 许可证

当前仓库尚未附带开源许可证。在明确添加许可证之前，默认保留所有权利。如果计划公开发布或接受第三方贡献，建议先选择并添加合适的 `LICENSE` 文件。

## 第三方服务声明

本产品使用 TMDB API，但未经 TMDB 认可或认证。影视文字、图片及其他元数据的权利归其各自权利人所有。
