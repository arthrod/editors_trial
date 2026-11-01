#!/usr/bin/env python3
"""Report C's A/B table (section 6.3) is generated from the variants' pages
(build/ab_table.py), never typed. v0.9.2 published it at 110 dpi with the prose
under it citing the picture's figures for the chart ("42,474 and 42,474
differing pixels for 190 and 190 bytes")."""
import sys
import unittest
from pathlib import Path

BUILD = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD))
import ab_table  # noqa: E402
import facts  # noqa: E402

TEMPLATE = BUILD.parent / "templates/reports/Report C - Rendering Versus Word (2026).md"

DATA = {
    "dpi": 200,
    "corpus_bytes": 161459,
    "variants": {
        "no_w14": {"bytes": 150473, "pages": {"2": {"diff_px": 3000, "bbox": [152, 527, 651, 545]}}},
        "no_dgm": {"bytes": 161325, "pages": {"3": {"diff_px": 30000, "bbox": [1, 2, 3, 4]},
                                              "4": {"diff_px": 50000, "bbox": [5, 6, 7, 8]}},
                   "lo_pages": {"3": {"diff_px": 60000, "bbox": [0, 0, 1, 1]},
                                "4": {"diff_px": 90000, "bbox": [0, 0, 1, 1]}},
                   "blue": {"3": 70000, "4": 0}},
    },
    "corpus_blue": {"3": 35000, "4": 35500},
}


class Table(unittest.TestCase):
    def test_rows_carry_the_measurement(self):
        t = ab_table.table(DATA)
        lines = t.splitlines()
        self.assertTrue(lines[0].startswith("| Variant | Construct removed | Word PDF bytes | Δ |"))
        self.assertIn("| corpus | — | 161,459 | — | — |", t)
        self.assertIn("| `no_w14` | the `w14:textOutline` run | 150,473 | −10,986 | 3,000 on page 2, bbox (152, 527) – (651, 545) |", t)
        self.assertIn("30,000 on page 3 + 50,000 on page 4 — **all of it reflow**", t)
        self.assertIn("**−134**", t)  # the smallest byte delta is bold

    def test_facts_publish_the_table_and_each_variant(self):
        f = {}
        ab_table.facts_into(DATA, f)
        self.assertEqual(f["ab.no_w14.px"], "3,000")
        self.assertEqual(f["ab.no_w14.page"], "2")
        self.assertEqual(f["ab.no_dgm.px"], "80,000")
        self.assertEqual(f["ab.no_w14.delta"], "−10,986")
        self.assertIn("| Variant |", f["ab.table"])
        self.assertEqual(f["ab.no_dgm.lo.p3.px"], "60,000")
        self.assertEqual(f["ab.no_dgm.lo.p4.px"], "90,000")
        self.assertEqual(f["ab.corpus.blue.p3"], "35,000")
        self.assertEqual(f["ab.corpus.blue.p4"], "35,500")
        self.assertEqual(f["ab.no_dgm.blue.p3"], "70,000")
        self.assertEqual(f["ab.no_dgm.blue.p4"], "0")

    def test_blue_is_the_ole_and_picture_colour_only(self):
        self.assertTrue(ab_table.is_blue((31, 119, 180)))
        self.assertTrue(ab_table.is_blue((40, 125, 175)))
        self.assertFalse(ab_table.is_blue((68, 114, 196)))   # the chart's bars
        self.assertFalse(ab_table.is_blue((0, 0, 0)))


class Template(unittest.TestCase):
    def test_section_6_3_uses_the_facts(self):
        s = TEMPLATE.read_text()
        self.assertIn("{{ab.table}}", s)
        for stale in ("10,209", "10,608", "20,817", "18,904", "29,996", "y = 244", "(84, 542)", "1,709", "2,069", "28,135", "42,474", "40,847", "(83, 811)", "(83, 252)"):
            self.assertNotIn(stale, s, stale)


if __name__ == "__main__":
    unittest.main()
