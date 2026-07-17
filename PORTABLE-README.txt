影视硬链接整理工具（Linux x86_64 便携版）
====================================

使用方法：
1. 请先完整解压 ZIP，不要直接在压缩包内运行。
2. 给启动文件执行权限：chmod +x MediaLinker
3. 在终端运行：./MediaLinker
4. 程序会自动打开默认浏览器。
5. 在终端按 Ctrl+C 即可停止服务。

新设备不需要安装 Python、Node.js 或其他依赖。需要带图形桌面的 x86_64 Linux。

注意事项：
- 请将整个 MediaLinker 文件夹一起复制，不要只复制 exe。
- 建议放在普通可写目录，例如 ~/Applications/MediaLinker。
- TMDB 凭证不会随便携包分发，需要在每台设备首次使用时配置。
- 配置保存在程序旁边的 config\settings.json。
- 硬链接要求来源与目标位于同一文件系统。
