"""E2 C07: the caret is judged against where the clicked line ends up after
the click's own scroll (owner's decision, 2026-11-22).

A1  A click that scrolls nothing gets the old verdict: the caret on the line
    box read before the click is on the line; no shift is applied.
A2  A click that scrolls its scroller by 18 px (BetterOffice's cut last line):
    the caret on the moved line is on the clicked line, and the shift is 18.
A3  A caret on another line is refused in both cases.
A4  A click that scrolled is judged only on the moved line: a caret left at
    the line's old place is refused (Codex review, 2026-11-22).
A5  When the document itself scrolls, the window's scroll is counted once,
    not also as the document's scroller (Codex review, 2026-11-22).
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
            cls.cases[(row["mode"], row["scrollBy"])] = row

    def test_a_click_that_scrolls_nothing_keeps_the_old_verdict(self):
        row = self.cases[("scroller", 0)]
        self.assertEqual(row["scrolled"], 0, row)
        self.assertEqual(row["onLine"], {"on_line": True, "after_click_scroll": False}, row)
        self.assertFalse(row["offLine"]["on_line"], row)

    def test_a_click_that_scrolls_is_judged_on_the_moved_line(self):
        row = self.cases[("scroller", 18)]
        self.assertEqual(row["scrolled"], 18, row)
        self.assertEqual(row["onLine"], {"on_line": True, "after_click_scroll": True}, row)
        self.assertFalse(row["offLine"]["on_line"], row)

    def test_a_caret_left_at_the_old_place_is_refused_after_a_scroll(self):
        row = self.cases[("scroller", 18)]
        self.assertEqual(row["staleCaret"], {"on_line": False, "after_click_scroll": False}, row)
        # Without a scroll the same caret is on the line, as before.
        self.assertTrue(self.cases[("scroller", 0)]["staleCaret"]["on_line"])

    def test_the_window_scroll_is_counted_once(self):
        row = self.cases[("window", 18)]
        self.assertEqual(row["scrolled"], 18, row)
        self.assertEqual(row["onLine"], {"on_line": True, "after_click_scroll": True}, row)

    def test_a_scroll_between_the_caret_and_its_delta_is_refused_not_judged(self):
        # CodeRabbit on #283 (2026-11-23): the caret and the click's scroll delta
        # were read in two evaluations; a scroll tick between them shifted the
        # line by the wrong amount. The delta is now read on both sides of the
        # caret, and the point is refused when the two reads differ.
        script = """
        import { readStateWithClickScroll } from './perf/runner/criteria_input.mjs';
        // Each read is {delta, events} (null: no recorder on the page).
        const fake = (deltas, events = [0, 0]) => {
          let i = 0;
          return { evaluate: async () => { const k = i++; return deltas[k] === null ? null : { delta: deltas[k], events: events[k] }; } };
        };
        const out = {};
        for (const [name, deltas] of Object.entries({
          steady: [18, 18], absent: [null, null], moved: [0, 18], lost: [18, null], bounced: [18, 18],
        })) {
          const events = name === 'bounced' ? [0, 2] : [0, 0];
          const r = await readStateWithClickScroll(fake(deltas, events), async () => ({ caret: 'c' }));
          out[name] = { stable: r.stable, scrolled: r.scrolled, state: r.state };
        }
        process.stdout.write(JSON.stringify(out));
        """
        proc = subprocess.run(["node", "--input-type=module", "-e", script], cwd=str(REPO),
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["steady"], {"stable": True, "scrolled": 18, "state": {"caret": "c"}})
        self.assertTrue(out["absent"]["stable"])
        self.assertFalse(out["moved"]["stable"])
        self.assertFalse(out["lost"]["stable"])
        # CodeRabbit on #287: equal deltas, but scroll events in between.
        self.assertFalse(out["bounced"]["stable"])
        src = (REPO / "perf/runner/criteria_input.mjs").read_text()
        self.assertIn("click_scroll_moved_during_caret_read", src)


if __name__ == "__main__":
    unittest.main()
