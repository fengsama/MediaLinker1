import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from app.main import app


if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


def choose_port() -> int:
    for port in range(8787, 8800):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("没有可用端口，请关闭其他 MediaLinker 实例后重试")


def open_browser(port: int) -> None:
    time.sleep(1.2)
    webbrowser.open(f"http://127.0.0.1:{port}")


def main() -> None:
    server_mode = os.environ.get("MEDIALINKER_SERVER_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    port = int(os.environ.get("MEDIALINKER_PORT", "8787")) if server_mode else choose_port()
    host = "0.0.0.0" if server_mode else "127.0.0.1"
    print("=" * 58)
    print("影视硬链接整理工具已启动")
    print(f"访问地址：http://{'NAS-IP' if server_mode else '127.0.0.1'}:{port}")
    print("服务器模式正在持续运行" if server_mode else "关闭所有 MediaLinker 网页后，服务会自动停止")
    print("=" * 58)
    if not server_mode and os.environ.get("MEDIALINKER_NO_BROWSER") != "1":
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
