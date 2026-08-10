import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator

from app.models import ScanRequest, VideoFile
from app.routers.files import scan_video_files
from app.routers.organizer import CreateLinksRequest, LinkItem, execute_organization
from app.server_config import config_directory, is_server_mode, path_is_allowed


if os.environ.get("FLATPAK_ID"):
    APP_ROOT = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "media-linker"
elif getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    APP_ROOT = Path(__file__).resolve().parents[2]

AUTOMATION_DIR = config_directory() or APP_ROOT / "config"
CONFIG_FILE = AUTOMATION_DIR / "automation.json"
STATE_FILE = AUTOMATION_DIR / "automation-state.json"
EVENT_LIMIT = 200


class WatchRule(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str = Field(default="自动整理规则", min_length=1, max_length=120)
    enabled: bool = True
    source_path: str = Field(min_length=1, max_length=4096)
    target_root: str = Field(min_length=1, max_length=4096)
    media_type: Literal["movie", "tv"] = "tv"
    title: str = Field(min_length=1, max_length=255)
    year: str = Field(default="", max_length=4, pattern=r"^$|^\d{4}$")
    season: int = Field(default=1, ge=0, le=99)
    recursive: bool = True
    include_subtitles: bool = True

    @model_validator(mode="after")
    def validate_paths(self):
        source = Path(self.source_path).expanduser().resolve()
        target = Path(self.target_root).expanduser().resolve()
        if source == target or source in target.parents:
            raise ValueError("输出目录不能位于监控目录内部，否则会形成重复扫描")
        if is_server_mode() and (not path_is_allowed(source) or not path_is_allowed(target)):
            raise ValueError("监控目录或输出目录不在 NAS 管理员允许访问的范围内")
        return self


class AutomationConfig(BaseModel):
    enabled: bool = False
    start_on_boot: bool = False
    scan_interval_seconds: int = Field(default=15, ge=5, le=3600)
    settle_seconds: int = Field(default=60, ge=10, le=86400)
    rules: list[WatchRule] = Field(default_factory=list, max_length=100)


_lock = threading.RLock()
_wake_event = threading.Event()
_stop_event = threading.Event()
_worker: threading.Thread | None = None
_seen: dict[str, tuple[str, float]] = {}
_scan_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load_config() -> AutomationConfig:
    with _lock:
        return AutomationConfig.model_validate(_read_json(CONFIG_FILE, {}))


def save_config(config: AutomationConfig) -> None:
    with _lock:
        _write_json(CONFIG_FILE, config.model_dump())
    _wake_event.set()


def _load_state() -> dict[str, object]:
    payload = _read_json(STATE_FILE, {})
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("files", {})
    payload.setdefault("events", [])
    return payload


def _save_state(state: dict[str, object]) -> None:
    state["events"] = list(state.get("events") or [])[:EVENT_LIMIT]
    _write_json(STATE_FILE, state)


def _record_event(state: dict[str, object], level: str, message: str, rule: WatchRule | None = None, path: str = "") -> None:
    events = list(state.get("events") or [])
    events.insert(0, {
        "id": uuid.uuid4().hex,
        "created_at": _utc_now(),
        "level": level,
        "message": message,
        "rule_id": rule.id if rule else "",
        "rule_name": rule.name if rule else "",
        "path": path,
    })
    state["events"] = events[:EVENT_LIMIT]


def _signature(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_size}:{stat.st_mtime_ns}"


def _is_stable(path: Path, signature: str, settle_seconds: int) -> bool:
    now = time.monotonic()
    key = os.path.normcase(str(path))
    previous = _seen.get(key)
    if previous is None or previous[0] != signature:
        _seen[key] = (signature, now)
        return False
    return now - previous[1] >= settle_seconds


def _safe_title(value: str) -> str:
    cleaned = "".join("-" if character in '<>:"/\\|?*' or ord(character) < 32 else character for character in value)
    return cleaned.rstrip(" .").strip()


def _targets_for_video(rule: WatchRule, video: VideoFile) -> list[tuple[Path, list[str], str]]:
    title = _safe_title(rule.title)
    source = Path(video.path)
    if rule.media_type == "movie":
        display_title = f"{title} ({rule.year})" if rule.year else title
        target_name = f"{display_title}{video.extension}"
        targets = [(source, [display_title], target_name)]
    else:
        if video.detected_episode is None:
            raise ValueError("文件名中未识别到集数（请使用 S01E01、E01 或“第1集”等格式）")
        season = video.detected_season if video.detected_season is not None else rule.season
        episode = video.detected_episode
        show_folder = f"{title} ({rule.year})" if rule.year else title
        season_folder = f"Season {season:02d}"
        target_name = f"{title} S{season:02d}E{episode:02d}{video.extension}"
        targets = [(source, [show_folder, season_folder], target_name)]

    if not rule.include_subtitles:
        return targets
    source_stem = source.stem
    target_stem = Path(targets[0][2]).stem
    for subtitle in video.subtitles:
        subtitle_path = Path(subtitle.path)
        suffix = subtitle_path.stem[len(source_stem):]
        targets.append((subtitle_path, targets[0][1], f"{target_stem}{suffix}{subtitle.extension}"))
    return targets


def _process_rule(rule: WatchRule, config: AutomationConfig, state: dict[str, object]) -> tuple[int, int]:
    source_root = Path(rule.source_path).expanduser().resolve()
    target_root = Path(rule.target_root).expanduser().resolve()
    if not source_root.is_dir():
        raise ValueError("监控目录不存在或无法访问")
    if not target_root.is_dir():
        raise ValueError("输出目录不存在或无法访问")

    response = scan_video_files(ScanRequest(path=str(source_root), recursive=rule.recursive))
    file_state = dict(state.get("files") or {})
    completed = 0
    pending = 0

    for video in response.files:
        video_path = Path(video.path)
        try:
            targets = _targets_for_video(rule, video)
        except ValueError as exc:
            signature = _signature(video_path)
            key = f"{rule.id}:{os.path.normcase(str(video_path))}"
            previous = dict(file_state.get(key) or {})
            if previous.get("signature") != signature or previous.get("status") != "waiting_name":
                _record_event(state, "warning", str(exc), rule, str(video_path))
            file_state[key] = {"signature": signature, "status": "waiting_name", "updated_at": _utc_now()}
            pending += 1
            continue

        items: list[LinkItem] = []
        source_keys: list[tuple[str, str, str]] = []
        all_stable = True
        for source, target_parts, target_name in targets:
            signature = _signature(source)
            key = f"{rule.id}:{os.path.normcase(str(source))}"
            target = target_root.joinpath(*target_parts, target_name)
            previous = dict(file_state.get(key) or {})
            if previous.get("signature") == signature and previous.get("status") == "completed":
                continue
            if target.exists():
                try:
                    if os.path.samefile(source, target):
                        file_state[key] = {"signature": signature, "status": "completed", "target": str(target), "updated_at": _utc_now()}
                        continue
                except OSError:
                    pass
                if previous.get("signature") != signature or previous.get("status") != "conflict":
                    _record_event(state, "error", f"目标文件已存在且不是同一硬链接：{target}", rule, str(source))
                file_state[key] = {"signature": signature, "status": "conflict", "target": str(target), "updated_at": _utc_now()}
                all_stable = False
                pending += 1
                continue
            if not _is_stable(source, signature, config.settle_seconds):
                all_stable = False
                pending += 1
                continue
            items.append(LinkItem(source_path=str(source), target_parts=target_parts, target_name=target_name))
            source_keys.append((key, signature, str(target)))

        if not items or not all_stable:
            continue
        try:
            result = execute_organization(CreateLinksRequest(
                target_root=str(target_root),
                items=items,
                mode="hardlink",
                title=f"自动：{rule.title}",
                media_type=rule.media_type,
            ))
            for key, signature, target in source_keys:
                file_state[key] = {"signature": signature, "status": "completed", "target": target, "updated_at": _utc_now()}
            completed += len(items)
            _record_event(state, "success", f"已自动创建 {result['completed_count']} 个硬链接", rule, str(video_path))
        except HTTPException as exc:
            for key, signature, target in source_keys:
                file_state[key] = {"signature": signature, "status": "failed", "target": target, "updated_at": _utc_now()}
            _record_event(state, "error", str(exc.detail), rule, str(video_path))
            pending += len(items)

    state["files"] = file_state
    return completed, pending


def scan_once() -> dict[str, object]:
    if not _scan_lock.acquire(blocking=False):
        return {"running": True, "message": "自动扫描正在进行中"}
    try:
        config = load_config()
        state = _load_state()
        total_completed = 0
        total_pending = 0
        for rule in config.rules:
            if not rule.enabled:
                continue
            try:
                completed, pending = _process_rule(rule, config, state)
                total_completed += completed
                total_pending += pending
            except (HTTPException, OSError, ValueError) as exc:
                detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
                _record_event(state, "error", detail, rule, rule.source_path)
        state["last_scan_at"] = _utc_now()
        state["last_completed_count"] = total_completed
        state["pending_count"] = total_pending
        _save_state(state)
        return {"running": False, "completed_count": total_completed, "pending_count": total_pending, "last_scan_at": state["last_scan_at"]}
    finally:
        _scan_lock.release()


def _worker_loop() -> None:
    while not _stop_event.is_set():
        try:
            config = load_config()
            if config.enabled:
                scan_once()
            wait_seconds = config.scan_interval_seconds
        except Exception:
            wait_seconds = 30
        _wake_event.wait(wait_seconds)
        _wake_event.clear()


def start_worker() -> None:
    global _worker
    with _lock:
        if _worker and _worker.is_alive():
            return
        _stop_event.clear()
        _worker = threading.Thread(target=_worker_loop, name="medialinker-automation", daemon=True)
        _worker.start()


def stop_worker() -> None:
    _stop_event.set()
    _wake_event.set()


def worker_running() -> bool:
    return bool(_worker and _worker.is_alive())


def should_keep_alive() -> bool:
    try:
        return load_config().enabled
    except Exception:
        return False


def automation_status() -> dict[str, object]:
    config = load_config()
    state = _load_state()
    return {
        **config.model_dump(),
        "worker_running": worker_running(),
        "last_scan_at": state.get("last_scan_at", ""),
        "last_completed_count": state.get("last_completed_count", 0),
        "pending_count": state.get("pending_count", 0),
        "recent_events": list(state.get("events") or [])[:50],
    }
