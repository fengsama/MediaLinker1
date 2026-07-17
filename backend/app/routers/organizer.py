import os
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(tags=["organizer"])
INVALID_COMPONENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


class LinkItem(BaseModel):
    source_path: str = Field(min_length=1)
    target_parts: list[str] = Field(min_length=1, max_length=10)
    target_name: str = Field(min_length=1, max_length=255)


class CreateLinksRequest(BaseModel):
    target_root: str = Field(min_length=1)
    items: list[LinkItem] = Field(min_length=1, max_length=5000)
    mode: Literal["hardlink", "move"] = "hardlink"


def validate_component(value: str) -> str:
    component = value.strip()
    if not component or component in (".", "..") or INVALID_COMPONENT.search(component):
        raise HTTPException(status_code=400, detail=f"目标名称包含 Windows 不允许的字符：{value}")
    if component.rstrip(". ").upper() in RESERVED_NAMES:
        raise HTTPException(status_code=400, detail=f"目标名称是 Windows 保留名称：{value}")
    if component.endswith((" ", ".")):
        raise HTTPException(status_code=400, detail=f"目标名称不能以空格或句点结尾：{value}")
    return component


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
            action = "创建硬链接" if request.mode == "hardlink" else "安全移动并重命名"
            raise HTTPException(status_code=400, detail=f"无法{action}：源文件与输出目录不在同一文件系统：{source.name}")

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
    except OSError as exc:
        for source, target in reversed(completed):
            try:
                if request.mode == "hardlink":
                    target.unlink(missing_ok=True)
                elif target.exists() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    target.rename(source)
            except OSError:
                pass
        action = "创建硬链接" if request.mode == "hardlink" else "移动并重命名"
        raise HTTPException(status_code=500, detail=f"{action}失败，已尝试回滚本次操作：{exc}") from exc

    return {
        "success": True,
        "operation": request.mode,
        "completed_count": len(completed),
        "target_root": str(target_root),
        "targets": [str(target) for _, target in completed],
    }


@router.post("/hardlinks")
def create_hardlinks(request: CreateLinksRequest) -> dict[str, object]:
    request.mode = "hardlink"
    return execute_organization(request)
