from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

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
SUBTITLE_EXTENSIONS = {".srt"}


@router.post("/pick-directory")
def pick_directory(purpose: str = Query(default="source", pattern="^(source|target)$")) -> dict[str, str | bool]:
    """Open the native Windows directory picker on the machine running the API."""
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.update()
        selected = filedialog.askdirectory(
            parent=root,
            title="选择硬链接输出文件夹" if purpose == "target" else "选择需要扫描的影视文件夹",
            mustexist=True,
        )
        return {"selected": bool(selected), "path": selected}
    except tk.TclError as exc:
        raise HTTPException(
            status_code=500,
            detail="无法打开系统文件夹选择窗口，请确认程序正在图形桌面会话中运行",
        ) from exc
    finally:
        if root is not None:
            root.destroy()


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
            video_stem = path.stem.casefold()
            matched_subtitles = []
            for subtitle in subtitles_by_directory.get(path.parent, []):
                subtitle_stem = subtitle.stem.casefold()
                if subtitle_stem != video_stem and not subtitle_stem.startswith(f"{video_stem}."):
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
                    subtitles=matched_subtitles,
                )
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"没有权限访问目录：{exc}") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"扫描目录失败：{exc}") from exc

    files.sort(key=lambda item: item.path.casefold())
    return ScanResponse(root=str(root.resolve()), count=len(files), files=files)
