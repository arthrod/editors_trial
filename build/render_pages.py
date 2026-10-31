#!/usr/bin/env python3
"""
Render every output to PDF with LibreOffice and rasterise the first page.

This is the *rendering proxy*: it is not the editor's own renderer, it is
what a consumer sees when it opens the editor's file. The claim it supports
is therefore precise - what survives into a rendered rendering of the editor's
output.

usage: python3 build/render_pages.py <outdir>
"""
import os
import subprocess
import sys

BASE = "/Users/arthrod/temp/T/editors_trial"

TARGETS = [
    ("corpus", os.path.join(BASE, "fixture", "complex.docx")),
    ("superdoc", os.path.join(BASE, "out", "superdoc", "complex.docx")),
    ("folio", os.path.join(BASE, "out", "folio", "complex.docx")),
    ("genoffice", os.path.join(BASE, "out", "genoffice", "complex.docx")),
    ("eigenpal", os.path.join(BASE, "out", "eigenpal", "complex.docx")),
    ("office-open", os.path.join(BASE, "out", "officeopen", "complex.docx")),
    ("docen", os.path.join(BASE, "out", "docen", "complex.docx")),
    ("wordcraft", os.path.join(BASE, "out", "wordcraft", "complex.docx")),
    ("fidus", os.path.join(BASE, "out", "fidus", "complex.docx")),
    ("canvas", os.path.join(BASE, "out", "canvas", "complex.docx")),
    ("docs.plus", os.path.join(BASE, "out", "docsplus", "complex.docx")),
    ("plate", os.path.join(BASE, "out", "plate", "complex.docx")),
    ("docxodus", os.path.join(BASE, "out", "docxodus", "complex.docx")),
    ("libreoffice", os.path.join(BASE, "out", "lo_baseline", "complex.docx")),
]


def main(outdir):
    lo = os.path.join(outdir, "lo")
    png = os.path.join(outdir, "png")
    os.makedirs(lo, exist_ok=True)
    os.makedirs(png, exist_ok=True)

    for label, path in TARGETS:
        if not os.path.exists(path):
            print("%-14s MISSING" % label)
            continue
        work = os.path.join(lo, label)
        os.makedirs(work, exist_ok=True)
        pdf = os.path.join(work, "doc.pdf")
        subprocess.run(["rm", "-f", pdf], capture_output=True)
        r = subprocess.run(
            ["soffice", "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", work, path],
            capture_output=True, text=True, timeout=300)
        made = os.path.join(work, "complex.pdf")
        if os.path.exists(made):
            os.replace(made, pdf)
        if not os.path.exists(pdf):
            print("%-14s RENDER FAILED (%s)" % (label, r.stdout.strip()[:80]))
            continue
        pages = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
        n = ""
        for ln in pages.split("\n"):
            if ln.startswith("Pages:"):
                n = ln.split()[-1]
        # rasterise every page of the first two pages
        for p in (1, 2):
            subprocess.run(["pdftoppm", "-f", str(p), "-l", str(p), "-r", "72",
                            "-png", pdf, os.path.join(png, "%s_p%d" % (label, p))],
                           capture_output=True)
        print("%-14s %s pages -> %s" % (label, n, pdf))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render"))
