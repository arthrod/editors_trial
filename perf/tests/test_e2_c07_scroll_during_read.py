"""E2 C07: the caret read is stable only if nothing scrolled during it.

CodeRabbit on #287 (2026-11-23): ``readStateWithClickScroll`` compared the
click's scroll delta before and after the caret read. A scroll away and back
during the read left both ends equal, so the read was called stable although
the caret came from another viewport. The page-side tracker now also counts
scroll events on the clicked line's scrollers and the window, and the second
read waits one frame so a pending scroll event is counted.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "perf" / "tests" / "e2_c07_scroll_during_read.mjs"


@pytest.fixture(scope="module")
def cases():
    """Run the browser repro once: three reads, still, away and back, away."""
    if shutil.which("node") is None:
        pytest.skip("node is not on PATH")
    if not (REPO / "harness" / "ui" / "node_modules" / "playwright").exists():
        pytest.skip("harness/ui has no playwright package")
    proc = subprocess.run(["node", str(SCRIPT)], cwd=str(REPO), capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_a_read_with_no_scroll_is_stable(cases):
    """The control: nothing moved, the read stands."""
    assert cases["still"] == {"stable": True, "scrolled": 0}


def test_a_scroll_away_and_back_during_the_read_is_unstable(cases):
    """Both ends equal, but the page scrolled in between: refused."""
    assert cases["away_and_back"]["stable"] is False, cases["away_and_back"]


def test_a_scroll_away_during_the_read_is_unstable(cases):
    """The case the delta comparison already caught still is."""
    assert cases["away"]["stable"] is False, cases["away"]
