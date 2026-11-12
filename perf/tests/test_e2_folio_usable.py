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


# The folio usable expression, pinned so a comment edit cannot change it.
FOLIO_USABLE = (
    "(() => {"
    ' const pages = document.querySelectorAll("[data-page-number]");'
    " for (const page of pages) {"
    "   if (page.getBoundingClientRect().height <= 0) continue;"
    '   for (const block of page.querySelectorAll("[data-block-id]")) {'
    '     if ((block.innerText || "").trim().length > 0 && block.getBoundingClientRect().height > 0) return true;'
    "   }"
    " }"
    " return false;"
    "})()"
)


class FolioUsableCommentTests(unittest.TestCase):
    def test_comment_certifies_the_first_viewport_and_the_expression_is_unchanged(self):
        if _node() is None:
            self.skipTest("node is not on PATH")
        script = (
            "const mod = await import(%s);\n"
            "console.log(JSON.stringify(mod.usableExpression('folio', '[data-page-number]')));\n"
        ) % json.dumps((REPO / "perf" / "runner" / "edit_surface.mjs").as_uri())
        proc = subprocess.run(
            [_node(), "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO),
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout), FOLIO_USABLE)
        source = (REPO / "perf" / "runner" / "edit_surface.mjs").read_text()
        folio = source.index("  folio:")
        hidden = source.index("hidden:", folio)
        usable = source.index("\n    usable:", hidden)
        comment = source[hidden:usable]
        self.assertIn("first viewport", comment)
        self.assertIn("virtualized", comment)
        self.assertIn("mounts on scroll", comment)
        self.assertNotIn("mounted document", comment)


if __name__ == "__main__":
    unittest.main()
