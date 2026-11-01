#!/usr/bin/env python3
"""Report C's UI figures show what the recipe asked for: a missed readiness wait or
scroll target fails the capture instead of shipping page 1 labelled as page 3."""
import functools
import http.server
import json
import subprocess
import threading
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "harness" / "ui"
BAD = ("NOT FOUND", "[wait-for-error]", "[scroll-text-error]")


class ShotFailsOnAMiss(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = tempfile.TemporaryDirectory()
        (Path(cls.site.name) / "index.html").write_text("<p>page one</p>")
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=cls.site.name)
        h.log_message = lambda *a: None
        cls.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.url = "http://127.0.0.1:%d/" % cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.site.cleanup()

    def shot(self, *extra):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run(["node", "shot.mjs", "--name", "t", "--outdir", d,
                                "--url", self.url, "--wait", "100", *extra],
                               cwd=UI, capture_output=True, text=True, timeout=120)
            return r.returncode, r.stdout + r.stderr

    def test_a_scroll_target_not_on_the_page_is_a_failed_capture(self):
        code, out = self.shot("--scroll-text", "A sentence with a comment")
        self.assertEqual(code, 4, out)
        self.assertIn("MISS t", out)

    def test_a_found_target_is_ok(self):
        code, out = self.shot("--scroll-text", "page one")
        self.assertEqual(code, 0, out)


class PublishedCaptures(unittest.TestCase):
    def test_every_published_capture_reached_its_target(self):
        for meta in sorted((ROOT / "out" / "ui").glob("*.json")):
            log = json.loads(meta.read_text()).get("consoleLog", [])
            bad = [line for line in log if any(b in line for b in BAD)]
            self.assertEqual(bad, [], meta.name)


if __name__ == "__main__":
    unittest.main()
