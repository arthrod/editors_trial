"""E2: the caret click must land on a painted body line, not loading chrome.

Issue #168: on slow hosts SuperDoc's ready selector (.superdoc__document)
is visible while it still paints the v2-document-loading-overlay. The
overlay's "Loading document" text satisfies FIND_TEXT_LINE (>= 12 chars,
in viewport), so prepareEditSurface's text-line gate passed immediately and
placeCaret clicked the overlay. No editor took focus, the typed token never
landed, and waitForTokenDelta then polled the model for its full bound —
the probe's whole 600 s budget — producing `browser_probe ... timed out`.

A text line is a line inside the surface's declared paragraph block
(superdoc: .superdoc-line). Overlay text outside the block is not a line.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "perf/tests/fixtures/e2_find_text_line_probe.mjs"
HOSTS = REPO / "perf/tests/fixtures/hosts"
TIMEOUT_S = 120


def _node() -> str | None:
    return shutil.which("node")


def _playwright_dir() -> Path | None:
    for candidate in (
        REPO / "harness" / "ui" / "plate" / "node_modules" / "playwright",
        REPO / "harness" / "ui" / "node_modules" / "playwright",
    ):
        if candidate.is_dir():
            return candidate
    return None


class _FakeHost:
    server = None
    tmp = None

    @classmethod
    def start(cls):
        from perf.runner.browser_hosts import StaticHost

        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = StaticHost(HOSTS)
        return cls.server.url

    @classmethod
    def stop(cls):
        if cls.server is not None:
            cls.server.stop()
            cls.server = None
        if cls.tmp is not None:
            cls.tmp.cleanup()
            cls.tmp = None


class FindTextLineGateTests(unittest.TestCase):
    """prepareEditSurface/placeCaret through the real runner code."""

    base = ""

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        if _playwright_dir() is None:
            raise unittest.SkipTest("harness/ui has no playwright package")
        cls.base = _FakeHost.start()

    @classmethod
    def tearDownClass(cls):
        _FakeHost.stop()

    def probe(self, query: str, *, editor: str = "superdoc", timeout_ms: int = 2500) -> dict:
        cmd = [
            _node(),
            str(PROBE),
            "%s/e2_superdoc_loading.html%s" % (self.base, query),
            editor,
            str(timeout_ms),
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(REPO)
        )
        self.assertEqual(
            proc.returncode,
            0,
            "the find-line probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        return json.loads(proc.stdout)

    def test_loading_overlay_is_not_a_text_line(self):
        """While only the loading overlay is painted, no caret line exists.

        RED today: the overlay's 'Loading document' text satisfies
        FIND_TEXT_LINE, so text_line comes back true and placeCaret returns
        a click point on the overlay — the keypress then lands nowhere and
        the token poll burns the whole 600 s budget.
        """
        payload = self.probe("")
        self.assertFalse(
            payload["prepare"]["text_line"],
            "the loading overlay must not satisfy the text-line gate: %s" % payload,
        )
        self.assertEqual(
            payload["place"].get("error"),
            "edit_surface_no_text_line",
            "placeCaret must refuse the overlay, got %s" % payload["place"],
        )

    def test_painted_line_is_the_caret_target(self):
        """Once .superdoc-line paragraphs paint, the line gate and the caret
        use them — the same behavior the fast-machine run relies on."""
        payload = self.probe("?lines=1")
        self.assertTrue(payload["prepare"]["text_line"], payload)
        point = payload["place"].get("point") or {}
        self.assertTrue(
            str(point.get("line") or "").startswith("The quick brown fox"),
            "expected a painted body line, got %s" % payload["place"],
        )

    def test_overlay_beside_painted_lines_still_picks_the_line(self):
        """If the overlay and painted lines coexist briefly, the caret must
        still land on the body line."""
        payload = self.probe("?lines=1&overlay=1")
        point = payload["place"].get("point") or {}
        self.assertTrue(
            str(point.get("line") or "").startswith("The quick brown fox"),
            "expected a painted body line, got %s" % payload["place"],
        )


if __name__ == "__main__":
    unittest.main()
