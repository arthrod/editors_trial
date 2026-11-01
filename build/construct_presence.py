#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=11"]
# ///
"""
Which constructs are VISIBLE in each editor's rendering?

The method is a three-way match against the A/B variants:

  corpus      Word's rendering of the corpus (ground truth)
  variant     Word's rendering of the corpus with ONE construct removed
  editor      Word's rendering of the editor's output

If the editor's rendering is closer to the corpus than to the variant, the
construct survived into the rendering. If it is closer to the variant, the
construct was dropped. If the corpus and the variant are nearly identical
(no signal), the construct is not resolvable this way and the cell says so.

This is a PIXEL test, because Word's PDF export draws several constructs as
vector outlines whose glyphs are invisible to text extraction.

usage: python3 build/construct_presence.py <render-dir>
"""
import json
import os
import sys

from PIL import Image, ImageChops

BASE = "/Users/arthrod/temp/T/editors_trial"

CONSTRUCTS = [
    ("SmartArt", "no_dgm", "word/diagrams/data1.xml"),
    ("Chart", "no_chart", "word/charts/chart1.xml"),
    ("Image", "no_pic", "word/media/image1.png"),
    ("Text box (mc:Choice)", "no_wps", "word/document.xml"),
    ("OLE object", "no_ole", "word/embeddings/embedded1.docx"),
]

WORD_EDITORS = ["superdoc", "genoffice", "eigenpal", "wordcraft",
                 "canvas", "docs.plus", "plate", "docxodus", "apryse", "libreoffice"]

LO_EDITORS = ["superdoc", "folio", "genoffice", "eigenpal", "office-open",
               "docen", "wordcraft", "fidus", "canvas", "docs.plus",
               "plate", "docxodus", "apryse", "libreoffice"]


def diff(a_path, b_path, thresh=8):
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if a.size != b.size:
        return 10 ** 7
    d = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > thresh else 0)
    return d.histogram()[255]


def word_pages(d, label):
    out = []
    i = 1
    while os.path.exists(os.path.join(d, "%s-%d.png" % (label, i))):
        out.append(os.path.join(d, "%s-%d.png" % (label, i)))
        i += 1
    return out


def lo_pages(rend, label):
    d = os.path.join(rend, "lo_png")
    out = []
    i = 1
    while os.path.exists(os.path.join(d, "%s-%d.png" % (label, i))):
        out.append(os.path.join(d, "%s-%d.png" % (label, i)))
        i += 1
    return out


def main():
    rend = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render")
    wdir = os.path.join(rend, "png_word")
    adir = os.path.join(BASE, "out", "ab", "png")

    corpus_w = word_pages(wdir, "corpus")
    variants = {name: word_pages(adir, v) for name, v, _ in CONSTRUCTS}

    result = {}

    # ---- WORD (ground truth) ----
    print("=== MICROSOFT WORD rendering: construct visible? ===\n")
    for name, vlabel, _ in CONSTRUCTS:
        vp = variants[name]
        signal = sum(diff(corpus_w[i], vp[i]) for i in range(min(len(corpus_w), len(vp))))
        print("%s  (corpus vs %s: %d px differ)" % (name, vlabel, signal))

    print()
    print("%-12s %-22s %-22s %-22s %-22s %-22s" % (
        "editor", *[c[0] for c in CONSTRUCTS]))
    print("-" * 126)
    for lab in WORD_EDITORS:
        ep = word_pages(wdir, lab)
        if not ep:
            continue
        cells = []
        for name, vlabel, _ in CONSTRUCTS:
            vp = variants[name]
            dc = dv = 0
            for i in range(min(len(corpus_w), len(ep), len(vp))):
                dc += diff(corpus_w[i], ep[i])
                dv += diff(vp[i], ep[i])
            if dc == 0 and dv == 0:
                cells.append("no signal")
            elif dc < dv * 0.5:
                cells.append("VISIBLE")
            elif dv < dc * 0.5:
                cells.append("absent")
            else:
                cells.append("ambiguous")
        result[lab] = cells
        print("%-12s %-22s %-22s %-22s %-22s %-22s" % (lab, *cells))

    print()
    print("=== LIBREOFFICE proxy (for the four Word refuses) ===\n")
    print("%-12s %-22s %-22s %-22s %-22s %-22s" % (
        "editor", *[c[0] for c in CONSTRUCTS]))
    print("-" * 126)
    for lab in LO_EDITORS:
        ep = lo_pages(rend, lab)
        cp = lo_pages(rend, "corpus")
        if not ep or not cp:
            continue
        cells = []
        for name, vlabel, _ in CONSTRUCTS:
            # the LO corpus render and the LO variant render
            vp = lo_pages(rend, vlabel.replace("no_", ""))
            if not vp:
                cells.append("-")
                continue
            dc = dv = 0
            for i in range(min(len(cp), len(ep), len(vp))):
                dc += diff(cp[i], ep[i])
                dv += diff(vp[i], ep[i])
            if dc == 0 and dv == 0:
                cells.append("no signal")
            elif dc < dv * 0.5:
                cells.append("VISIBLE")
            elif dv < dc * 0.5:
                cells.append("absent")
            else:
                cells.append("ambiguous")
        print("%-12s %-22s %-22s %-22s %-22s %-22s" % (lab, *cells))

    with open(os.path.join(rend, "construct_presence.json"), "w") as f:
        json.dump({"constructs": [c[0] for c in CONSTRUCTS], "word": result}, f, indent=1)


if __name__ == "__main__":
    main()
