"""E2: the input suite must not resolve click points while the document mounts.

Issue #168: on a slow host SuperDoc's ready selector fires on its loading
shell — ``.superdoc__document`` exists while the document pages do not — and
the mount continues for tens of seconds afterwards. The input suite resolves
its ink click points a fixed pause after that signal, so the ink scan
photographs the loading overlay's progress text and the click lands on
loading chrome: the typed character changes nothing and C07/C08/C09 refuse
``correctness: input_did_not_change_document`` even though the editor takes
input the moment its first page paints.

The fake host ``e2_superdoc_latemount.html`` does what the real editor does
on the slow box: the ready selector is live immediately, a loading overlay
paints several lines of progress text, and four seconds later the document's
text lines mount together with the ``[role='textbox']`` element the surface
declares as its usable signal.

A1  a document still mounting is **measured**: the suite waits for the
    surface's declared usable signal before resolving its click points.
A2  a host that never becomes usable still runs and refuses for its own
    reason: the wait is bounded and non-fatal, never a hang.

The browser tests drive headless Chromium through node and the Playwright the
harness pins. They skip when node or that browser is missing.
"""

from __future__ import annotations

import json
import os
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

PROBE = REPO / "perf" / "runner" / "warm_cold_browser.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
UI = REPO / "harness" / "ui"
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


class LateMountInputTests(unittest.TestCase):
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

    def probe(self, page: str, *, extra=(), env=None) -> dict:
        cmd = [
            _node(),
            str(PROBE),
            "--driver",
            "playwright",
            "--editor",
            "superdoc",
            "--criteria",
            "C07",
            "--url",
            "%s/%s" % (self.base, page),
            "--corpus",
            str(_FakeHost.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--ready-selector",
            "#editor .superdoc__document",
            "--edit-selector",
            "#editor .superdoc__document",
            *[str(value) for value in extra],
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            cwd=str(UI),
            env={**os.environ, **(env or {})},
        )
        self.assertEqual(
            proc.returncode,
            0,
            "the input probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        return json.loads(proc.stdout)

    # -- A1 --------------------------------------------------------------

    def test_a_document_still_mounting_is_measured_not_refused(self):
        payload = self.probe("e2_superdoc_latemount.html")
        c07 = (payload.get("criteria") or {}).get("C07") or {}
        self.assertEqual(
            c07.get("outcome"),
            "measured",
            "a document still mounting must be measured once usable: %r" % (payload,),
        )

    # -- A2 --------------------------------------------------------------

    def test_a_never_usable_host_still_finishes_with_its_own_refusal(self):
        payload = self.probe(
            "e2_superdoc_latemount.html?never=1",
            env={"PERF_USABLE_WAIT_MS": "1500"},
        )
        c07 = (payload.get("criteria") or {}).get("C07") or {}
        self.assertNotEqual(
            c07.get("outcome"),
            "measured",
            "a host that never mounts the document must not be measured: %r" % (payload,),
        )
        self.assertEqual(
            c07.get("failure_reason"),
            "usable_signal_not_observed",
            "the bound must refuse usable_signal_not_observed, not fall "
            "through: %r" % (c07,),
        )


if __name__ == "__main__":
    unittest.main()
