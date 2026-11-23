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

import unittest

from perf.tests import test_e2_c10_late_mount as late

_FakeHost, _node, _playwright_dir = late._FakeHost, late._node, late._playwright_dir


class DisplayContentsScrollTests(unittest.TestCase):
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

    probe = late.LateMountScrollTests.probe

    def _content(self, payload: dict) -> dict:
        samples = payload.get("samples") or []
        self.assertTrue(samples, "no sample: %r" % (payload,))
        return samples[0].get("content") or {}

    def test_a_display_contents_wrapper_is_looked_through(self):
        payload = self.probe("contents.html", extra=("--through-contents",))
        self.assertEqual(payload.get("outcome"), "measured", "expected a measurement: %r" % (payload.get("reason"),))
        content = self._content(payload)
        self.assertGreater(content.get("moved_px") or 0, 0, content)

    def test_without_the_flag_the_wrapper_is_not_looked_through(self):
        payload = self.probe("contents.html")
        self.assertNotEqual(payload.get("outcome"), "measured", payload)
        self.assertNotIn("through_display_contents", str(payload))

    def test_only_react_docx_asks_for_it_and_the_lane_passes_it(self):
        from pathlib import Path

        from perf.runner.adversarial_c10_scroll import _probe_command
        from perf.runner.benchmark_warm_cold import BROWSER_TARGETS
        asking = sorted(n for n, t in BROWSER_TARGETS.items() if t.get("c10_through_contents"))
        self.assertEqual(asking, ["reactdocx"])
        for name in ("reactdocx", "plate"):
            target = {**BROWSER_TARGETS[name], "editor_id": name}
            cmd = _probe_command(target=target, corpus_path=Path("x.docx"), pairs=1)
            self.assertEqual("--through-contents" in cmd, name == "reactdocx", name)

    def test_the_content_walk_is_not_inside_the_timed_window(self):
        payload = self.probe("contents-slow.html", extra=("--through-contents",))
        self.assertEqual(payload.get("outcome"), "measured", "expected a measurement: %r" % (payload.get("reason"),))
        sample = (payload.get("samples") or [{}])[0]
        self.assertGreater((sample.get("content") or {}).get("moved_px") or 0, 0, sample.get("content"))
        frame_ms = sample.get("scroll_frame_ms")
        self.assertIsInstance(frame_ms, (int, float), sample)
        self.assertLess(frame_ms, 250, "the walk ran between the scroll and its frame: %r ms" % (frame_ms,))

    def test_the_plain_host_keeps_its_first_pass_probe(self):
        payload = self.probe("prose.html")
        self.assertEqual(payload.get("outcome"), "measured", "expected a measurement: %r" % (payload.get("reason"),))
        self.assertNotIn("through_display_contents", str(payload))


if __name__ == "__main__":
    unittest.main()
