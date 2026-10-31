#!/usr/bin/env python3
"""
Rendering comparison against MICROSOFT WORD's own rendering.

For every editor output that Word could open, compare Word's page-by-page
rendering of the output against Word's page-by-page rendering of the corpus.

The corpus render is the ground truth: Word is the application the document
was written for. The comparison is at the PIXEL level, because Word's PDF
export draws several constructs as vector outlines (a w14 text outline, OMML
math, a text box) whose glyphs are invisible to text extraction while being
perfectly visible on the page.

Also resolves each construct against the A/B variants: a variant of the corpus
with exactly one construct removed from the body. If an editor's rendering
matches the corpus better than it matches the variant, the construct survived.

usage: python3 build/render_compare_word.py <render-dir>
"""
import json
import os
import sys

from PIL import Image, ImageChops

BASE = "/Users/arthrod/temp/T/editors_trial"

EDITORS = ["superdoc", "genoffice", "eigenpal", "wordcraft",
           "canvas", "docs.plus", "plate", "docxodus", "libreoffice"]

# construct -> the A/B variant that removes it
VARIANTS = {
    "SmartArt": "no_dgm",
    "Chart": "no_chart",
    "Image": "no_pic",
    "Text box (mc:Choice)": "no_wps",
    "OLE object": "no_ole",
}


def ink(path):
    im = Image.open(path).convert("L")
    h = im.histogram()
    return im.size[0] * im.size[1] - h[255]


def diff(a_path, b_path, thresh=8):
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if a.size != b.size:
        return {"size_mismatch": True, "size_a": a.size, "size_b": b.size}
    d = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > thresh else 0)
    hist = d.histogram()
    return {
        "size_mismatch": False,
        "size": a.size,
        "diff_px": hist[255],
        "total_px": a.size[0] * a.size[1],
        "bbox": d.getbbox(),
    }


def pages(d, label):
    p = os.path.join(d, "%s-%d.png" % (label, 1))
    out = []
    i = 1
    while os.path.exists(p):
        out.append(p)
        i += 1
        p = os.path.join(d, "%s-%d.png" % (label, i))
    return out


def main():
    rend = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render")
    wdir = os.path.join(rend, "png_word")
    adir = os.path.join(BASE, "out", "ab", "png")

    ref_pages = pages(wdir, "corpus")
    print("corpus: %d pages, ink %s" % (
        len(ref_pages), [ink(p) for p in ref_pages]))

    variant_pages = {}
    for name, v in VARIANTS.items():
        vp = pages(adir, v)
        variant_pages[name] = vp
        print("variant %-22s %d pages" % (name, len(vp)))

    rows = {}
    print()
    print("%-12s %6s %10s %10s %12s" % (
        "editor", "pages", "diff_px", "ink", "verdict"))
    print("-" * 60)
    for lab in EDITORS:
        if not os.path.exists(os.path.join(wdir, lab + "-1.png")):
            print("%-12s   (Word refused this file)" % lab)
            rows[lab] = {"refused": True}
            continue
        op = pages(wdir, lab)
        total = 0
        maxdiff = 0
        per = []
        for i, rp in enumerate(ref_pages):
            if i >= len(op):
                total += 10 ** 7
                per.append(None)
                continue
            r = diff(rp, op[i])
            if r.get("size_mismatch"):
                total += 10 ** 7
                per.append(r)
                continue
            total += r["diff_px"]
            maxdiff = max(maxdiff, r["diff_px"])
            per.append(r["diff_px"])
        npages = len(op)
        # verdict thresholds, relative to the corpus's own ink
        cin = sum(ink(p) for p in ref_pages)
        pct = (total / cin * 100) if cin else 0
        if pct < 0.5:
            verdict = "pixel-identical"
        elif pct < 5:
            verdict = "very close"
        elif pct < 25:
            verdict = "close"
        else:
            verdict = "different"
        rows[lab] = {"pages": npages, "diff_px": total, "ink": sum(ink(p) for p in op),
                     "corpus_ink": cin, "pct_of_ink": round(pct, 2),
                     "verdict": verdict, "per_page": per}
        print("%-12s %6d %10d %10d   %s (%.2f%% of corpus ink)" % (
            lab, npages, total, sum(ink(p) for p in op), verdict, pct))

    with open(os.path.join(rend, "word_render_compare.json"), "w") as f:
        json.dump(rows, f, indent=1)
    print("\nwrote %s" % os.path.join(rend, "word_render_compare.json"))


if __name__ == "__main__":
    main()
