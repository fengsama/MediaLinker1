import asyncio
import os
import sys

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter(tags=["lifecycle"])

_SHUTDOWN_GRACE_SECONDS = 6
_active_connections: set[int] = set()
_shutdown_tasks: set[asyncio.Task[None]] = set()


async def _shutdown_when_idle() -> None:
    await asyncio.sleep(_SHUTDOWN_GRACE_SECONDS)
    if not _active_connections:
        os._exit(0)


@router.websocket("/lifecycle")
async def lifecycle_connection(websocket: WebSocket) -> None:
    """Keep packaged desktop service alive while at least one browser page is open."""
    await websocket.accept()
    connection_id = id(websocket)
    _active_connections.add(connection_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(connection_id)
        if getattr(sys, "frozen", False) and not _active_connections:
            task = asyncio.create_task(_shutdown_when_idle())
            _shutdown_tasks.add(task)
            task.add_done_callback(_shutdown_tasks.discard)
