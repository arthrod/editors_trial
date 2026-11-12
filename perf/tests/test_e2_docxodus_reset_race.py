"""E2 + policy: the C09 fixture-reset reload must wait out the loading shell,
and the input lane's probe cap must outlive the load-timeout policy.

Issue #173. Two holes, one measurement:

1. ``measureUndo``'s ``finally`` reloaded the page and clicked ``#modeEditor``
   at once. The button is static HTML, so the click landed while
   ``window.__docxodus.rendered`` was still false; on the real host that mount
   never finishes. ``openEditorMode`` then waited ``loadTimeoutMs()`` — the
   same 300 s ``benchmark_input`` gave the probe — so the lane killed the
   probe and C04/C07, already computed inside it, were lost. The C07 reload
   path never raced because its ``reloadPage`` re-waits the ready signal; the
   reset path now uses that same helper.

2. ``benchmark_input`` never exported ``PERF_LOAD_TIMEOUT_MS`` and capped the
   probe at a fixed 300 s, so the probe's own 300 s waits could never expire
   first and name their failure. The lane now follows the same policy every
   other lane does (``load_timeouts.py``, #155 item 6): export the workload's
   load timeout and cap the subprocess at ``load_timeout_ms/1000 + 300``.

The fake host ``e2_docxodus_reset_race.html`` does what the real host does:
``#modeEditor`` is in the static HTML, ``rendered`` flips ~1 s after load,
and the contenteditable block editor mounts only when the click arrives
after ``rendered``. Undo is disabled so C09 always reaches the reset path.

The browser test drives headless Chromium through node and the Playwright the
harness pins. It skips when node or that browser is missing.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from perf.fixtures.docx_workload import workload_docx  # noqa: E402
from perf.runner.browser_hosts import StaticHost  # noqa: E402

PROBE = REPO / "perf" / "runner" / "warm_cold_browser.mjs"
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
UI = REPO / "harness" / "ui"
# Perf budget for the whole probe on this fixture. At 4488f9b6 the reset
# click lands before `rendered` and openEditorMode burns the whole
# PERF_LOAD_TIMEOUT_MS=20000 wait; the pre-reset work alone is about 15 s, so
# a lost race reads as ~40 s. A wait-for-ready reset returns well under 30 s.
PROBE_WALL_BOUND_S = 30
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


class ResetRaceInputTests(unittest.TestCase):
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
            "C04,C07,C09,C08",
            "--url",
            "%s/%s" % (self.base, page),
            "--corpus",
            str(_FakeHost.corpus),
            "--corpus-route",
            "/corpus.docx",
            "--ready-js",
            "window.__docxodus && window.__docxodus.rendered",
            "--wait-after-ready",
            "200",
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

    def test_c09_reset_reopens_editor_mode_after_ready(self):
        """A1: the reset click must wait for `rendered`, not race the mount.

        At 4488f9b6 the fixture-reset ``finally`` clicks ``#modeEditor``
        straight out of ``page.reload()`` — before this host's ``rendered``
        flag flips — and the mount never comes, so ``openEditorMode`` sits in
        its load-timeout wait and the reset ends ``restored: false`` about
        PERF_LOAD_TIMEOUT_MS later than it should.
        """
        t0 = time.monotonic()
        payload = self.probe(
            "e2_docxodus_reset_race.html",
            env={"PERF_LOAD_TIMEOUT_MS": "20000"},
        )
        wall = time.monotonic() - t0
        criteria = payload.get("criteria") or {}
        c04 = criteria.get("C04") or {}
        self.assertEqual(
            c04.get("outcome"),
            "measured",
            "C04 must stay in the payload and measured: %r" % (payload,),
        )
        c09 = criteria.get("C09") or {}
        reset = c09.get("fixture_reset") or {}
        self.assertIs(
            reset.get("attempted"),
            True,
            "the undo-blocking host must drive C09 into the reset path: %r" % (c09,),
        )
        self.assertIs(
            reset.get("restored"),
            True,
            "a reset click after the ready wait remounts and restores the "
            "fixture text; a click that raced `rendered` leaves it unrestored: "
            "%r" % (reset,),
        )
        self.assertLess(
            wall,
            PROBE_WALL_BOUND_S,
            "the probe must return well under %ss — a %ss dead wait inside "
            "openEditorMode is the bug this test catches (wall %.1fs)"
            % (PROBE_WALL_BOUND_S, "load-timeout", wall),
        )


class ProbeLoadTimeoutPolicy(unittest.TestCase):
    """benchmark_input follows the owner load-timeout policy (#155 item 6)."""

    def test_probe_env_exports_the_workload_load_timeout(self):
        from perf.runner.benchmark_input import _fixture, _probe_env
        from perf.runner.load_timeouts import load_timeout_ms

        fixture, _sha, _size, _row = _fixture("plate", "micro-paragraphs")
        for workload_id in ("micro-paragraphs", "prose-250kw"):
            with self.subTest(workload_id=workload_id):
                env = _probe_env("docxodus", {}, fixture, workload_id=workload_id)
                self.assertEqual(
                    env.get("PERF_LOAD_TIMEOUT_MS"),
                    str(load_timeout_ms(workload_id)),
                    "the probe env must carry the workload's load timeout so "
                    "the probe's inner waits follow the same policy the cap does",
                )

    def test_probe_subprocess_cap_outlives_the_load_timeout(self):
        """The lane kill must come after the probe's own waits can expire.

        warm_cold caps at ``load_timeout_ms(workload)/1000 + 300``; the input
        lane used a fixed 300 s — the same number as the default load wait —
        so a probe whose inner wait was still open got SIGKILLed and its
        computed criteria never reached the payload.
        """
        from unittest.mock import patch

        from perf.fixtures.profiles import size_ladder
        from perf.runner import benchmark_input as bi
        from perf.runner.load_timeouts import load_timeout_ms

        fixture, _sha, _size, _row = bi._fixture("plate", "micro-paragraphs")

        for workload_id in ("micro-paragraphs", "prose-250kw"):
            with self.subTest(workload_id=workload_id):
                row = next(w for w in size_ladder() if w["workload_id"] == workload_id)
                captured = {}

                def fake_run(cmd, **kwargs):
                    captured.update(kwargs)
                    return types.SimpleNamespace(returncode=1, stdout="", stderr="stopped at the seam")

                def fake_fixture(editor_id, wid="micro-paragraphs"):
                    return fixture, "a" * 64, 1234, row

                with (
                    patch.object(bi, "_fixture", fake_fixture),
                    patch.object(bi, "_start_server", lambda *a, **k: "server-token"),
                    patch.object(bi, "_stop_server", lambda *a, **k: None),
                    patch.object(bi, "record_process", lambda *a, **k: None),
                    patch.object(bi, "_write_criteria_refusals", lambda *a, **k: None),
                    patch("perf.runner.browser_hosts.select_fixture", lambda *a, **k: None),
                    patch.object(bi.subprocess, "run", fake_run),
                ):
                    attempt_dir = Path(tempfile.mkdtemp())
                    bi.run_editor("docxodus", attempt_dir, workload_id)

                self.assertEqual(
                    captured.get("timeout"),
                    load_timeout_ms(workload_id) / 1000 + 300,
                    "the subprocess cap must be load_timeout_ms/1000 + 300 "
                    "(warm_cold's formula), got %r" % (captured.get("timeout"),),
                )
                self.assertEqual(
                    (captured.get("env") or {}).get("PERF_LOAD_TIMEOUT_MS"),
                    str(load_timeout_ms(workload_id)),
                    "the probe env must carry the workload's load timeout",
                )


if __name__ == "__main__":
    unittest.main()
