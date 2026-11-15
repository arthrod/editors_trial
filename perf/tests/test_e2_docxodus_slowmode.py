"""E2: the mode-open wait must scale with the document, not stop at 20 s.

Issue #168: the input lane opens docxodus's block editor by clicking
``#modeEditor`` and waiting for ``#editorHost [contenteditable]`` — with a
fixed 20 s bound. The real host mounts that editor in ~44 s on a 250k-word
document (measured locally, slower still on the Space box), so the lane
refused ``editor_mode_did_not_open`` on every edit criterion even though the
mode always opens. The ready/navigation policy already grants minutes for
the same kind of wait; the mode-open wait was the one bound that ignored it.

The fake host ``e2_docxodus_slowmode.html`` does what the real host does:
the ready flag is true at once, and the contenteditable block editor mounts
21 s after the ``#modeEditor`` click — past the old bound, far inside the
load-timeout policy.

A1  a mode that opens inside the load policy is **measured**, not refused.
A2  a mode that never opens still refuses ``editor_mode_did_not_open`` — the
    bound is longer, not gone.

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


class SlowModeInputTests(unittest.TestCase):
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
            "docxodus",
            "--criteria",
            "C07",
            "--url",
            "%s/%s" % (self.base, page),
            "--corpus",
            str(_FakeHost.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--ready-js",
            "window.__docxodus && window.__docxodus.rendered",
            "--edit-selector",
            "#pages",
            *[str(value) for value in extra],
        ]
        import os

        run_env = dict(os.environ)
        run_env.update(env or {})
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_S, cwd=str(UI),
            env=run_env,
        )
        self.assertEqual(
            proc.returncode,
            0,
            "the input probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        return json.loads(proc.stdout)

    # -- A1 --------------------------------------------------------------

    def test_a_mode_opening_inside_the_load_policy_is_measured(self):
        payload = self.probe("e2_docxodus_slowmode.html")
        c07 = (payload.get("criteria") or {}).get("C07") or {}
        self.assertEqual(
            c07.get("outcome"),
            "measured",
            "a mode that opens inside the load policy must measure: %r" % (payload,),
        )

    # -- A2 --------------------------------------------------------------

    def test_a_mode_that_never_opens_still_refuses(self):
        payload = self.probe(
            "e2_docxodus_slowmode.html?delay=240000",
            env={"PERF_LOAD_TIMEOUT_MS": "30000"},
        )
        c07 = (payload.get("criteria") or {}).get("C07") or {}
        self.assertNotEqual(
            c07.get("outcome"),
            "measured",
            "a mode that never opens must not be measured: %r" % (payload,),
        )
        self.assertIn(
            "editor_mode_did_not_open",
            str(c07.get("failure_reason") or "") + str(payload.get("input_surface")),
            "the refusal must still name the mode that did not open: %r" % (payload,),
        )


if __name__ == "__main__":
    unittest.main()
