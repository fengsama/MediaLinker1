from datetime import datetime, timezone

from fastapi import APIRouter

from app.version import __version__


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "media-linker-api",
        "version": __version__,
        "time": datetime.now(timezone.utc).isoformat(),
    }
