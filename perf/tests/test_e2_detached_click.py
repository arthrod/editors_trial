"""E2: the input lane's detached-target rule is react-docx's alone.

A1  On a page without react-docx's global, a click whose target the editor
    replaced during pointerdown is judged as before this branch: not inside,
    and no event path is recorded.
A2  On react-docx's page, the same click is judged by its ancestors at the
    event: inside, flagged ``target_detached``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "perf" / "tests" / "e2_detached_click.mjs"


class DetachedClickGateTests(unittest.TestCase):
    cases: dict = {}

    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if node is None:
            raise unittest.SkipTest("node is not on PATH")
        if not (REPO / "harness" / "ui" / "node_modules" / "playwright").exists():
            raise unittest.SkipTest("harness/ui has no playwright package")
        proc = subprocess.run([node, str(SCRIPT)], capture_output=True, text=True, timeout=120, cwd=str(REPO))
        if proc.returncode != 0:
            raise AssertionError(proc.stderr[-2000:])
        for line in proc.stdout.splitlines():
            row = json.loads(line)
            cls.cases[row["reactDocx"]] = row

    def test_other_pages_keep_the_old_verdict(self):
        row = self.cases[False]
        self.assertIs(row["verdict"]["inside"], False, row)
        self.assertNotIn("target_detached", row["verdict"], row)
        self.assertFalse(row["recordedPath"], row)

    def test_react_docx_page_judges_by_the_event_path(self):
        row = self.cases[True]
        self.assertIs(row["verdict"]["inside"], True, row)
        self.assertTrue(row["verdict"].get("target_detached"), row)


if __name__ == "__main__":
    unittest.main()
