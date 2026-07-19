from datetime import datetime, timezone

from fastapi import APIRouter

from app.version import __version__
from app.server_config import access_token, allowed_roots, is_server_mode


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, object]:
    server_mode = is_server_mode()
    return {
        "status": "ok",
        "service": "media-linker-api",
        "version": __version__,
        "time": datetime.now(timezone.utc).isoformat(),
        "server_mode": server_mode,
        "authentication_required": server_mode,
        "server_configured": not server_mode or bool(access_token()),
        "allowed_root_count": len(allowed_roots()) if server_mode else 0,
    }
