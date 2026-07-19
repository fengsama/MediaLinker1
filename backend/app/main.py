import hmac
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import auth, files, health, lifecycle, metadata, organizer, updates
from app.server_config import access_token, is_server_mode
from app.version import __version__


app = FastAPI(
    title="影视硬链接整理工具 API",
    description="扫描影视文件，并为后续硬链接整理功能提供基础服务。",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def protect_server_api(request: Request, call_next):
    if not is_server_mode() or not request.url.path.startswith("/api/"):
        return await call_next(request)
    if request.url.path in {"/api/health", "/api/auth/login"}:
        return await call_next(request)
    configured_token = access_token()
    if not configured_token:
        return JSONResponse(status_code=503, content={"detail": "服务器管理员尚未配置访问密码"})
    authorization = request.headers.get("authorization", "")
    supplied_token = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    if not supplied_token or not hmac.compare_digest(supplied_token, configured_token):
        return JSONResponse(status_code=401, content={"detail": "请先输入服务器访问密码"})
    return await call_next(request)

app.include_router(auth.router, prefix="/api/auth")
app.include_router(health.router, prefix="/api")
app.include_router(lifecycle.router, prefix="/api")
app.include_router(files.router, prefix="/api/files")
app.include_router(metadata.router, prefix="/api/metadata")
app.include_router(organizer.router, prefix="/api/organizer")
app.include_router(updates.router, prefix="/api/update")


if getattr(sys, "frozen", False):
    frontend_dir = Path(getattr(sys, "_MEIPASS")) / "frontend_dist"
else:
    frontend_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    @app.get("/", tags=["root"])
    def root() -> dict[str, str]:
        return {"message": "影视硬链接整理工具 API", "docs": "/docs"}
