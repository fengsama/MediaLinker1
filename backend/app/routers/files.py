import asyncio
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, HTTPException, Query

from app.models import ScanRequest, ScanResponse, SubtitleFile, VideoFile


router = APIRouter(tags=["files"])

VIDEO_EXTENSIONS = {
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".m4v",
    ".ts",
    ".webm",
}
SUBTITLE_EXTENSIONS = {
    ".srt",
    ".ass",
    ".ssa",
    ".vtt",
    ".sub",
    ".idx",
    ".sup",
    ".smi",
    ".sami",
    ".ttml",
    ".dfxp",
    ".stl",
    ".sbv",
    ".mpl",
    ".mpl2",
    ".usf",
    ".jss",
    ".rt",
    ".aqt",
    ".pjs",
    ".psb",
}
SUBTITLE_SUFFIX_SEPARATORS = (".", "_", "-", " ", "[", "(")
EPISODE_PATTERNS = (
    re.compile(
        r"(?:^|[.\s_\-\[(])s(?P<season>\d{1,2})[.\s_\-]*e(?P<episode>\d{1,4})(?:v\d+)?(?=$|[.\s_\-\])])",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|[.\s_\-\[(])(?:ep(?:isode)?|e)[.\s_\-]*(?P<episode>\d{1,4})(?:v\d+)?(?=$|[.\s_\-\])])",
        re.IGNORECASE,
    ),
    re.compile(r"第\s*(?P<episode>\d{1,4})\s*[集话話]", re.IGNORECASE),
)
SEASON_PATTERN = re.compile(
    r"(?:^|[.\s_\-\[(])(?:season|s)[.\s_\-]*(?P<season>\d{1,2})(?=$|[.\s_\-\])])",
    re.IGNORECASE,
)


class DirectoryPickerUnavailable(RuntimeError):
    pass


def _subtitle_matches_video(video_stem: str, subtitle_stem: str) -> bool:
    """Match exact names and common language/variant suffixes without prefix collisions."""
    normalized_video = video_stem.casefold()
    normalized_subtitle = subtitle_stem.casefold()
    if normalized_subtitle == normalized_video:
        return True
    if not normalized_subtitle.startswith(normalized_video):
        return False
    suffix = normalized_subtitle[len(normalized_video) :]
    return suffix.startswith(SUBTITLE_SUFFIX_SEPARATORS)


def _detect_episode(filename: str) -> tuple[int | None, int | None]:
    stem = Path(filename).stem
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(stem)
        if not match:
            continue
        groups = match.groupdict()
        season = int(groups["season"]) if groups.get("season") else None
        episode = int(groups["episode"])
        return season, episode
    season_match = SEASON_PATTERN.search(stem)
    season = int(season_match.group("season")) if season_match else None
    return season, None


def _natural_key(value: str) -> tuple[tuple[int, object], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in re.split(r"(\d+)", value)
        if part
    )


