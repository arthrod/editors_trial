#!/usr/bin/env python3
"""Every pixel measurement rasterises at one resolution, build/pixels.py's DPI.
Release rule from v0.9.3: 200 dpi (110 before). A script with its own literal
resolution would compare pages drawn at two different scales."""
import re
import sys
import unittest
from pathlib import Path

BUILD = Path(__file__).resolve().parent
sys.path.insert(0, str(BUILD))
PIXEL_SCRIPTS = ["word_pages.py", "lo_pages.py", "lo_render_compare.py", "smartart_verify.py", "raster_controls.py", "strips.py", "ab_table.py"]


class OneResolution(unittest.TestCase):
    def test_the_release_resolution_is_200_dpi(self):
        import pixels
        self.assertEqual(pixels.DPI, 200)

    def test_every_pixel_script_takes_it_from_pixels_py(self):
        for name in PIXEL_SCRIPTS:
            s = (BUILD / name).read_text()
            self.assertIn("pixels", s, name)
            self.assertIsNone(re.search(r'"-r",\s*"\d+"', s), name)
            self.assertNotIn("110", s, name)

    def test_no_shell_script_rasterises_at_its_own_resolution(self):
        for sh in sorted(BUILD.glob("*.sh")):
            for line in sh.read_text().splitlines():
                if "pdftoppm" in line and not line.lstrip().startswith("#"):
                    self.assertIsNone(re.search(r"-r\s+\d", line), f"{sh.name}: {line.strip()}")

    def test_every_compared_page_image_is_at_the_release_resolution(self):
        """A page image is Letter (8.5 or 11 in) or, for Fidus Writer's A4 output,
        A4 (8.27 or 11.69 in) wide; read the width from the PNG header."""
        import struct
        import pixels
        widths = {round(w * pixels.DPI) for w in (8.5, 11, 8.27, 11.69)}
        root = BUILD.parent / "out"
        wrong = []
        for d in ("ab/png", "ab/lo_png", "smartart/png", "render/png_word", "render/lo_png", "ui/libreoffice"):
            for png in sorted((root / d).glob("*.png")):
                w = struct.unpack(">I", png.read_bytes()[16:20])[0]
                if w not in widths:
                    wrong.append(f"{d}/{png.name}: {w}")
        self.assertEqual(wrong[:5], [])

    def test_libreoffice_variants_render_with_the_libreoffice_corpus(self):
        s = (BUILD / "ab_table.py").read_text()
        self.assertIn('lrc.render("corpus"', s)
        self.assertIn('"out/ab/%s.docx" % v', s)

    def test_lo_pages_covers_apryse(self):
        self.assertIn('"apryse"', (BUILD / "lo_pages.py").read_text())



class LibreOfficeTable(unittest.TestCase):
    def test_lo_pixel_facts_and_the_report_c_table_use_them(self):
        import json, tempfile
        import facts
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lo.json"
            p.write_text(json.dumps({"apryse": {"pages": 6, "diff": 24540, "pct": 4.32, "verdict": "very close"},
                                     "plate": {"pages": 2, "diff": None, "pct": None, "verdict": "different"}}))
            f = {}
            facts.lo_pixel_facts(p, f)
        self.assertEqual((f["lpx.apryse.pages"], f["lpx.apryse.diff_px"], f["lpx.apryse.pct"]), (6, "24,540", "4.32%"))
        self.assertEqual((f["lpx.plate.diff_px"], f["lpx.plate.pct"], f["lpx.plate.verdict"]), ("—", "—", "different"))
        t = (BUILD.parent / "templates/reports/Report C - Rendering Versus Word (2026).md").read_text()
        head = t.index("| Output | LO pages |")
        rows = t[head:t.index("\n\n", head)].splitlines()[2:]
        self.assertTrue(any("Apryse" in r for r in rows))
        for r in rows:
            cells = [c.strip("* ") for c in r.strip("|").split("|")]
            for c in cells[1:]:
                self.assertRegex(c, r"^\{\{lpx\.[a-z_.]+\}\}$", r)


if __name__ == "__main__":
    unittest.main()
