from __future__ import annotations

import threading
import time
import webbrowser
import socket

import uvicorn


def find_free_port(start: int = 8000) -> int:
    port = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1


def open_browser(port: int) -> None:
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    selected_port = find_free_port()
    threading.Thread(target=open_browser, args=(selected_port,), daemon=True).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=selected_port, reload=True)
