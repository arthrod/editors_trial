#!/usr/bin/env python3
"""Validate the wordcraft BROWSER_TARGETS entry through the runner's own server startup.

Does not run the browser probe (that is a measurement): it exercises cwd/command/url exactly as
perf/runner/benchmark_warm_cold.py::_start_server does, then stops the server.

    /opt/homebrew/bin/python3.13 harness/ui/wordcraft-host/check_target.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from perf.adapters.capabilities import default_lane, pin_label  # noqa: E402
from perf.runner.benchmark_warm_cold import UI, _start_server, _stop_server  # noqa: E402

TARGET = {
    "cwd": UI / "wordcraft-host",
    "command": ["node", "server.mjs"],
    "url": "http://127.0.0.1:5219/",
    "corpus_route": "/corpus.docx",
    "ready_selector": '#wc-ready[data-state="rendered"]',
    "ready_js": "window.__WORDCRAFT_READY__ === true",
    "edit_selector": "#wordcraft_canvas",
    "driver": "playwright",
    "criteria": {
        "C03": ("first_usable", "browser_visible"),
        "C05": ("presented_frame", "browser_visible"),
        "C06": ("input_to_next_paint", "browser_visible"),
    },
}

# Keys the runner reads (perf/runner/benchmark_warm_cold.py::_start_server/_run_browser_probe and
# perf/runner/adversarial_c10_scroll.py::_scroll_samples).
REQUIRED = ("cwd", "command", "url", "corpus_route", "ready_selector", "edit_selector", "driver",
            "criteria")
OPTIONAL = ("ready_js", "ready_text", "wait_after_ready", "pre_edit_click", "skip_edit",
            "sample_route", "env")
print("keys ok:", all(k in TARGET for k in REQUIRED), "| unknown:",
      sorted(set(TARGET) - set(REQUIRED) - set(OPTIONAL)))
print("pin:", pin_label("wordcraft"), "| c10 lane:", default_lane("wordcraft"))

proc = _start_server("wordcraft", TARGET)
try:
    with urllib.request.urlopen(TARGET["url"], timeout=5) as resp:
        body = resp.read()
    print("server up:", proc.pid, "status", resp.status, "html bytes", len(body))
    print("host.js injected:", b'<script src="/_host/host.js">' in body)
    with urllib.request.urlopen(TARGET["url"] + "corpus.docx", timeout=5) as resp:
        print("corpus route:", resp.status, resp.headers["content-type"])
finally:
    _stop_server(proc)
print("stopped; listening:", end=" ")
try:
    urllib.request.urlopen(TARGET["url"], timeout=2)
    print("STILL UP (bad)")
except Exception:
    print("no")
