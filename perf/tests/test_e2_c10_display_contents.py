"""E2: the C10 content probe looks through a ``display: contents`` wrapper.

react-docx mounts its whole document in one ``display: contents`` div inside
the scroller. Such an element has no box (its rect is 0x0 at the origin
whatever the scroll), so a probe that picks it reports "the scroll did not
move the content" although the page scrolled. The probe now looks through
such wrappers, but only when the scroller's own children give no box, so an
editor whose probe was found on the first pass keeps exactly that probe.

A1  ``contents.html`` (document inside a display:contents wrapper) measures.
A2  ``prose.html`` (the plain host) measures with the same kind of probe as
    before: no ``through_display_contents`` flag.
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
        payload = self.probe("contents.html")
        self.assertEqual(payload.get("outcome"), "measured", "expected a measurement: %r" % (payload.get("reason"),))
        content = self._content(payload)
        self.assertGreater(content.get("moved_px") or 0, 0, content)

    def test_the_plain_host_keeps_its_first_pass_probe(self):
        payload = self.probe("prose.html")
        self.assertEqual(payload.get("outcome"), "measured", "expected a measurement: %r" % (payload.get("reason"),))
        self.assertNotIn("through_display_contents", str(payload))


if __name__ == "__main__":
    unittest.main()
