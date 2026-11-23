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
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "perf" / "tests" / "e2_c07_click_scroll.mjs"


@pytest.fixture(scope="module")
def cases():
    """Run the browser repro once; its rows keyed by (mode, scrollBy)."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    if not (REPO / "harness" / "ui" / "node_modules" / "playwright").exists():
        pytest.skip("harness/ui has no playwright package")
    proc = subprocess.run([node, str(SCRIPT)], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert proc.returncode == 0, proc.stderr[-2000:]
    rows = {}
    for line in proc.stdout.splitlines():
        row = json.loads(line)
        rows[(row["mode"], row["scrollBy"])] = row
    return rows


def test_a_click_that_scrolls_nothing_keeps_the_old_verdict(cases):
    """A1, A3: no scroll, no shift; a caret on another line is refused."""
    row = cases[("scroller", 0)]
    assert row["scrolled"] == 0, row
    assert row["onLine"] == {"on_line": True, "after_click_scroll": False}, row
    assert not row["offLine"]["on_line"], row


def test_a_click_that_scrolls_is_judged_on_the_moved_line(cases):
    """A2, A3: an 18 px scroll is applied; a caret on another line is refused."""
    row = cases[("scroller", 18)]
    assert row["scrolled"] == 18, row
    assert row["onLine"] == {"on_line": True, "after_click_scroll": True}, row
    assert not row["offLine"]["on_line"], row


def test_a_caret_left_at_the_old_place_is_refused_after_a_scroll(cases):
    """A4: after a scroll only the moved line counts."""
    row = cases[("scroller", 18)]
    assert row["staleCaret"] == {"on_line": False, "after_click_scroll": False}, row
    # Without a scroll the same caret is on the line, as before.
    assert cases[("scroller", 0)]["staleCaret"]["on_line"]


def test_the_window_scroll_is_counted_once(cases):
    """A5: the document's own scroll is the window's, counted once."""
    row = cases[("window", 18)]
    assert row["scrolled"] == 18, row
    assert row["onLine"] == {"on_line": True, "after_click_scroll": True}, row


def test_a_scroll_between_the_caret_and_its_delta_is_refused_not_judged():
    """The caret read is stable only when the scroll reads around it agree and nothing scrolled."""
    # CodeRabbit on #283 (2026-11-23): the caret and the click's scroll delta
    # were read in two evaluations; a scroll tick between them shifted the
    # line by the wrong amount. The delta is now read on both sides of the
    # caret, and the point is refused when the two reads differ.
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH")
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
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["steady"] == {"stable": True, "scrolled": 18, "state": {"caret": "c"}}
    assert out["absent"]["stable"]
    assert not out["moved"]["stable"]
    assert not out["lost"]["stable"]
    # CodeRabbit on #287: equal deltas, but scroll events in between.
    assert not out["bounced"]["stable"]
    src = (REPO / "perf/runner/criteria_input.mjs").read_text()
    assert "click_scroll_moved_during_caret_read" in src
