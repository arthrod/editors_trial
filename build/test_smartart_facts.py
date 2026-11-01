#!/usr/bin/env python3
"""Report C's SmartArt band figures come from out/smartart/verify.json
(build/smartart_verify.py), never typed: the pixel resolution changed from
110 to 200 dpi in v0.9.3, and every typed pixel count went stale with it."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates/reports/Report C - Rendering Versus Word (2026).md"

VERIFY = {
    "band": {"page": 4, "bbox": [152, 445, 1049, 968], "w": 897, "h": 523},
    "band_measurement": {
        "page": 4, "bbox": [152, 445, 1049, 968], "band_px": 469131,
        "corpus_ink_in_band": 0, "border_variant_ink_in_band": 28000, "dpi": 200,
        "diff_px_corpus_vs_border": 28151,
        "outside_band_diff_px": 151, "outside_band_bbox": [376, 986, 377, 1137],
    },
    "controls": {
        "dgm_pic_checker": {"page3": {"diff_px": 0, "diff_bbox": None},
                            "page4": {"diff_px": 269641, "diff_bbox": [152, 445, 1049, 968]}},
        "dgm_marker": {"page4": {"diff_px": 0, "diff_bbox": None}},
        "dgm_cached": {"page4": {"diff_px": 0, "diff_bbox": None}},
    },
}


class SmartArtFacts(unittest.TestCase):
    def test_every_band_figure_comes_from_verify_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "verify.json"
            p.write_text(json.dumps(VERIFY))
            f = {}
            facts.smartart_facts(p, f)
        self.assertEqual(f["sa.dpi"], 200)
        self.assertEqual(f["sa.page"], 4)
        self.assertEqual(f["sa.band_px"], "469,131")
        self.assertEqual(f["sa.w"], 897)
        self.assertEqual(f["sa.h"], 523)
        self.assertEqual(f["sa.bbox"], "(152, 445) – (1049, 968)")
        self.assertEqual(f["sa.w_in"], "4.49")
        self.assertEqual(f["sa.h_in"], "2.62")
        self.assertEqual(f["sa.corpus_ink"], 0)
        self.assertEqual(f["sa.border_ink"], "28,000")
        self.assertEqual(f["sa.checker"], "269,641")
        self.assertEqual(f["sa.checker_bbox"], "(152, 445) – (1049, 968)")
        self.assertEqual(f["sa.marker"], 0)
        self.assertEqual(f["sa.cached"], 0)
        self.assertEqual(f["sa.border_diff"], "28,151")
        self.assertEqual(f["sa.outside"], 151)
        self.assertEqual(f["sa.outside_bbox"], "(376, 986) – (377, 1137)")

    def test_missing_file_adds_nothing(self):
        f = {}
        facts.smartart_facts(Path("/nonexistent/verify.json"), f)
        self.assertEqual(f, {})


class ReportCText(unittest.TestCase):
    def test_no_typed_110_dpi_figure_is_left(self):
        s = TEMPLATE.read_text()
        for stale in ("142,766", "73,065", "8,492", "494 × 289", "(83, 244)", "1210 × 935", "leaves 335"):
            self.assertNotIn(stale, s, stale)
        # "110 dpi" may only appear in a paragraph about earlier editions
        for para in s.split("\n\n"):
            if "110 dpi" in para:
                self.assertIn("earlier editions", para.lower(), para[:120])

    def test_band_figures_are_placeholders(self):
        s = TEMPLATE.read_text()
        for key in ("sa.band_px", "sa.checker", "sa.border_ink", "sa.bbox", "pixels.dpi"):
            self.assertIn("{{" + key, s, key)


if __name__ == "__main__":
    unittest.main()
