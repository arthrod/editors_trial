#!/usr/bin/env python3
"""
Rasterise MICROSOFT WORD's own PDF export of every output, so the report can
show what Word actually drew.

Word's export is the ground truth: it is the application the document was
written for. LibreOffice's export is the proxy - it can open every output,
including the four Word refuses.

usage: python3 build/word_pages.py <outdir>
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixels  # noqa: E402  (build/pixels.py: the release resolution)

BASE = "/Users/arthrod/temp/T/editors_trial"

ORDER = ["corpus", "superdoc", "folio", "genoffice", "eigenpal",
         "office-open", "docen", "wordcraft", "fidus", "canvas",
         "docs.plus", "plate", "docxodus", "apryse", "libreoffice"]


def main(outdir):
    worddir = os.path.join(outdir, "word")
    png = os.path.join(outdir, "png_word")
    os.makedirs(png, exist_ok=True)

    for label in ORDER:
        pdf = os.path.join(worddir, label + ".pdf")
        if not os.path.exists(pdf):
            print("%-14s no Word PDF (Word refused the file)" % label)
            continue
        info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
        pages = 0
        for ln in info.split("\n"):
            if ln.startswith("Pages:"):
                pages = int(ln.split()[-1])
        # every page, at the release resolution (build/pixels.py)
        subprocess.run(["pdftoppm", "-r", str(pixels.DPI), "-png", pdf,
                        os.path.join(png, label)], capture_output=True)
        made = sorted(f for f in os.listdir(png) if f.startswith(label + "-"))
        print("%-14s %d pages -> %d png" % (label, pages, len(made)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render"))
