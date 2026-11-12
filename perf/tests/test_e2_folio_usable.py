"""Folio's usable signal is the painted document blocks, not a contenteditable page.

The painted ``[data-page-number]`` page is not contenteditable. The hidden
ProseMirror mounts on a click, which the usable wait is not allowed to do:
the wait runs before any pointer input. A Folio-like shell paints the page
with no blocks; the wait must refuse there and pass once a block carrying
fixture text is in that page.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HOSTS = REPO / "perf" / "tests" / "fixtures" / "hosts"
PROBE = REPO / "perf" / "tests" / "e2_folio_usable_probe.mjs"


def _node() -> str | None:
    return shutil.which("node")


class FolioUsableSignalTests(unittest.TestCase):
    server = None
    base = ""

    @classmethod
    def setUpClass(cls):
        if _node() is None:
            raise unittest.SkipTest("node is not on PATH")
        from perf.runner.browser_hosts import StaticHost

        cls.server = StaticHost(HOSTS)
        cls.base = cls.server.url

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.stop()
            cls.server = None

    def probe(self, query: str, *, wait_ms: str) -> dict:
        proc = subprocess.run(
            [_node(), str(PROBE), "%s/e2_folio_usable.html%s" % (self.base, query)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO),
            env={**os.environ, "PERF_USABLE_WAIT_MS": wait_ms},
        )
        self.assertEqual(
            proc.returncode,
            0,
            "folio usable probe failed (rc=%s)\nstdout:\n%s\nstderr:\n%s"
            % (proc.returncode, proc.stdout, proc.stderr),
        )
        return json.loads(proc.stdout)

    def test_loading_shell_with_a_painted_page_and_no_blocks_is_refused(self):
        payload = self.probe("?never=1", wait_ms="800")
        self.assertIs(payload["immediate"], False)
        self.assertEqual(payload["refusal"], "usable_signal_not_observed")

    def test_wait_passes_once_painted_blocks_carry_fixture_text(self):
        payload = self.probe("?delay=400", wait_ms="3000")
        self.assertIs(
            payload["immediate"],
            False,
            "the shell, before blocks, must not already be usable: %r" % (payload,),
        )
        self.assertIsNone(
            payload["refusal"],
            "blocks on the painted page must satisfy Folio's usable signal: %r" % (payload,),
        )


if __name__ == "__main__":
    unittest.main()
