import asyncio
import hmac

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.server_config import access_token, is_server_mode


router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=4096)


@router.post("/login")
async def login(request: LoginRequest) -> dict[str, object]:
    if not is_server_mode():
        return {"success": True, "server_mode": False}
    configured_token = access_token()
    if not configured_token:
        raise HTTPException(status_code=503, detail="服务器管理员尚未配置访问密码")
    if not hmac.compare_digest(request.password, configured_token):
        await asyncio.sleep(0.4)
        raise HTTPException(status_code=401, detail="访问密码错误")
    return {"success": True, "server_mode": True}
