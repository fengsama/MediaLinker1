import json
import os
from pathlib import Path


def is_server_mode() -> bool:
    return os.environ.get("MEDIALINKER_SERVER_MODE", "").strip().lower() in {"1", "true", "yes", "on"}


def access_token() -> str:
    return os.environ.get("MEDIALINKER_ACCESS_TOKEN", "").strip()


def config_directory() -> Path | None:
    value = os.environ.get("MEDIALINKER_CONFIG_DIR", "").strip()
    return Path(value).expanduser().resolve() if value else None


def allowed_roots() -> list[Path]:
    raw = os.environ.get("MEDIALINKER_ALLOWED_ROOTS", "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        values = parsed if isinstance(parsed, list) else [str(parsed)]
    except json.JSONDecodeError:
        values = [part.strip() for part in raw.split(",")]

    roots: list[Path] = []
    seen: set[str] = set()
    for value in values:
        if not str(value).strip():
            continue
        root = Path(str(value).strip()).expanduser().resolve()
        key = os.path.normcase(str(root))
        if key not in seen:
            roots.append(root)
            seen.add(key)
    return roots


def path_is_allowed(path: Path) -> bool:
    if not is_server_mode():
        return True
    resolved = path.expanduser().resolve()
    return any(resolved == root or root in resolved.parents for root in allowed_roots())
