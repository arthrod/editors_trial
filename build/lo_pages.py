#!/usr/bin/env python3
"""
Rasterise every LibreOffice PDF (the 13 targets plus the 5 A/B variants) at a
consistent resolution and page coverage, so the LO-side pixel comparison has
the same shape as the Word-side one.

usage: python3 build/lo_pages.py <render-dir>
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixels  # noqa: E402  (build/pixels.py: the release resolution)

BASE = "/Users/arthrod/temp/T/editors_trial"
DPI = str(pixels.DPI)  # build/pixels.py

TARGETS = ["corpus", "superdoc", "folio", "genoffice", "eigenpal",
           "office-open", "docen", "wordcraft", "fidus", "canvas",
           "docs.plus", "plate", "docxodus", "apryse", "libreoffice"]

VARIANTS = ["no_dgm", "no_chart", "no_pic", "no_wps", "no_ole"]


def main():
    rend = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render")
    out = os.path.join(rend, "lo_png")
    os.makedirs(out, exist_ok=True)

    for lab in TARGETS:
        pdf = os.path.join(rend, "lo", lab, "doc.pdf")
        if not os.path.exists(pdf):
            print("%-14s no LO pdf" % lab)
            continue
        subprocess.run(["pdftoppm", "-r", DPI, "-png", pdf,
                        os.path.join(out, lab)], capture_output=True)
        n = len([f for f in os.listdir(out) if f.startswith(lab + "-")])
        print("%-14s %d pages" % (lab, n))

    for lab in VARIANTS:
        pdf = os.path.join(BASE, "out", "ab", "lo", lab, "doc.pdf")
        if not os.path.exists(pdf):
            print("%-14s no LO pdf" % lab)
            continue
        subprocess.run(["pdftoppm", "-r", DPI, "-png", pdf,
                        os.path.join(out, lab)], capture_output=True)
        n = len([f for f in os.listdir(out) if f.startswith(lab + "-")])
        print("%-14s %d pages" % (lab, n))


if __name__ == "__main__":
    main()
