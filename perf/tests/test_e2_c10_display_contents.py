"""E2: the C10 content probe looks through a ``display: contents`` wrapper.

react-docx mounts its whole document in one ``display: contents`` div inside
the scroller. Such an element has no box (its rect is 0x0 at the origin
whatever the scroll), so a probe that picks it reports "the scroll did not
move the content" although the page scrolled. The probe now looks through
such wrappers, but only for a target that asks for it (``c10_through_contents``,
react-docx only: outside review, 2026-11-22, found the unflagged fallback could
add work inside a published editor's timed window), and only when the
scroller's own children give no box.

A1  ``contents.html`` with ``--through-contents`` measures.
A2  ``contents.html`` without the flag refuses, as before this change.
A3  ``prose.html`` (the plain host) measures with no ``through_display_contents``.
A4  Only react-docx's browser target sets the flag; the lane passes it.
A5  The content walk runs after the witness has its frame, not inside the
    timed window (CodeAnt on #283, 2026-11-23: the walk through every
    paragraph made up ~40% of react-docx's 250kw sample). On
    ``contents-slow.html`` every style read costs 250 ms once the page has
    scrolled, so a walk inside the window makes the sample at least 250 ms.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from perf.tests import test_e2_c10_late_mount as late

_FakeHost, _node, _playwright_dir = late._FakeHost, late._node, late._playwright_dir


class _Probe(late.LateMountScrollTests):
    """Borrow the probe CLI driver; never collected as a test class."""

    __test__ = False

    def runTest(self):  # pragma: no cover - TestCase needs one to instantiate
        pass


@pytest.fixture(scope="module")
def probe():
    """Serve the fake hosts once and hand back the probe driver."""
    if _node() is None:
        pytest.skip("node is not on PATH")
    if _playwright_dir() is None:
        pytest.skip("harness/ui has no playwright package")
    driver = _Probe()
    driver.base = _FakeHost.start()
    yield driver
    _FakeHost.stop()


def _content(payload: dict) -> dict:
    """The first sample's content check."""
    samples = payload.get("samples") or []
    assert samples, "no sample: %r" % (payload,)
    return samples[0].get("content") or {}


def test_a_display_contents_wrapper_is_looked_through(probe):
    """A1: with the flag, the wrapper's children are probed and the page measures."""
    payload = probe.probe("contents.html", extra=("--through-contents",))
    assert payload.get("outcome") == "measured", "expected a measurement: %r" % (payload.get("reason"),)
    content = _content(payload)
    assert (content.get("moved_px") or 0) > 0, content


def test_without_the_flag_the_wrapper_is_not_looked_through(probe):
    """A2: without the flag the page refuses, as before this change."""
    payload = probe.probe("contents.html")
    assert payload.get("outcome") != "measured", payload
    assert "through_display_contents" not in str(payload)


def test_only_react_docx_asks_for_it_and_the_lane_passes_it():
    """A4: only react-docx's browser target sets the flag, and the lane passes it."""
    from perf.runner.adversarial_c10_scroll import _probe_command
    from perf.runner.benchmark_warm_cold import BROWSER_TARGETS
    asking = sorted(n for n, t in BROWSER_TARGETS.items() if t.get("c10_through_contents"))
    assert asking == ["reactdocx"]
    for name in ("reactdocx", "plate"):
        target = {**BROWSER_TARGETS[name], "editor_id": name}
        cmd = _probe_command(target=target, corpus_path=Path("x.docx"), pairs=1)
        assert ("--through-contents" in cmd) == (name == "reactdocx"), name


def test_the_content_walk_is_not_inside_the_timed_window(probe):
    """A5: the walk runs after the witness's frame, so a slow walk does not slow the sample."""
    payload = probe.probe("contents-slow.html", extra=("--through-contents",))
    assert payload.get("outcome") == "measured", "expected a measurement: %r" % (payload.get("reason"),)
    sample = (payload.get("samples") or [{}])[0]
    assert ((sample.get("content") or {}).get("moved_px") or 0) > 0, sample.get("content")
    frame_ms = sample.get("scroll_frame_ms")
    assert isinstance(frame_ms, (int, float)), sample
    assert frame_ms < 250, "the walk ran between the scroll and its frame: %r ms" % (frame_ms,)


def test_the_plain_host_keeps_its_first_pass_probe(probe):
    """A3: the plain host measures with no look-through."""
    payload = probe.probe("prose.html")
    assert payload.get("outcome") == "measured", "expected a measurement: %r" % (payload.get("reason"),)
    assert "through_display_contents" not in str(payload)
