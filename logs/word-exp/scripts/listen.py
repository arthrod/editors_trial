#!/usr/bin/env python3
"""Log every TCP connection and HTTP request line on 127.0.0.1:18009 to ../net.log; answer 404."""
import socket, threading, datetime
from pathlib import Path
LOG = Path(__file__).resolve().parent.parent / "net.log"
def handle(c, a):
    """Log a connection's first request line and user agent, then reply with 404.

    Receive and send errors are ignored; log file errors propagate. The socket is
    closed after the response attempt.
    """
    c.settimeout(5)
    try: data = c.recv(2048)
    except Exception: data = b""
    line = data.split(b"\r\n")[0].decode("latin-1", "replace")
    ua = [l for l in data.decode("latin-1", "replace").split("\r\n") if l.lower().startswith("user-agent")]
    with LOG.open("a") as f:
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}\t{a[0]}:{a[1]}\t{line}\t{ua[0] if ua else ''}\n")
    try: c.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
    except Exception: pass
    c.close()
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", 18009)); s.listen(16)
while True:
    c, a = s.accept(); threading.Thread(target=handle, args=(c, a), daemon=True).start()
