from fastapi import APIRouter, BackgroundTasks, HTTPException

from app import automation
from app.automation import AutomationConfig
from app.autostart import configure as configure_autostart
from app.autostart import status as autostart_status


router = APIRouter(tags=["automation"])


@router.get("/status")
def get_status() -> dict[str, object]:
    return {**automation.automation_status(), "autostart": autostart_status()}


@router.put("/config")
def update_config(config: AutomationConfig) -> dict[str, object]:
    try:
        startup = autostart_status()
        if config.start_on_boot != bool(startup.get("enabled")):
            startup = configure_autostart(config.start_on_boot)
    except (OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=f"开机自启动设置失败：{exc}") from exc
    automation.save_config(config)
    return {**automation.automation_status(), "autostart": startup}


@router.post("/scan-now")
def scan_now(background_tasks: BackgroundTasks) -> dict[str, object]:
    background_tasks.add_task(automation.scan_once)
    return {"started": True, "message": "已开始扫描监控目录"}
