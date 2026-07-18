import json
import os
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


router = APIRouter(tags=["organizer"])
INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
HISTORY_LIMIT = 200
_history_lock = threading.Lock()

if os.environ.get("FLATPAK_ID"):
    APP_ROOT = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "media-linker"
elif getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    APP_ROOT = Path(__file__).resolve().parents[3]
HISTORY_FILE = APP_ROOT / "config" / "task-history.json"


class LinkItem(BaseModel):
    source_path: str = Field(min_length=1)
    target_parts: list[str] = Field(min_length=1, max_length=10)
    target_name: str = Field(min_length=1, max_length=255)


class CreateLinksRequest(BaseModel):
    target_root: str = Field(min_length=1)
    items: list[LinkItem] = Field(min_length=1, max_length=5000)
    mode: Literal["hardlink", "move"] = "hardlink"
    title: str = Field(default="", max_length=255)
    media_type: Literal["movie", "tv", ""] = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_history() -> list[dict[str, object]]:
    try:
        payload = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"无法读取任务历史：{exc}") from exc
    return payload if isinstance(payload, list) else []


def _write_history(records: list[dict[str, object]]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = HISTORY_FILE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(records[:HISTORY_LIMIT], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(HISTORY_FILE)


def _prepend_history(record: dict[str, object]) -> None:
    with _history_lock:
        records = _load_history()
        records.insert(0, record)
        _write_history(records)


def _file_identity(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {"device": int(stat.st_dev), "inode": int(stat.st_ino), "size": int(stat.st_size)}


def _identity_matches(path: Path, identity: dict[str, object]) -> bool:
    try:
        current = _file_identity(path)
    except OSError:
        return False
    return (
        current["device"] == int(identity.get("device", -1))
        and current["inode"] == int(identity.get("inode", -1))
        and current["size"] == int(identity.get("size", -1))
    )


def validate_component(value: str) -> str:
    component = value.strip()
    if not component or component in (".", "..") or INVALID_COMPONENT.search(component):
        raise HTTPException(status_code=400, detail=f"目标名称包含 Windows 不允许的字符：{value}")
    if component.rstrip(". ").upper() in RESERVED_NAMES:
        raise HTTPException(status_code=400, detail=f"目标名称是 Windows 保留名称：{value}")
    if component.endswith((" ", ".")):
        raise HTTPException(status_code=400, detail=f"目标名称不能以空格或句点结尾：{value}")
    return component


def _rollback_completed(
    completed: list[tuple[Path, Path]], mode: Literal["hardlink", "move"]
) -> list[str]:
    errors: list[str] = []
    for source, target in reversed(completed):
        try:
            if mode == "hardlink":
                target.unlink(missing_ok=True)
            elif target.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                target.rename(source)
        except OSError as exc:
            errors.append(f"{target}: {exc}")
    return errors


def _history_record(
    request: CreateLinksRequest,
    target_root: Path,
    plans: list[tuple[Path, Path]],
    status: str,
    error: str = "",
    rollback_errors: list[str] | None = None,
) -> dict[str, object]:
    items = []
    for source, target in plans:
        identity_path = target if target.exists() else source
        identity = _file_identity(identity_path) if identity_path.exists() else {}
        items.append(
            {
                "source_path": str(source),
                "target_path": str(target),
                "identity": identity,
            }
        )
    return {
        "id": uuid.uuid4().hex,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "status": status,
        "mode": request.mode,
        "title": request.title.strip() or target_root.name,
        "media_type": request.media_type,
        "target_root": str(target_root),
        "item_count": len(plans),
        "items": items,
        "error": error,
        "rollback_errors": rollback_errors or [],
    }


@router.post("/execute")
def execute_organization(request: CreateLinksRequest) -> dict[str, object]:
    target_root = Path(request.target_root).expanduser().resolve()
    if not target_root.exists() or not target_root.is_dir():
        raise HTTPException(status_code=400, detail="输出根目录不存在或不是文件夹")

    plans: list[tuple[Path, Path]] = []
    seen_targets: set[str] = set()
    target_device = target_root.stat().st_dev

    for item in request.items:
        source = Path(item.source_path).expanduser().resolve()
        if not source.exists() or not source.is_file():
            raise HTTPException(status_code=400, detail=f"源文件不存在：{source}")
        if source.stat().st_dev != target_device:
            action = "创建硬链接" if request.mode == "hardlink" else "移动并重命名"
            raise HTTPException(
                status_code=400,
                detail=f"无法{action}：源文件与输出目录不在同一文件系统：{source.name}",
            )

        parts = [validate_component(part) for part in item.target_parts]
        target_name = validate_component(item.target_name)
        target = target_root.joinpath(*parts, target_name)
        target_key = os.path.normcase(str(target))
        if target_key in seen_targets:
            raise HTTPException(status_code=409, detail=f"生成计划中存在重复目标：{target}")
        seen_targets.add(target_key)
        if target.exists():
            raise HTTPException(status_code=409, detail=f"目标文件已存在，不会覆盖：{target}")
        plans.append((source, target))

    completed: list[tuple[Path, Path]] = []
    try:
        for source, target in plans:
            target.parent.mkdir(parents=True, exist_ok=True)
            if request.mode == "hardlink":
                os.link(source, target)
            else:
                source.rename(target)
            completed.append((source, target))

        record = _history_record(request, target_root, plans, "completed")
        try:
            _prepend_history(record)
        except (OSError, HTTPException) as exc:
            rollback_errors = _rollback_completed(completed, request.mode)
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            suffix = f"；回滚异常：{'；'.join(rollback_errors)}" if rollback_errors else ""
            raise HTTPException(status_code=500, detail=f"无法保存任务历史，本次操作已回滚：{detail}{suffix}") from exc
    except HTTPException:
        raise
    except OSError as exc:
        rollback_errors = _rollback_completed(completed, request.mode)
        record = _history_record(
            request,
            target_root,
            plans,
            "failed",
            error=str(exc),
            rollback_errors=rollback_errors,
        )
        try:
            _prepend_history(record)
        except (OSError, HTTPException):
            pass
        action = "创建硬链接" if request.mode == "hardlink" else "移动并重命名"
        rollback_message = "，已自动回滚" if not rollback_errors else "，但有部分文件回滚失败"
        raise HTTPException(status_code=500, detail=f"{action}失败{rollback_message}：{exc}") from exc

    return {
        "success": True,
        "operation": request.mode,
        "completed_count": len(completed),
        "target_root": str(target_root),
        "targets": [str(target) for _, target in completed],
        "task_id": record["id"],
        "history_recorded": True,
    }


@router.get("/history")
def list_history(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
    with _history_lock:
        records = _load_history()[:limit]
    return {"count": len(records), "tasks": records}


def _remove_empty_target_directories(target: Path, target_root: Path) -> None:
    current = target.parent
    while current != target_root and target_root in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


@router.post("/history/{task_id}/undo")
def undo_task(task_id: str) -> dict[str, object]:
    with _history_lock:
        records = _load_history()
        record_index = next((index for index, item in enumerate(records) if item.get("id") == task_id), -1)
        if record_index < 0:
            raise HTTPException(status_code=404, detail="没有找到这条任务记录")
        record = records[record_index]
        if record.get("status") != "completed":
            raise HTTPException(status_code=409, detail="只有已完成且尚未撤销的任务可以撤销")

        mode = str(record.get("mode"))
        items = list(record.get("items") or [])
        target_root = Path(str(record.get("target_root"))).resolve()

        for item in items:
            source = Path(str(item.get("source_path"))).resolve()
            target = Path(str(item.get("target_path"))).resolve()
            identity = dict(item.get("identity") or {})
            if not target.exists():
                raise HTTPException(status_code=409, detail=f"目标文件已不存在，无法安全撤销：{target}")
            if identity and not _identity_matches(target, identity):
                raise HTTPException(status_code=409, detail=f"目标文件已被替换，拒绝删除或移动：{target}")
            if mode == "hardlink":
                if not source.exists() or not os.path.samefile(source, target):
                    raise HTTPException(status_code=409, detail=f"源文件与目标已不再是同一硬链接：{target}")
            elif source.exists():
                raise HTTPException(status_code=409, detail=f"原位置已有文件，无法回滚移动操作：{source}")

        undone: list[tuple[Path, Path]] = []
        try:
            for item in reversed(items):
                source = Path(str(item.get("source_path"))).resolve()
                target = Path(str(item.get("target_path"))).resolve()
                if mode == "hardlink":
                    target.unlink()
                else:
                    source.parent.mkdir(parents=True, exist_ok=True)
                    target.rename(source)
                undone.append((source, target))
        except OSError as exc:
            restore_errors = []
            for source, target in reversed(undone):
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if mode == "hardlink":
                        os.link(source, target)
                    elif source.exists() and not target.exists():
                        source.rename(target)
                except OSError as restore_exc:
                    restore_errors.append(str(restore_exc))
            suffix = f"；恢复异常：{'；'.join(restore_errors)}" if restore_errors else ""
            raise HTTPException(status_code=500, detail=f"撤销失败，已尝试恢复撤销前状态：{exc}{suffix}") from exc

        for _, target in undone:
            _remove_empty_target_directories(target, target_root)

        record["status"] = "undone"
        record["updated_at"] = _utc_now()
        record["undone_at"] = _utc_now()
        records[record_index] = record
        try:
            _write_history(records)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"文件已撤销，但历史状态保存失败：{exc}") from exc

    return {
        "success": True,
        "task_id": task_id,
        "status": "undone",
        "restored_count": len(items),
        "mode": mode,
    }


@router.post("/hardlinks")
def create_hardlinks(request: CreateLinksRequest) -> dict[str, object]:
    request.mode = "hardlink"
    return execute_organization(request)
