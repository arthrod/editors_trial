"""E2 C07: the caret is judged against where the clicked line ends up after
the click's own scroll (owner's decision, 2026-11-22).

A1  A click that scrolls nothing gets the old verdict: the caret on the line
    box read before the click is on the line; no shift is applied.
A2  A click that scrolls its scroller by 18 px (BetterOffice's cut last line):
    the caret on the moved line is on the clicked line, and the shift is 18.
A3  A caret on another line is refused in both cases.
A4  No published editor's verdict can move: the published campaign
    (ds-final, 3,144 C07 attempts) has no caret_not_on_clicked_line refusal,
    and the shift is consulted only after the old comparison failed
    (source order pinned here).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "perf" / "tests" / "e2_c07_click_scroll.mjs"


class ClickScrollTests(unittest.TestCase):
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
            cls.cases[row["scrollBy"]] = row

    def test_a_click_that_scrolls_nothing_keeps_the_old_verdict(self):
        row = self.cases[0]
        self.assertEqual(row["scrolled"], 0, row)
        self.assertEqual(row["onLine"], {"on_line": True, "after_click_scroll": False}, row)
        self.assertFalse(row["offLine"]["on_line"], row)

    def test_a_click_that_scrolls_is_judged_on_the_moved_line(self):
        row = self.cases[18]
        self.assertEqual(row["scrolled"], 18, row)
        self.assertEqual(row["onLine"], {"on_line": True, "after_click_scroll": True}, row)
        self.assertFalse(row["offLine"]["on_line"], row)

    def test_the_shift_is_consulted_only_after_the_old_comparison_failed(self):
        src = (REPO / "perf/runner/criteria_input.mjs").read_text(encoding="utf-8")
        body = src[src.index("export function caretOnClickedLine("):]
        body = body[: body.index("\n}\n")]
        self.assertLess(body.index("caretOverlapsLine(caret, line)"), body.index("Number(scrolled)"))


if __name__ == "__main__":
    unittest.main()