def _file_uri_to_path(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise DirectoryPickerUnavailable("系统文件选择器返回了不支持的路径格式")
    return unquote(parsed.path)


async def _pick_directory_with_portal(title: str) -> str:
    try:
        from dbus_next import BusType, Variant
        from dbus_next.aio import MessageBus
    except ImportError as exc:
        raise DirectoryPickerUnavailable("未安装 Linux 文件选择门户组件") from exc

    bus = None
    try:
        bus = await MessageBus(bus_type=BusType.SESSION).connect()
        desktop_path = "/org/freedesktop/portal/desktop"
        introspection = await bus.introspect("org.freedesktop.portal.Desktop", desktop_path)
        proxy = bus.get_proxy_object("org.freedesktop.portal.Desktop", desktop_path, introspection)
        chooser = proxy.get_interface("org.freedesktop.portal.FileChooser")
        token = f"medialinker_{uuid.uuid4().hex}"
        handle = await chooser.call_open_file(
            "",
            title,
            {
                "handle_token": Variant("s", token),
                "accept_label": Variant("s", "选择"),
                "modal": Variant("b", True),
                "multiple": Variant("b", False),
                "directory": Variant("b", True),
            },
        )

        request_introspection = await bus.introspect("org.freedesktop.portal.Desktop", handle)
        request_proxy = bus.get_proxy_object(
            "org.freedesktop.portal.Desktop", handle, request_introspection
        )
        request = request_proxy.get_interface("org.freedesktop.portal.Request")
        loop = asyncio.get_running_loop()
        response_future: asyncio.Future[tuple[int, dict[str, object]]] = loop.create_future()

        def receive_response(response: int, results: dict[str, object]) -> None:
            if not response_future.done():
                response_future.set_result((response, results))

        request.on_response(receive_response)
        response, results = await asyncio.wait_for(response_future, timeout=300)
        if response != 0:
            return ""
        uri_value = results.get("uris")
        uris = getattr(uri_value, "value", uri_value) or []
        if not uris:
            return ""
        return _file_uri_to_path(str(uris[0]))
    except asyncio.TimeoutError as exc:
        raise DirectoryPickerUnavailable("系统文件夹选择窗口等待超时") from exc
    except DirectoryPickerUnavailable:
        raise
    except Exception as exc:
        raise DirectoryPickerUnavailable("无法连接 Linux 系统文件选择门户") from exc
    finally:
        if bus is not None:
            bus.disconnect()


def _pick_directory_with_linux_command(title: str) -> str:
    if zenity := shutil.which("zenity"):
        result = subprocess.run(
            [zenity, "--file-selection", "--directory", f"--title={title}"],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    elif kdialog := shutil.which("kdialog"):
        result = subprocess.run(
            [kdialog, "--getexistingdirectory", str(Path.home()), "--title", title],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    else:
        raise DirectoryPickerUnavailable("未找到可用的 Linux 图形文件夹选择器")
    if result.returncode == 0:
        return result.stdout.strip()
    if result.returncode == 1:
        return ""
    raise DirectoryPickerUnavailable(result.stderr.strip() or "Linux 文件夹选择器启动失败")


def _pick_directory_with_tk(title: str) -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise DirectoryPickerUnavailable("当前程序未包含 Tk 图形组件") from exc

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        return filedialog.askdirectory(parent=root, title=title, mustexist=True)
    except tk.TclError as exc:
        raise DirectoryPickerUnavailable("无法打开 Tk 文件夹选择窗口") from exc
    finally:
        if root is not None:
            root.destroy()


@router.post("/pick-directory")
def pick_directory(purpose: str = Query(default="source", pattern="^(source|target)$")) -> dict[str, str | bool]:
    """Open a native directory picker on the machine running the API."""
    title = "选择硬链接输出文件夹" if purpose == "target" else "选择需要扫描的影视文件夹"
    errors = []

    if sys.platform.startswith("linux"):
        try:
            selected = asyncio.run(_pick_directory_with_portal(title))
            return {"selected": bool(selected), "path": selected}
        except DirectoryPickerUnavailable as exc:
            errors.append(str(exc))

        if not os.environ.get("FLATPAK_ID"):
            try:
                selected = _pick_directory_with_linux_command(title)
                return {"selected": bool(selected), "path": selected}
            except (DirectoryPickerUnavailable, subprocess.TimeoutExpired) as exc:
                errors.append(str(exc))

    try:
        selected = _pick_directory_with_tk(title)
        return {"selected": bool(selected), "path": selected}
    except DirectoryPickerUnavailable as exc:
        errors.append(str(exc))

    detail = "；".join(error for error in errors if error)
    raise HTTPException(
        status_code=500,
        detail=f"无法打开系统文件夹选择窗口，请确认程序正在图形桌面会话中运行。{detail}",
    )


@router.post("/scan", response_model=ScanResponse)
def scan_video_files(request: ScanRequest) -> ScanResponse:
    root = Path(request.path).expanduser()

    if not root.exists():
        raise HTTPException(status_code=404, detail="目录不存在或当前服务无法访问")
    if not root.is_dir():
        raise HTTPException(status_code=400, detail="指定路径不是目录")

    iterator = root.rglob("*") if request.recursive else root.glob("*")
    files: list[VideoFile] = []

    try:
        discovered = [path for path in iterator if path.is_file()]
        subtitles_by_directory: dict[Path, list[Path]] = {}
        for path in discovered:
            if path.suffix.lower() in SUBTITLE_EXTENSIONS:
                subtitles_by_directory.setdefault(path.parent, []).append(path)

        for path in discovered:
            if path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            stat = path.stat()
            video_stem = path.stem
            detected_season, detected_episode = _detect_episode(path.name)
            matched_subtitles = []
            for subtitle in subtitles_by_directory.get(path.parent, []):
                if not _subtitle_matches_video(video_stem, subtitle.stem):
                    continue
                subtitle_stat = subtitle.stat()
                matched_subtitles.append(
                    SubtitleFile(
                        name=subtitle.name,
                        path=str(subtitle.resolve()),
                        extension=subtitle.suffix.lower(),
                        size=subtitle_stat.st_size,
                    )
                )
            matched_subtitles.sort(key=lambda item: item.name.casefold())
            files.append(
                VideoFile(
                    name=path.name,
                    path=str(path.resolve()),
                    extension=path.suffix.lower(),
                    size=stat.st_size,
                    modified_at=datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    detected_season=detected_season,
                    detected_episode=detected_episode,
                    subtitles=matched_subtitles,
                )
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"没有权限访问目录：{exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"扫描目录失败：{exc}") from exc

    files.sort(key=lambda item: _natural_key(item.path))
    return ScanResponse(root=str(root.resolve()), count=len(files), files=files)
