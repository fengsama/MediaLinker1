MediaLinker Flatpak 安装与升级说明
=================================

推荐安装方法：

1. 将整个 MediaLinker-Flatpak 文件夹完整解压。
2. 在该文件夹空白处打开终端。
3. 执行：

   chmod +x install-or-upgrade.sh
   ./install-or-upgrade.sh

升级工具会自动：

- 停止仍在后台运行的旧版 MediaLinker；
- 检查用户级和系统级是否同时安装了不同版本；
- 移除冲突的旧程序，但保留 MediaLinker 配置数据；
- 安装新版本；
- 直接运行程序的 --version 参数核对真实版本。

安装完成后的启动命令：

flatpak run --user io.github.medialinker.MediaLinker

安装后请关闭浏览器里仍然打开的旧版 MediaLinker 页面，再从应用菜单重新启动，
不要继续使用旧页面或旧端口。

如果系统级旧版本需要移除，终端会要求输入 Linux 管理员密码。这是 Flatpak
移除系统范围旧程序所必需的权限，输入密码时终端不会显示星号，属于正常现象。

手动诊断命令：

flatpak info --user io.github.medialinker.MediaLinker
flatpak info --system io.github.medialinker.MediaLinker
flatpak run --user io.github.medialinker.MediaLinker --version
