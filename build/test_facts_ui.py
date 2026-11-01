#!/usr/bin/env python3
"""Report C's capture date comes from the capture run, not from the template."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts  # noqa: E402


class UiFacts(unittest.TestCase):
    def test_capture_date_is_read_from_the_stamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            ui = Path(tmp)
            (ui / "captured_at.txt").write_text("2026-11-01\n")
            got: dict = {}
            facts.ui_facts(ui, got)
            self.assertEqual(got, {"ui.date": "2026-11-01"})

    def test_no_stamp_means_no_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            got: dict = {}
            facts.ui_facts(Path(tmp), got)
            self.assertEqual(got, {})

    def test_a_malformed_stamp_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            ui = Path(tmp)
            (ui / "captured_at.txt").write_text("yesterday\n")
            with self.assertRaises(ValueError):
                facts.ui_facts(ui, {})


class StampFacts(unittest.TestCase):
    def test_stamp_attribution_becomes_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "stamp.json").write_text(
                '{"stamp_parts": ["word/header3.xml", "word/media/image2.png"], "stamped": true,'
                ' "unseparable": ["ref.headerTrackedChange"], "own": ["sec.landscape", "sdt.count"],'
                ' "labels": {"ref.headerTrackedChange": "tracked change inside header kept",'
                ' "sec.landscape": "landscape section kept", "sdt.count": "content controls kept (>=5)"}}')
            got: dict = {}
            facts.stamp_facts(d, got)
            self.assertEqual(got["stamp.apryse.parts"], 2)
            self.assertEqual(got["stamp.apryse.unseparable"], 1)
            self.assertEqual(got["stamp.apryse.own"], 2)
            self.assertEqual(got["stamp.apryse.unseparable_labels"], "tracked change inside header kept")


if __name__ == "__main__":
    unittest.main()
