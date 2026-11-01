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


if __name__ == "__main__":
    unittest.main()
