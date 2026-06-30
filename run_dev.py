#!/usr/bin/env python3
"""
Development server with automatic browser reload.

Watches Python, HTML, CSS, and JavaScript files — saves a file and the
browser refreshes without a manual reload.
"""

import os
import socket

from dotenv import load_dotenv
from livereload import Server

load_dotenv()

from app import BASE_DIR, DB_PATH, app

WATCH_PATHS = (
    os.path.join(BASE_DIR, "templates"),
    os.path.join(BASE_DIR, "static"),
    os.path.join(BASE_DIR, "app.py"),
    os.path.join(BASE_DIR, "helpers.py"),
    os.path.join(BASE_DIR, "database.py"),
)


def find_free_port(preferred: int, attempts: int = 10) -> int:
    """Return preferred port if available, otherwise the next free port."""
    for offset in range(attempts):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found near {preferred}.")


def main() -> None:
    """Start Flask with LiveReload enabled."""
    if not os.path.exists(DB_PATH):
        print("Database not found. Run: python3 init_db.py")

    os.environ["FLASK_DEBUG"] = "1"
    app.config["DEBUG"] = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    preferred = int(os.environ.get("PORT", 5000))
    port = find_free_port(preferred)
    server = Server(app.wsgi_app)

    for path in WATCH_PATHS:
        server.watch(path)

    print(f"Live reload enabled — http://127.0.0.1:{port}")
    if port != preferred:
        print(f"(Port {preferred} was busy; using {port} instead.)")
    print("Save any template, CSS, JS, or Python file and the browser will refresh.")
    server.serve(host="127.0.0.1", port=port, debug=True, restart_delay=0.4)


if __name__ == "__main__":
    main()
