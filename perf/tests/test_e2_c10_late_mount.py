"""E2: the C10 scroll probe must not scan while the document is still mounting.

Issue #168: on a slow host SuperDoc's ready selector fires on its loading
shell (``.superdoc__document`` exists while the paginated pages do not) and
the document keeps mounting for tens of seconds afterwards. The scroll
discovery that runs a fixed pause after the ready signal then inspects the
loading shell — forty-some elements, no scroller — and the lane refuses
``no scroll container`` even though the document can scroll once mounted.

The fake host ``latemount.html`` does the same thing the real editor does on
the slow box: the ready flag is true immediately, the document's paragraphs
mount progressively for seconds afterwards, and only then does the page have
a scroll container that holds document text.

A1  a document still mounting is **measured**, not refused: the probe waits
    out the mount instead of scanning the loading shell (``latemount.html``).
A2  a document that truly cannot scroll still refuses: the wait does not turn
    ``fits.html`` into a measurement, it only delays the verdict.

The browser tests drive headless Chromium through node and the Playwright the
harness pins. They skip when node or that browser is missing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.fixtures.docx_workload import workload_docx  # noqa: E402
from perf.runner.browser_hosts import StaticHost  # noqa: E402

PROBE = REPO / "perf" / "runner" / "adversarial_c10_scroll.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts" / "b5_scroll"
TIMEOUT_S = 300


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
    corpus = None
    tmp = None

    @classmethod
    def start(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        built = workload_docx("prose-50kw")
        cls.corpus = Path(cls.tmp.name) / "prose-50kw.docx"
        cls.corpus.write_bytes(built["docx"])
        cls.server = StaticHost(
            HOSTS, corpus_route="/corpus.docx", fixture=cls.corpus
        )
        return cls.server.url

    @classmethod
    def stop(cls):
        if cls.server is not None:
            cls.server.stop()
            cls.server = None
        if cls.tmp is not None:
            cls.tmp.cleanup()
            cls.tmp = None


class LateMountScrollTests(unittest.TestCase):
    """The browser side, driven through the probe's own CLI."""

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

    def probe(self, page: str, *, extra=()) -> dict:
        cmd = [
            _node(),
            str(PROBE),
            "--url",
            "%s/%s" % (self.base, page),
            "--corpus",
            str(_FakeHost.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--ready-js",
            "window.__docxReady === true",
            "--pairs",
            "1",
            *[str(value) for value in extra],
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(REPO)
        )
        self.assertEqual(
            proc.returncode,
            0,
            "the scroll probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        return json.loads(proc.stdout)

    # -- A1 --------------------------------------------------------------

    def test_a_document_still_mounting_is_measured_not_refused(self):
        payload = self.probe("latemount.html")
        self.assertEqual(
            payload.get("outcome"),
            "measured",
            "a document still mounting must be measured once it mounts: %r" % (payload,),
        )
        samples = payload.get("samples") or []
        self.assertTrue(samples, "the probe must report the sample it measured")
        for sample in samples:
            self.assertEqual(sample.get("outcome"), "measured", "%r" % (sample,))
            self.assertGreater(
                sample.get("scroll_top_delta") or 0,
                0,
                "the container must have moved: %r" % (sample,),
            )

    # -- A2 --------------------------------------------------------------

    def test_a_document_that_fits_still_refuses_no_scroll_container(self):
        payload = self.probe("fits.html")
        self.assertEqual(
            payload.get("outcome"),
            "not_applicable",
            "a host whose document fits the viewport must still refuse: %r" % (payload,),
        )
        self.assertIn(
            "no scroll container",
            str(payload.get("reason")),
            "the refusal must still say what it did not find: %r" % (payload,),
        )


if __name__ == "__main__":
    unittest.main()
