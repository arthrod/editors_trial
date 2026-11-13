"""C14's I01-I03 check reads the whole rendered text, not a 4,000-character prefix (#181).

``build_fixture`` appends the Unicode, emoji and bidi paragraphs at the end of
every C14 document; the probe kept only ``docText.slice(0, 4000)``, so the
check could never pass on a document longer than that.
"""

from __future__ import annotations

import unittest

import perf.runner.benchmark_document as bd
from perf.analysis.interpretation import check_correctness
from perf.scenarios.catalog import scenarios
from perf.tests import test_b3_document as b3  # noqa: F401 (server and probe helpers)

FAMILY = "\U0001f468‍\U0001f469‍\U0001f467‍\U0001f466"
MARKERS = ("́", "\U0002000b", FAMILY, "\U0001f44d\U0001f3fb", "Hello", "مرحبا")
C14 = next(row for row in scenarios() if row["id"] == "C14")


def _i01_i03(text):
    """The interpretation checks C14 lists, alone (the env checks are other tests')."""
    return check_correctness(C14["correctness"], text)


class CorrectnessText(unittest.TestCase):
    def test_short_document_is_checked_whole(self):
        payload = {"document_text": "abc", "document_text_tail": "abc", "document_text_chars": 3}
        self.assertEqual(bd.c14_correctness_text(payload), "abc")

    def test_long_document_is_checked_head_and_tail(self):
        head = "x" * 4000
        tail = "y" * 3990 + " é \U0002000b"
        payload = {"document_text": head, "document_text_tail": tail, "document_text_chars": 9000}
        text = bd.c14_correctness_text(payload)
        self.assertTrue(text.startswith(head) and text.endswith(tail))

    def test_a_payload_without_a_tail_keeps_the_old_text(self):
        self.assertEqual(bd.c14_correctness_text({"document_text": "abc"}), "abc")

    def test_c14_lists_i01_to_i03(self):
        self.assertEqual(set(C14["correctness"]), {"I01", "I02", "I03"})


class ProbeRecordsTheTail(unittest.TestCase):
    """The real probe in Chromium, on a document longer than 4,000 characters.

    The fake host fits on one screen (4px text), so the probe's painted-text
    surface holds the whole document, as the gated read does for editors that
    expose their whole text.
    """

    setUpClass = classmethod(b3.FakeHostMeasurers.setUpClass.__func__)
    tearDownClass = classmethod(b3.FakeHostMeasurers.tearDownClass.__func__)
    probe = b3.FakeHostMeasurers.probe

    def test_fixture_at_the_end_passes_i01_to_i03(self):
        payload = self.probe("scale", "b3_long_fixture_at_end.html", [])
        self.assertGreater(payload.get("document_text_chars") or 0, 4000, payload.get("document_text_chars"))
        head = payload.get("document_text") or ""
        # The defect: the 4,000-character prefix holds none of the markers.
        self.assertFalse(any(marker in head for marker in MARKERS[:2]))
        self.assertFalse(_i01_i03(head)[0])
        tail = payload.get("document_text_tail") or ""
        self.assertLessEqual(len(tail), 4000)
        for marker in MARKERS:
            self.assertIn(marker, tail)
        ok, reason = _i01_i03(bd.c14_correctness_text(payload))
        self.assertTrue(ok, reason)



if __name__ == "__main__":
    unittest.main()
