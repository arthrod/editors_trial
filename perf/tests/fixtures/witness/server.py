"""Tiny stdlib static server for the witness fake hosts.

The witness module talks to a page; the fake hosts are plain files, so they
need a server that serves them with the right MIME type and nothing else.
`http.server` is enough: the pages are static, the port is ephemeral, and the
server is started and stopped inside one test.

Usage (manual):

    python3 perf/tests/fixtures/witness/server.py 8765
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler without the request log on stderr."""

    def log_message(self, fmt, *args):  # noqa: D102 - silence the default log
        pass


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(directory=None, port=0):
    """Start a static server for `directory`.

    Returns `(httpd, thread, base_url)`. The caller closes `httpd` when done.
    """
    root = Path(directory) if directory is not None else HERE
    handler = functools.partial(_QuietHandler, directory=str(root))
    httpd = _Server(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, bound_port = httpd.server_address[:2]
    return httpd, thread, f"http://{host}:{bound_port}"


def main(argv=None):
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    port = int(args[0]) if args else 8765
    httpd, _thread, base = serve(port=port)
    print(base, flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
