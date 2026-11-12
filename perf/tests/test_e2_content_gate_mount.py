"""E2: the document-content gate must wait out a still-mounting document.

Issue #168: ``verifyCanvasOpening`` runs the moment the ready signal fires
and reads the mounted text ONCE. On a host whose ready selector lives on
the loading shell — SuperDoc's ``.superdoc__document`` hosts the
v2-document-loading-overlay — a large document is still mounting and the
read returns ``""``, so the pair refuses ``document_content_absent`` on
every arm even though the document mounts seconds later (local 250kw run).

The same mount race the caret and ink-scan fixes cover; the gate just sits
one layer earlier: wait for the surface's usable signal (or a quiet DOM)
before the one-shot read.

The fake host ``e2_superdoc_latemount.html`` paints overlay text under the
ready selector at once and mounts ``.superdoc-page`` lines ~4 s later.

A1  a document still mounting is **verified**, not refused absent.
A2  a document that never mounts still refuses ``document_content_absent``
    — the wait is bounded and falls through to the gate's own verdict.

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

PROBE = REPO / "perf" / "runner" / "warm_cold_browser.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
UI = REPO / "harness" / "ui"
TIMEOUT_S = 600


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


class ContentGateMountTests(unittest.TestCase):
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

    def probe(self, page: str) -> dict:
        cmd = [
            _node(),
            str(PROBE),
            "--driver",
            "playwright",
            "--editor",
            "superdoc",
            "--pairs",
            "1",
            "--skip-edit",
            "true",
            "--url",
            "%s/%s" % (self.base, page),
            "--corpus",
            str(_FakeHost.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--ready-selector",
            ".superdoc__document",
            "--edit-selector",
            "#editor",
            "--expected-opening-text",
            "fixture line one alpha bravo charlie delta echo foxtrot golf",
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(UI)
        )
        self.assertEqual(
            proc.returncode,
            0,
            "the warm/cold probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        return json.loads(proc.stdout)

    # -- A1 --------------------------------------------------------------

    def test_a_still_mounting_document_verifies_not_absent(self):
        payload = self.probe("e2_superdoc_latemount.html")
        for arm in ("cold", "warm"):
            check = ((payload.get("pairs") or [{}])[0].get(arm) or {}).get(
                "content_check"
            ) or {}
            self.assertTrue(
                check.get("content_verified"),
                "%s arm: a document still mounting must verify, not refuse "
                "document_content_absent: %r" % (arm, check),
            )

    # -- A2 --------------------------------------------------------------

    def test_a_never_mounting_document_still_refuses_absent(self):
        payload = self.probe("e2_superdoc_latemount.html?never=1")
        for arm in ("cold", "warm"):
            check = ((payload.get("pairs") or [{}])[0].get(arm) or {}).get(
                "content_check"
            ) or {}
            self.assertEqual(
                check.get("surface_reason"),
                "document_content_absent",
                "%s arm: a document that never mounts still refuses "
                "document_content_absent: %r" % (arm, check),
            )


if __name__ == "__main__":
    unittest.main()
