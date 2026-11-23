"""E2 C10: the content must move at the scroll, not on a later frame.

CodeRabbit on #287 (2026-11-23): once the content walk moved after the
witness (CodeAnt on #283), the gate accepted any movement seen by that later
read, so a page that moves its content a few frames after the scroll could be
timed on a frame that precedes the movement. The lane now also reads, at the
scroll, the position of the one element the probe chose before it (a single
rect read, no walk).

``late-move.html``: the probed content's containing block is outside the
scroller and the page moves it two frames after the scroll event, while a
striped spacer in the scroller's flow makes the first frame change.
"""

from __future__ import annotations

import pytest

from perf.tests import test_e2_c10_late_mount as late


class _Probe(late.LateMountScrollTests):
    """Borrow the probe CLI driver; never collected as a test class."""

    __test__ = False

    def runTest(self):  # pragma: no cover - unittest needs one to instantiate
        pass


@pytest.fixture(scope="module")
def probe():
    """Serve the fake hosts once and hand back the probe driver."""
    if late._node() is None:
        pytest.skip("node is not on PATH")
    if late._playwright_dir() is None:
        pytest.skip("harness/ui has no playwright package")
    driver = _Probe()
    driver.base = late._FakeHost.start()
    yield driver
    late._FakeHost.stop()


def test_content_moved_only_on_a_later_frame_is_refused(probe):
    """The scroll moved the scroller, not the content: no figure."""
    payload = probe.probe("late-move.html")
    assert payload.get("outcome") != "measured", payload
    assert "at the scroll" in str(payload.get("reason")), payload.get("reason")


def test_content_that_moves_with_the_scroll_is_measured_and_says_so(probe):
    """The plain host: the content moved at the scroll by the scroll's own delta."""
    payload = probe.probe("prose.html")
    assert payload.get("outcome") == "measured", payload.get("reason")
    sample = (payload.get("samples") or [{}])[0]
    content = sample.get("content") or {}
    assert content.get("moved_at_scroll_px") == pytest.approx(sample.get("scroll_top_delta"), abs=0.6), sample
