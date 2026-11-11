"""Static server for B4 input-criteria fake hosts."""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(directory=None, port=0):
    root = Path(directory) if directory is not None else HERE
    handler = functools.partial(_QuietHandler, directory=str(root))
    httpd = _Server(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, bound_port = httpd.server_address[:2]
    return httpd, thread, f"http://{host}:{bound_port}/"
