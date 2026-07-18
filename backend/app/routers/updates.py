from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query

from app.version import GITHUB_LATEST_RELEASE_API, __version__


router = APIRouter(tags=["updates"])

_CACHE_SECONDS = 600
_MAX_DOWNLOAD_BYTES = 600 * 1024 * 1024
_release_cache: dict[str, Any] = {"checked_at": 0.0, "release": None}
_update_lock = threading.Lock()
_update_started = False


def _version_tuple(value: str) -> tuple[int, ...]:
    normalized = value.strip().lower().removeprefix("v").split("-", 1)[0]
    parts = []
    for item in normalized.split("."):
        digits = "".join(character for character in item if character.isdigit())
        parts.append(int(digits or 0))
    return tuple((parts + [0, 0, 0])[:3])


def _platform_info() -> tuple[str, str | None, bool]:
    frozen = bool(getattr(sys, "frozen", False))
    if os.environ.get("FLATPAK_ID"):
        return "flatpak", "MediaLinker-x86_64.flatpak", False
    if sys.platform == "win32":
        installed = frozen and (Path(sys.executable).resolve().parent / "installed.marker").is_file()
        if installed:
            return "windows-installer", "MediaLinker-Setup-x64.exe", True
        return "windows-portable", "MediaLinker-Windows-x64.zip", frozen
    if sys.platform.startswith("linux"):
        return "linux", "MediaLinker-Linux-x86_64.tar.gz", frozen
    return platform.system().lower() or "unknown", None, False


def _github_request_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"MediaLinker/{__version__}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 403:
            return _github_release_fallback()
        if exc.code == 404:
            raise HTTPException(
                status_code=502,
                detail="未找到可公开访问的 GitHub Release，请确认仓库和 Release 为公开状态。",
            ) from exc
        raise HTTPException(status_code=502, detail=f"GitHub 返回错误：{exc.code}") from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="暂时无法连接 GitHub 检查更新。") from exc


def _github_release_fallback() -> dict[str, Any]:
    latest_url = "https://github.com/fengsama/MediaLinker1/releases/latest"
    request = Request(latest_url, headers={"User-Agent": f"MediaLinker/{__version__}"})
    try:
        with urlopen(request, timeout=15) as response:
            release_url = response.geturl()
        tag_name = unquote(release_url.rstrip("/").rsplit("/", 1)[-1])
        if not tag_name.lower().startswith("v"):
            raise ValueError("latest release redirect did not contain a version tag")
        asset_names = (
            "MediaLinker-Setup-x64.exe",
            "MediaLinker-Windows-x64.zip",
            "MediaLinker-Linux-x86_64.tar.gz",
            "MediaLinker-x86_64.flatpak",
        )
        download_root = f"https://github.com/fengsama/MediaLinker1/releases/download/{tag_name}"
        return {
            "tag_name": tag_name,
            "html_url": release_url,
            "published_at": "",
            "body": "",
            "assets": [
                {
                    "name": name,
                    "browser_download_url": f"{download_root}/{name}",
                    "size": 0,
                    "digest": "",
                }
                for name in asset_names
            ],
        }
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="GitHub 更新接口暂时受限，请稍后重试。") from exc


