#!/usr/bin/env python3
"""
The Rendering report's tables.

Three independent verdicts per construct:
  PACKAGE  the construct's markup is in the editor's output package
  WORD     the construct is visible in MICROSOFT WORD's own rendering of it
  LO       the construct is visible in a LIBREOFFICE rendering of it

The WORD column is the ground truth. Where Word draws a construct as vector
outlines (a w14 text outline, OMML math), the PDF text layer cannot see it and
the verdict comes from the A/B pixel test instead - see PIXEL_VERDICTS.

usage: python3 build/render_report.py <render-dir>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_inventory as ri  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"

# Constructs whose Word verdict comes from the A/B pixel test rather than the
# text layer. Each was proved by removing exactly that construct from the
# corpus and rendering the result in Word.
#
#   "drawn"      Word draws it (visible on the page)
#   "not-drawn"  Word does NOT draw it (the space is reserved but nothing shows)
PIXEL_VERDICTS = {
    "w14 attributes and elements": "drawn",   # no_w14.docx: 1709 px differ on page 2
    "OMML math": "drawn",                      # no_math.docx: 2069 px differ on page 4
    "SmartArt (step 1)": "not-drawn",         # no_dgm.docx: the slot is reserved, nothing drawn
    "SmartArt (step 2)": "not-drawn",
}

EDITORS = ["superdoc", "folio", "genoffice", "eigenpal", "office-open",
           "docen", "wordcraft", "fidus", "canvas", "docs.plus", "plate",
           "docxodus", "libreoffice"]

# Constructs that LIBREOFFICE cannot render at all, so a LibreOffice-only
# verdict for them is meaningless. Measured on the corpus itself: LibreOffice
# renders the comment ANCHOR text but never the comment body or the balloon.
# For an output Word refuses, the verdict for these is unresolvable.
LO_UNSUPPORTED = {
    "Comment": "LibreOffice renders the comment anchor but never the body",
}

PRETTY = {
    "superdoc": "SuperDoc", "folio": "Folio", "genoffice": "GenOffice",
    "eigenpal": "eigenpal", "office-open": "office-open", "docen": "Docen",
    "wordcraft": "WordCraft", "fidus": "Fidus Writer",
    "canvas": "canvas-editor", "docs.plus": "docs.plus", "plate": "Plate.js",
    "docxodus": "Docxodus",
    "libreoffice": "LibreOffice",
}


def cell(e, name):
    p = e["pkg"].get(name)
    if p is None:
        return "—"
    r = e["lo"].get(name)
    w = e["word"].get(name)
    # the pixel verdict only applies to a construct that is IN the package:
    # if it is not there, there is nothing that could have been rendered
    if name in PIXEL_VERDICTS and w is not None and p:
        w = PIXEL_VERDICTS[name] == "drawn"
    # LibreOffice cannot render this construct at all, so without a Word
    # rendering the verdict is unresolvable, not negative
    if name in LO_UNSUPPORTED and w is None:
        return "?" if p else "—"
    if r is None and w is None:
        return "P" if p else "—"
    rendered = (w is True) or (w is None and r is True)
    if p and rendered:
        return "both"
    if p:
        return "**file**"
    if rendered:
        return "render"
    return "—"


def main(outdir):
    rows = ri.build(outdir)
    labels = list(rows.keys())
    names = [n for n, _ in ri.PROBES] + [n for n, _ in ri.RASTER]

    print("### Construct visibility\n")
    print("| Construct | " + " | ".join(PRETTY.get(l, l) for l in labels) + " |")
    print("|---|" + "---|" * len(labels))
    for n in names:
        print("| %s | %s |" % (n, " | ".join(cell(rows[l], n) for l in labels)))

    print("\n### Page counts and image counts\n")
    print("| Output | Word pages | Word images | LO pages | LO images |")
    print("|---|---:|---:|---:|---:|")
    for l in labels:
        e = rows[l]
        print("| %s | %s | %s | %s | %s |" % (
            PRETTY.get(l, l),
            e["word_pages"] if e["has_word_pdf"] else "—",
            e["word_images"] if e["has_word_pdf"] else "—",
            e["lo_pages"], e["lo_images"]))

    # the headline: what is in the package but NOT rendered, per editor
    print("\n### In the package but not rendered\n")
    print("| Output | Constructs present in the file and NOT visible in the rendering | Count |")
    print("|---|---|---:|")
    for l in labels:
        e = rows[l]
        missing = []
        for n, _ in ri.PROBES:
            p = e["pkg"].get(n)
            if not p:
                continue
            r = e["lo"].get(n)
            w = e["word"].get(n)
            if n in PIXEL_VERDICTS and w is not None:
                w = PIXEL_VERDICTS[n] == "drawn"
            if n in LO_UNSUPPORTED and w is None:
                continue  # unresolvable without a Word rendering
            rendered = (w is True) or (w is None and r is True)
            if not rendered:
                missing.append(n)
        print("| %s | %s | %d |" % (
            PRETTY.get(l, l),
            ", ".join(missing) if missing else "—", len(missing)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render"))
