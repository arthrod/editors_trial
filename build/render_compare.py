#!/usr/bin/env python3
"""
Rendered comparison: what a reader actually sees after each editor's round trip.

Renders the corpus and every editor's output to PDF with LibreOffice, extracts
the laid-out text, and diffs it against the corpus's own rendering. This is the
third axis of the study, measured rather than asserted:

  serialized     written into the output package
  pass-through   copied byte-for-byte, never understood
  rendered       still visible when the output is rendered

usage: python3 build/render_compare.py
"""
import os
import re
import subprocess
import sys
import tempfile

BASE = "/Users/arthrod/temp/T/editors_trial"
WORK = "/tmp/rendercmp"
os.makedirs(WORK, exist_ok=True)

TARGETS = [
    ("Plate.js", "out/plate/complex.docx"),
    ("Docxodus", "out/docxodus/complex.docx"),
    ("SuperDoc", "out/superdoc/complex.docx"),
    ("Folio", "out/folio/complex.docx"),
    ("GenOffice", "out/genoffice/complex.docx"),
    ("eigenpal", "out/eigenpal/complex.docx"),
    ("office-open", "out/officeopen/complex.docx"),
    ("Docen", "out/docen/complex.docx"),
    ("WordCraft", "out/wordcraft/complex.docx"),
    ("Fidus Writer", "out/fidus/complex.docx"),
    ("canvas-editor + plugin", "out/canvas/complex.docx"),
    ("docs.plus", "out/docsplus/complex.docx"),
    ("Apryse WebViewer", "out/apryse/complex.docx"),
    ("LibreOffice (baseline)", "out/lo_baseline/complex.docx"),
]


def to_pdf(docx, outdir):
    subprocess.run(["soffice", "--headless", "--norestore", "--convert-to", "pdf",
                    "--outdir", outdir, docx],
                   capture_output=True, timeout=240)
    pdf = os.path.join(outdir,
                       os.path.splitext(os.path.basename(docx))[0] + ".pdf")
    return pdf if os.path.exists(pdf) else None


def text_of(pdf):
    r = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                       capture_output=True, text=True)
    return r.stdout


def lines(t):
    out = []
    for ln in t.splitlines():
        s = ln.strip()
        if s:
            out.append(re.sub(r"\s+", " ", s))
    return out


def main():
    tmp = tempfile.mkdtemp(dir=WORK)
    ref_pdf = to_pdf(os.path.join(BASE, "fixture", "complex.docx"), tmp)
    ref = lines(text_of(ref_pdf))
    ref_words = len(re.findall(r"\S+", text_of(ref_pdf)))
    ref_set = set(ref)
    print("CORPUS render: %d lines, %d words, %d pages"
          % (len(ref), ref_words,
             text_of(ref_pdf).count("\f")))
    print()
    print("%-24s %6s %6s %7s %9s %8s" %
          ("output", "lines", "words", "pages", "missing", "extra"))
    print("-" * 70)
    rows = []
    for label, rel in TARGETS:
        p = os.path.join(BASE, rel)
        if not os.path.exists(p):
            continue
        d = tempfile.mkdtemp(dir=tmp)
        pdf = to_pdf(p, d)
        if not pdf:
            print("%-24s  (conversion failed)" % label)
            continue
        t = text_of(pdf)
        ln = lines(t)
        words = len(re.findall(r"\S+", t))
        pages = t.count("\f")
        s = set(ln)
        missing = len(ref_set - s)
        extra = len(s - ref_set)
        print("%-24s %6d %6d %7d %9d %8d"
              % (label, len(ln), words, pages, missing, extra))
        rows.append((label, len(ln), words, pages, missing, extra, ln))
    print()
    print("missing = corpus lines no longer present in the rendered output")
    print("extra   = lines in the rendered output that were not in the corpus")
    return rows


if __name__ == "__main__":
    main()
