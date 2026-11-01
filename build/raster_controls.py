#!/usr/bin/env python3
"""
Rasterise Word's PDFs of the control documents at the release resolution
(build/pixels.py): the A/B variants (out/ab/pdf -> out/ab/png), which
render_compare_word.py and construct_presence.py compare against, and the
SmartArt controls (out/smartart/pdf -> out/smartart/png), which
smartart_verify.py measures. Word made the PDFs; this step does not open Word.
LibreOffice's pages of the A/B variants are rendered and rasterised by
ab_table.py, in the same run as LibreOffice's corpus pages.

usage: python3 build/raster_controls.py
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixels  # noqa: E402  (build/pixels.py: the release resolution)

BASE = "/Users/arthrod/temp/T/editors_trial"
SETS = [("out/ab/pdf", "out/ab/png"), ("out/smartart/pdf", "out/smartart/png")]


def main():
    for src, dst in SETS:
        src, dst = os.path.join(BASE, src), os.path.join(BASE, dst)
        os.makedirs(dst, exist_ok=True)
        for f in sorted(os.listdir(src)):
            if not f.endswith(".pdf"):
                continue
            label = f[:-4]
            for old in os.listdir(dst):
                if old.startswith(label + "-") and old.endswith(".png"):
                    os.remove(os.path.join(dst, old))
            subprocess.run(["pdftoppm", "-r", str(pixels.DPI), "-png", os.path.join(src, f),
                            os.path.join(dst, label)], check=True)
            n = len([x for x in os.listdir(dst) if x.startswith(label + "-")])
            print("%-22s %d pages" % (label, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
