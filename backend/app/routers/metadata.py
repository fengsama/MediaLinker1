import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.server_config import config_directory


router = APIRouter(tags=["metadata"])
TMDB_API_ROOT = "https://api.themoviedb.org/3"
TMDB_IMAGE_ROOT = "https://image.tmdb.org/t/p/w342"
if os.environ.get("FLATPAK_ID"):
    APP_ROOT = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "media-linker"
elif getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).resolve().parent
else:
    APP_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_FILE = (config_directory() / "settings.json") if config_directory() else APP_ROOT / "config" / "settings.json"

GENRES = {
    16: "动画", 18: "剧情", 28: "动作", 35: "喜剧", 36: "历史", 37: "西部",
    53: "惊悚", 80: "犯罪", 99: "纪录片", 10749: "爱情", 10751: "家庭",
    10752: "战争", 10759: "动作冒险", 10762: "儿童", 10763: "新闻",
    10764: "真人秀", 10765: "科幻奇幻", 10766: "肥皂剧", 10767: "脱口秀",
    10768: "战争政治", 9648: "悬疑", 878: "科幻", 14: "奇幻", 27: "恐怖",
    12: "冒险", 10402: "音乐", 10770: "电视电影",
}
LANGUAGES = {"zh": "中文", "ja": "日语", "en": "英语", "ko": "韩语", "fr": "法语", "de": "德语", "es": "西班牙语"}


class TokenConfig(BaseModel):
    token: str = Field(min_length=20, max_length=2048)


def load_token() -> str:
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return str(data.get("tmdb_read_access_token") or "").strip()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""


def tmdb_request(path: str, token: str, params: dict[str, object] | None = None) -> object:
    query = f"?{urlencode(params)}" if params else ""
    request = Request(
        f"{TMDB_API_ROOT}{path}{query}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "MediaLinker/0.5"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise HTTPException(status_code=401, detail="TMDB 凭证无效，请重新配置 API Read Access Token") from exc
        raise HTTPException(status_code=502, detail=f"TMDB 返回错误：{exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise HTTPException(status_code=502, detail="暂时无法连接 TMDB，请检查网络后重试") from exc


@router.get("/config/status")
def config_status() -> dict[str, bool | str]:
    return {"configured": bool(load_token()), "provider": "TMDB", "language": "zh-CN"}


@router.post("/config")
def save_config(config: TokenConfig) -> dict[str, bool | str]:
    token = config.token.strip()
    tmdb_request("/configuration", token)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = SETTINGS_FILE.with_suffix(".tmp")
    temp_file.write_text(json.dumps({"tmdb_read_access_token": token}, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(SETTINGS_FILE)
    return {"saved": True, "provider": "TMDB", "language": "zh-CN"}


@router.get("/search")
def search_metadata(q: str = Query(min_length=1, max_length=120, description="影视名称")) -> dict[str, object]:
    token = load_token()
    if not token:
        raise HTTPException(status_code=503, detail="尚未配置 TMDB API Read Access Token")

    payload = tmdb_request(
        "/search/multi",
        token,
        {"query": q.strip(), "language": "zh-CN", "include_adult": "false", "page": 1},
    )
    results = []
    for item in payload.get("results", []):
        media_type = item.get("media_type")
        if media_type not in ("movie", "tv"):
            continue
        title = item.get("title") if media_type == "movie" else item.get("name")
        original_title = item.get("original_title") if media_type == "movie" else item.get("original_name")
        date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
        poster_path = item.get("poster_path") or ""
        results.append({
            "id": item.get("id"),
            "title": title or original_title or "未知名称",
            "original_title": original_title or "",
            "year": (date or "")[:4],
            "media_type": media_type,
            "media_type_label": "电影" if media_type == "movie" else "电视剧",
            "language": LANGUAGES.get(item.get("original_language"), item.get("original_language") or ""),
            "genres": [GENRES[genre_id] for genre_id in item.get("genre_ids", []) if genre_id in GENRES],
            "country": " / ".join(item.get("origin_country") or []),
            "poster": f"{TMDB_IMAGE_ROOT}{poster_path}" if poster_path else "",
            "overview": item.get("overview") or "",
            "provider": "TMDB",
            "popularity": item.get("popularity") or 0,
        })

    return {"query": q.strip(), "provider": "TMDB", "language": "zh-CN", "count": len(results), "results": results[:20]}
