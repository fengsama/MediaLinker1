import os
import socket
import threading
import time
import webbrowser

import uvicorn

from app.main import app


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
    port = choose_port()
    print("=" * 58)
    print("影视硬链接整理工具已启动")
    print(f"访问地址：http://127.0.0.1:{port}")
    print("关闭此窗口即可停止服务")
    print("=" * 58)
    if os.environ.get("MEDIALINKER_NO_BROWSER") != "1":
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
