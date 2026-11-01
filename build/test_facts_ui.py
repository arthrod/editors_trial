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


class ReleaseFacts(unittest.TestCase):
    def test_release_date_and_cutoff_come_from_the_pin_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "release.json").write_text('{"date": "2026-11-01", "cutoff": "2026-10-27"}')
            got: dict = {}
            facts.release_facts(d / "release.json", got)
            self.assertEqual(got, {"release.date": "2026-11-01", "release.cutoff": "2026-10-27"})

    def test_a_malformed_release_date_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "release.json").write_text('{"date": "soon", "cutoff": "2026-10-27"}')
            with self.assertRaises(ValueError):
                facts.release_facts(d / "release.json", {})


class ReadFacts(unittest.TestCase):
    def test_code_read_commits_come_from_the_release_that_read_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "facts-v0.9.0.json"
            old.write_text('{"ver.plate.commit": "08b1571f2", "ver.plate.date": "2026-10-30", "rt.plate.weighted": 50}')
            got: dict = {}
            facts.read_facts(old, "v0.9.0", got)
            self.assertEqual(got, {"read.release": "v0.9.0", "read.plate.commit": "08b1571f2",
                                   "read.plate.date": "2026-10-30"})


class CountFacts(unittest.TestCase):
    def test_participants_editors_and_open_source_editors(self):
        got = {f"rt.{t}.weighted": 1 for t in ("superdoc", "docxodus", "apryse", "plate", "lo_baseline", "folio-editor")}
        facts.count_facts(got)
        self.assertEqual(got["count.participants"], 4)       # lanes and the baseline are not participants
        self.assertEqual(got["count.participants_others"], 3)
        self.assertEqual(got["count.editors"], 3)            # Docxodus is an SDK
        self.assertEqual(got["count.open_editors"], 2)       # Apryse is closed source
        self.assertEqual(got["count.open_editors_others"], 1)


if __name__ == "__main__":
    unittest.main()
