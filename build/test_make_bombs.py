#!/usr/bin/env python3
"""The bomb builder and the scorer. No editor is launched."""
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bomb_score
import make_bombs


class MakeBombsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="bombs-")
        cls.built = make_bombs.build(__import__("pathlib").Path(cls.tmp), "file:///tmp/xxe-canary.txt")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_b1_is_a_small_zip_of_a_large_part(self):
        path = self.built["B1"]
        self.assertLess(path.stat().st_size, 200_000)
        with zipfile.ZipFile(path) as zf:
            info = zf.getinfo("word/document.xml")
        self.assertGreater(info.file_size, 64 * 1024 * 1024)
        # Deflate cannot beat about 1032:1. This asserts the real ceiling, above 1000:1.
        self.assertGreater(info.file_size / max(info.compress_size, 1), 1000)

    def test_b2_has_the_entry_flood_and_b5_does_not_expand(self):
        with zipfile.ZipFile(self.built["B2"]) as zf:
            flood = [n for n in zf.namelist() if n.startswith("customXml/p")]
        self.assertEqual(len(flood), 25000)
        with zipfile.ZipFile(self.built["B5"]) as zf:
            raw = zf.read("word/document.xml")
        self.assertLess(len(raw), 100_000)
        self.assertLess(raw.count(make_bombs.LOL.encode()), 20)
        self.assertIn(b"file:///tmp/xxe-canary.txt", raw)
        self.assertNotIn(b"XXE_CANARY_editors_trial", raw)
        self.assertEqual(bomb_score.fidelity("B5", self.built["B5"].read_bytes()), "preserved")
        self.assertEqual(bomb_score.fidelity("B5", b"BOMB_BODY_OK only"), "dropped")

    def test_b6_keeps_a_traversal_name(self):
        with zipfile.ZipFile(self.built["B6"]) as zf:
            names = zf.namelist()
            rels = zf.read("word/_rels/document.xml.rels")
        self.assertTrue(any(".." in name for name in names))
        self.assertIn(b"etc/passwd", rels)
        self.assertEqual(bomb_score.fidelity("B6", self.built["B6"].read_bytes()), "preserved")
        self.assertEqual(bomb_score.fidelity("B6", b"root:x:0:0:root"), "preserved")
        self.assertEqual(bomb_score.fidelity("B6", b"clean"), "dropped")

    def test_score_separates_preserving_a_marker_from_a_crash(self):
        kept = b"javascript:alert(1)"
        fid = bomb_score.fidelity("B8", kept)
        self.assertEqual(fid, "preserved")
        self.assertEqual(bomb_score.caught(fid, "ok"), "no")
        self.assertEqual(bomb_score.fidelity("B8", b"clean"), "dropped")
        self.assertEqual(bomb_score.caught("dropped", "bounded-reject"), "yes")
        self.assertEqual(bomb_score.safety(0, True, False), "hang")
        self.assertEqual(bomb_score.caught("refused", "hang"), "no")
        self.assertEqual(bomb_score.safety(-9, False, False), "crash")
        self.assertEqual(bomb_score.safety(0, False, True), "leak")
        self.assertEqual(bomb_score.caught("dropped", "leak"), "no")
        self.assertEqual(bomb_score.caught("not-run", "not-run"), "no")
        self.assertEqual(bomb_score.fidelity("B10", b"\xff\xfe<<<"), "preserved")
        self.assertEqual(bomb_score.fidelity("B10", b"clean"), "dropped")


if __name__ == "__main__":
    unittest.main()
