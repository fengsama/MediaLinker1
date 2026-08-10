import asyncio
import os
import shlex
import sys
import uuid
from pathlib import Path

from app.server_config import is_server_mode


APP_ID = "io.github.medialinker.MediaLinker"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _linux_autostart_file() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "autostart" / "medialinker.desktop"


def _flatpak_marker() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "media-linker" / "autostart.enabled"


async def _configure_flatpak_background(enabled: bool) -> None:
    """Ask the desktop portal to create/remove the host autostart entry."""
    from dbus_next import BusType, Variant
    from dbus_next.aio import MessageBus

    bus = await MessageBus(bus_type=BusType.SESSION).connect()
    try:
        desktop_path = "/org/freedesktop/portal/desktop"
        introspection = await bus.introspect("org.freedesktop.portal.Desktop", desktop_path)
        proxy = bus.get_proxy_object("org.freedesktop.portal.Desktop", desktop_path, introspection)
        background = proxy.get_interface("org.freedesktop.portal.Background")
        handle = await background.call_request_background(
            "",
            {
                "handle_token": Variant("s", f"medialinker_{uuid.uuid4().hex}"),
                "reason": Variant("s", "监控新增影视文件并自动创建硬链接"),
                "autostart": Variant("b", enabled),
                "commandline": Variant("as", ["/app/bin/media-linker", "--background"]),
                "dbus-activatable": Variant("b", False),
            },
        )
        request_introspection = await bus.introspect("org.freedesktop.portal.Desktop", handle)
        request_proxy = bus.get_proxy_object("org.freedesktop.portal.Desktop", handle, request_introspection)
        request = request_proxy.get_interface("org.freedesktop.portal.Request")
        loop = asyncio.get_running_loop()
        response_future = loop.create_future()

        def receive_response(response: int, results: dict[str, object]) -> None:
            if not response_future.done():
                response_future.set_result((response, results))

        request.on_response(receive_response)
        response, _ = await asyncio.wait_for(response_future, timeout=300)
        if response != 0:
            raise RuntimeError("桌面系统未允许 MediaLinker 开机后台运行")
    finally:
        bus.disconnect()


def supported() -> bool:
    return is_server_mode() or getattr(sys, "frozen", False) or bool(os.environ.get("FLATPAK_ID"))


def status() -> dict[str, object]:
    if is_server_mode():
        return {"supported": True, "enabled": True, "managed_by": "docker", "message": "由 Docker 的 restart: unless-stopped 管理"}
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
                winreg.QueryValueEx(key, "MediaLinker")
            enabled = True
        except (FileNotFoundError, OSError):
            enabled = False
        return {"supported": getattr(sys, "frozen", False), "enabled": enabled, "managed_by": "windows"}
    if os.environ.get("FLATPAK_ID"):
        return {"supported": True, "enabled": _flatpak_marker().exists(), "managed_by": "flatpak-portal"}
    enabled = _linux_autostart_file().exists()
    return {"supported": supported(), "enabled": enabled, "managed_by": "linux"}


def configure(enabled: bool) -> dict[str, object]:
    if is_server_mode():
        return status()
    if not supported():
        raise RuntimeError("开发模式不支持设置开机自启动，请在打包后的客户端中使用")
    if sys.platform == "win32":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
            if enabled:
                command = f'"{Path(sys.executable).resolve()}" --background'
                winreg.SetValueEx(key, "MediaLinker", 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, "MediaLinker")
                except FileNotFoundError:
                    pass
        return status()

    if os.environ.get("FLATPAK_ID"):
        asyncio.run(_configure_flatpak_background(enabled))
        marker = _flatpak_marker()
        if enabled:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("enabled\n", encoding="utf-8")
        else:
            marker.unlink(missing_ok=True)
        return status()

    target = _linux_autostart_file()
    if enabled:
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.environ.get("FLATPAK_ID"):
            command = f"flatpak run {APP_ID} --background"
        else:
            command = f"{shlex.quote(str(Path(sys.executable).resolve()))} --background"
        target.write_text(
            "[Desktop Entry]\nType=Application\nName=MediaLinker 自动整理服务\n"
            f"Exec={command}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n",
            encoding="utf-8",
        )
    else:
        target.unlink(missing_ok=True)
    return status()
