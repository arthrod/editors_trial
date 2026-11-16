#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.64.1"]
# ///
"""Open one built demo in headless Chromium and check that it loads its document (#225).

    build/verify_demo.py <slug> <folder>               # folder: out/demos/<slug>, or the demo's dist/
                                                       # with the fixture copied in as document.docx
    build/verify_demo.py <slug> <folder> <shot.png>    # a demo that draws on a canvas: look at the picture

The folder is served the way benchmarks.law serves it, at /demo-apps/<slug>/. The check
fails when any request answers 400 or more or gets no answer at all, when a lazily imported
chunk cannot be fetched, or when the fixture's first heading is not in the page. A demo that
draws its document on a canvas (canvas-editor, Docen, WordCraft) puts no text in the page:
give it a screenshot path as the third argument and judge the document by eye; without one
it waits 90 seconds and fails. Reading the folder is not a check: et-v0.9.5 published five
demos that held only their entry chunks. A fresh dist/ holds no document.docx (`pnpm sync:demos`
writes it into the published folder): copy `out/demo/<editor>.docx` into it first, or the demo
has nothing to load and the check fails for that reason alone.

Needs the Chromium of playwright 1.64.1 once per machine:
    uv run --with playwright==1.64.1 playwright install chromium
"""
import functools
import http.server
import shutil
import sys
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

HEADING = "Chapter 1: Heading with mixed formatting"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # the failed requests are reported from the browser's side
        pass


class Roomy(http.server.ThreadingHTTPServer):
    # The default queue of 5 resets connections when a demo asks for dozens of chunks at once,
    # and a reset would be reported as the demo's missing file.
    request_queue_size = 128


def main() -> int:
    slug, folder = sys.argv[1], Path(sys.argv[2]).resolve()
    shot = sys.argv[3] if len(sys.argv) > 3 else None
    with tempfile.TemporaryDirectory() as root:
        shutil.copytree(folder, Path(root) / "demo-apps" / slug)
        handler = functools.partial(Quiet, directory=root)
        server = Roomy(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = "http://127.0.0.1:%d/demo-apps/%s/" % (server.server_address[1], slug)
        failed, errors, seen = [], [], False
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1400, "height": 950})
            page.on("response", lambda r: failed.append((r.status, r.url)) if r.status >= 400 else None)
            page.on("requestfailed", lambda r: failed.append((0, "%s (%s)" % (r.url, r.failure))))
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append("pageerror: %s" % e))
            page.goto(url, wait_until="load", timeout=90_000)
            for _ in range(45):
                page.wait_for_timeout(2000)
                if HEADING in page.evaluate("document.body.innerText"):
                    seen = True
                    break
            if shot:
                page.screenshot(path=shot)
            browser.close()
        server.shutdown()
    imports = [e for e in errors if "dynamically imported module" in e]
    for status, address in failed:
        print("FAILED %d %s" % (status, address))
    for error in imports:
        print("IMPORT %s" % error[:300])
    text = "in the page" if seen else ("not in the page text: look at %s" % shot if shot else "NOT in the page")
    print("%s: %d failed request(s), %d import error(s), heading %s" % (slug, len(failed), len(imports), text))
    # A canvas demo puts no text in the page: with a screenshot asked for, the eye judges the document.
    return 0 if not failed and not imports and (seen or shot) else 1


if __name__ == "__main__":
    sys.exit(main())