def _latest_release(force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    cached = _release_cache.get("release")
    if not force and cached and now - float(_release_cache["checked_at"]) < _CACHE_SECONDS:
        return cached
    release = _github_request_json(GITHUB_LATEST_RELEASE_API)
    _release_cache.update({"checked_at": now, "release": release})
    return release


def _release_info(force: bool = False) -> dict[str, Any]:
    release = _latest_release(force=force)
    latest_version = str(release.get("tag_name") or "0.0.0").removeprefix("v")
    update_available = _version_tuple(latest_version) > _version_tuple(__version__)
    platform_name, expected_asset, can_auto_update = _platform_info()
    asset = next(
        (item for item in release.get("assets", []) if item.get("name") == expected_asset),
        None,
    )
    return {
        "current_version": __version__,
        "latest_version": latest_version,
        "update_available": update_available,
        "release_url": release.get("html_url") or "",
        "published_at": release.get("published_at") or "",
        "release_notes": release.get("body") or "",
        "platform": platform_name,
        "packaged": bool(getattr(sys, "frozen", False)),
        "asset_name": expected_asset or "",
        "asset_url": (asset or {}).get("browser_download_url") or "",
        "asset_size": int((asset or {}).get("size") or 0),
        "asset_digest": (asset or {}).get("digest") or "",
        "can_auto_update": bool(can_auto_update and asset),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/check")
def check_update(force: bool = Query(default=False)) -> dict[str, Any]:
    return _release_info(force=force)


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        root = destination.resolve()
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if root != target and root not in target.parents:
                raise HTTPException(status_code=502, detail="更新包包含不安全的文件路径。")
        bundle.extractall(destination)


def _safe_extract_tar(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as bundle:
        root = destination.resolve()
        for member in bundle.getmembers():
            if member.issym() or member.islnk():
                raise HTTPException(status_code=502, detail="更新包包含不安全的链接文件。")
            target = (destination / member.name).resolve()
            if root != target and root not in target.parents:
                raise HTTPException(status_code=502, detail="更新包包含不安全的文件路径。")
        bundle.extractall(destination)


def _download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": f"MediaLinker/{__version__}"})
    try:
        with urlopen(request, timeout=45) as response, destination.open("wb") as output:
            expected = int(response.headers.get("Content-Length") or 0)
            if expected > _MAX_DOWNLOAD_BYTES:
                raise HTTPException(status_code=502, detail="更新包大小超过安全限制。")
            downloaded = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                downloaded += len(block)
                if downloaded > _MAX_DOWNLOAD_BYTES:
                    raise HTTPException(status_code=502, detail="更新包大小超过安全限制。")
                output.write(block)
    except HTTPException:
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=502, detail="下载更新包失败，请稍后重试。") from exc


def _verify_download(path: Path, expected_size: int, expected_digest: str) -> None:
    if expected_size and path.stat().st_size != expected_size:
        raise HTTPException(status_code=502, detail="更新包大小校验失败，已取消自动更新。")
    if not expected_digest.startswith("sha256:"):
        return
    actual = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            actual.update(block)
    if actual.hexdigest().lower() != expected_digest.split(":", 1)[1].lower():
        raise HTTPException(status_code=502, detail="更新包完整性校验失败，已取消自动更新。")


def _quote_powershell(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _prepare_windows_updater(staged_app: Path, install_dir: Path) -> Path:
    updater_dir = Path(tempfile.mkdtemp(prefix="medialinker-updater-"))
    script = updater_dir / "update.ps1"
    backup_dir = install_dir.with_name(f"{install_dir.name}.update-backup")
    log_file = updater_dir / "update.log"
    script.write_text(
        f"""
$processId = {os.getpid()}
$installDir = {_quote_powershell(str(install_dir))}
$stagedDir = {_quote_powershell(str(staged_app))}
$backupDir = {_quote_powershell(str(backup_dir))}
$logFile = {_quote_powershell(str(log_file))}
while (Get-Process -Id $processId -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 500 }}
try {{
    if (Test-Path -LiteralPath $backupDir) {{ Remove-Item -LiteralPath $backupDir -Recurse -Force }}
    Move-Item -LiteralPath $installDir -Destination $backupDir
    Move-Item -LiteralPath $stagedDir -Destination $installDir
    $oldConfig = Join-Path $backupDir 'config'
    if (Test-Path -LiteralPath $oldConfig) {{ Copy-Item -LiteralPath $oldConfig -Destination $installDir -Recurse -Force }}
    Start-Process -FilePath (Join-Path $installDir 'MediaLinker.exe')
    Start-Sleep -Seconds 5
    Remove-Item -LiteralPath $backupDir -Recurse -Force
}} catch {{
    $_ | Out-String | Set-Content -LiteralPath $logFile -Encoding UTF8
    if ((-not (Test-Path -LiteralPath $installDir)) -and (Test-Path -LiteralPath $backupDir)) {{
        Move-Item -LiteralPath $backupDir -Destination $installDir
        Start-Process -FilePath (Join-Path $installDir 'MediaLinker.exe')
    }}
}}
""".strip(),
        encoding="utf-8-sig",
    )
    return script


def _prepare_windows_installer_updater(installer: Path, install_dir: Path) -> Path:
    updater_dir = Path(tempfile.mkdtemp(prefix="medialinker-installer-"))
    script = updater_dir / "install-update.ps1"
    log_file = updater_dir / "update.log"
    executable = install_dir / "MediaLinker.exe"
    script.write_text(
        f"""
$processId = {os.getpid()}
$installer = {_quote_powershell(str(installer))}
$executable = {_quote_powershell(str(executable))}
$logFile = {_quote_powershell(str(log_file))}
while (Get-Process -Id $processId -ErrorAction SilentlyContinue) {{ Start-Sleep -Milliseconds 500 }}
try {{
    $process = Start-Process -FilePath $installer -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS' -Wait -PassThru
    if ($process.ExitCode -ne 0) {{ throw "安装程序退出代码：$($process.ExitCode)" }}
    Start-Process -FilePath $executable
}} catch {{
    $_ | Out-String | Set-Content -LiteralPath $logFile -Encoding UTF8
    if (Test-Path -LiteralPath $executable) {{ Start-Process -FilePath $executable }}
}}
""".strip(),
        encoding="utf-8-sig",
    )
    return script


def _quote_shell(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _prepare_linux_updater(staged_app: Path, install_dir: Path) -> Path:
    updater_dir = Path(tempfile.mkdtemp(prefix="medialinker-updater-"))
    script = updater_dir / "update.sh"
    backup_dir = install_dir.with_name(f"{install_dir.name}.update-backup")
    log_file = updater_dir / "update.log"
    script.write_text(
        f"""#!/bin/sh
pid={os.getpid()}
install_dir={_quote_shell(str(install_dir))}
staged_dir={_quote_shell(str(staged_app))}
backup_dir={_quote_shell(str(backup_dir))}
log_file={_quote_shell(str(log_file))}
while kill -0 "$pid" 2>/dev/null; do sleep 1; done
{{
  rm -rf -- "$backup_dir"
  mv -- "$install_dir" "$backup_dir"
  mv -- "$staged_dir" "$install_dir"
  if [ -d "$backup_dir/config" ]; then cp -a -- "$backup_dir/config" "$install_dir/"; fi
  chmod +x "$install_dir/MediaLinker"
  "$install_dir/MediaLinker" >/dev/null 2>&1 &
  sleep 5
  rm -rf -- "$backup_dir"
}} 2>"$log_file" || {{
  if [ ! -d "$install_dir" ] && [ -d "$backup_dir" ]; then mv -- "$backup_dir" "$install_dir"; fi
}}
""",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _exit_after_response() -> None:
    time.sleep(1.5)
    os._exit(0)


@router.post("/apply")
def apply_update() -> dict[str, Any]:
    global _update_started
    with _update_lock:
        if _update_started:
            return {"status": "already_started", "message": "更新已开始，请稍候。"}
        info = _release_info(force=True)
        if not info["update_available"]:
            return {"status": "up_to_date", "message": "当前已经是最新版本。", **info}
        if not info["can_auto_update"]:
            raise HTTPException(
                status_code=409,
                detail="当前运行方式不支持自动替换程序，请从 Release 页面手动下载安装。",
            )
        _update_started = True

    try:
        install_dir = Path(sys.executable).resolve().parent
        update_root = Path(tempfile.mkdtemp(prefix="medialinker-update-"))
        platform_name = str(info["platform"])
        archive = update_root / str(info["asset_name"])
        _download(str(info["asset_url"]), archive)
        _verify_download(archive, int(info["asset_size"]), str(info["asset_digest"]))

        if platform_name == "windows-installer":
            script = _prepare_windows_installer_updater(archive, install_dir)
            creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                creationflags=creation_flags,
                close_fds=True,
            )
            threading.Thread(target=_exit_after_response, daemon=True).start()
            return {
                "status": "restarting",
                "message": "新版安装包已下载，软件即将自动安装并重新启动。",
                "current_version": __version__,
                "latest_version": info["latest_version"],
            }

        staging = update_root / "staging"
        staging.mkdir()
        if platform_name == "windows-portable":
            _safe_extract_zip(archive, staging)
            executable_name = "MediaLinker.exe"
        else:
            _safe_extract_tar(archive, staging)
            executable_name = "MediaLinker"

        candidates = [path.parent for path in staging.rglob(executable_name)]
        if len(candidates) != 1:
            raise HTTPException(status_code=502, detail="更新包结构不正确，已取消自动更新。")

        if platform_name == "windows-portable":
            script = _prepare_windows_updater(candidates[0], install_dir)
            creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
                subprocess, "DETACHED_PROCESS", 0
            )
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                creationflags=creation_flags,
                close_fds=True,
            )
        else:
            script = _prepare_linux_updater(candidates[0], install_dir)
            subprocess.Popen(
                ["/bin/sh", str(script)],
                start_new_session=True,
                close_fds=True,
            )

        threading.Thread(target=_exit_after_response, daemon=True).start()
        return {
            "status": "restarting",
            "message": "新版本已下载，软件即将完成替换并重新启动。",
            "current_version": __version__,
            "latest_version": info["latest_version"],
        }
    except Exception:
        with _update_lock:
            _update_started = False
        raise
