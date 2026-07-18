import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import files, health, metadata, organizer, updates
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

app.include_router(health.router, prefix="/api")
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
