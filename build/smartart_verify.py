#!/usr/bin/env python3
"""
Verify (or refute) the claim "Word does not draw the corpus's SmartArt at all".

Method
------
The corpus contains one SmartArt: a 5486400 x 3200400 EMU (6.0in x 3.5in)
inline diagram.  At the 110 dpi used for every rasterisation in this study
that band is 660 x 385 px.

Four Word-rendered variants, all with the SAME extent so the layout and the
reflow are identical to the corpus:

  dgm_pic_border   the SmartArt replaced by a PNG: white inside, black border.
                   diff(corpus, dgm_pic_border) locates the band exactly and
                   equals  border_ink + corpus_ink_in_band.
  dgm_pic_checker  the SmartArt replaced by a dense checkerboard.
                   POSITIVE CONTROL: if the method can see ink in the band,
                   this must light the band up.
  dgm_marker       word/diagrams/data1.xml says ZQSMARTARTMARKERQZ instead of
                   "Step one".  If Word renders the diagram from its data,
                   the page changes.
  dgm_cached       the missing cached-drawing part word/diagrams/drawing1.xml
                   (dsp:drawing) is added and wired up through
                   dgm:extLst/dgm:dataModelExt, which is how Word stores a
                   diagram it has already laid out.

usage: python3 build/smartart_verify.py
"""
import json
import os
import sys

from PIL import Image, ImageChops

BASE = "/Users/arthrod/temp/T/editors_trial"
CORPUS_PNG = os.path.join(BASE, "out/render/png_word")
CTRL_PNG = os.path.join(BASE, "out/smartart/png")
OUT = os.path.join(BASE, "out/smartart")

WHITE = 255


def load(p):
    return Image.open(p).convert("RGB")


def ink_count(im, box=None):
    g = im.convert("L")
    if box:
        g = g.crop(box)
    px = g.load()
    w, h = g.size
    n = 0
    for y in range(h):
        for x in range(w):
            if px[x, y] < 245:
                n += 1
    return n


def diff(a, b, thr=8):
    if a.size != b.size:
        return {"size_mismatch": True, "size_a": a.size, "size_b": b.size}
    d = ImageChops.difference(a, b)
    g = d.convert("L").point(lambda v: 255 if v > thr else 0)
    return {
        "diff_px": g.histogram()[255],
        "diff_bbox": d.getbbox(),
        "size": a.size,
    }


def main():
    result = {}

    corpus_pages = {}
    for i in range(1, 8):
        p = os.path.join(CORPUS_PNG, "corpus-%d.png" % i)
        if os.path.exists(p):
            corpus_pages[i] = load(p)

    # ---------- 1. locate the band with dgm_pic_border --------------------
    # The band as RENDERED is not 660x385 px: the diagram's 6.0in nominal
    # extent is wider than the 4.49in text column, so Word scales the inline
    # graphic down to fit (uniform scale ~0.748 -> 494 x 289 px).  The band
    # is therefore found from the picture's own footprint, not assumed.
    band = None
    per_page = {}
    best = (0, None)
    for i, cim in corpus_pages.items():
        bp = os.path.join(CTRL_PNG, "dgm_pic_border-%d.png" % i)
        if not os.path.exists(bp):
            continue
        bim = load(bp)
        r = diff(cim, bim)
        per_page[i] = r
        if r.get("diff_px", 0) > best[0]:
            best = (r["diff_px"], i)
    if best[1] is not None and best[0] > 0:
        i = best[1]
        x0, y0, x1, y1 = per_page[i]["diff_bbox"]
        band = {"page": i, "bbox": [x0, y0, x1, y1],
                "w": x1 - x0, "h": y1 - y0}
    result["band_locator_pages"] = per_page
    result["band"] = band

    if not band:
        print("BAND NOT LOCATED")
        print(json.dumps(per_page, indent=2))
        return 1

    page = band["page"]
    x0, y0, x1, y1 = band["bbox"]
    result["band_page"] = page

    # ---------- 2. direct ink measurement inside the band -----------------
    cim = corpus_pages[page]
    bim = load(os.path.join(CTRL_PNG, "dgm_pic_border-%d.png" % page))
    band_ink_corpus = ink_count(cim, (x0, y0, x1, y1))
    band_ink_border = ink_count(bim, (x0, y0, x1, y1))
    inner = (x0 + 8, y0 + 8, x1 - 8, y1 - 8)
    inner_ink_corpus = ink_count(cim, inner)
    inner_ink_border = ink_count(bim, inner)
    d = diff(cim, bim)
    result["band_measurement"] = {
        "page": page,
        "bbox": band["bbox"],
        "band_px": (x1 - x0) * (y1 - y0),
        "corpus_ink_in_band": band_ink_corpus,
        "border_variant_ink_in_band": band_ink_border,
        "corpus_ink_in_band_interior": inner_ink_corpus,
        "border_variant_ink_in_band_interior": inner_ink_border,
        "diff_px_corpus_vs_border": d["diff_px"],
        "derived_corpus_ink_outside_border": d["diff_px"] - band_ink_border,
        "expected_nominal_px_at_110dpi": [660, 385],
        "rendered_scale": round((x1 - x0) / 660.0, 4),
    }

    # ---------- 3. positive control: the checker -------------------------
    ctrl = {}
    for i, cim2 in corpus_pages.items():
        for name in ("dgm_pic_checker", "dgm_marker", "dgm_cached"):
            p = os.path.join(CTRL_PNG, "%s-%d.png" % (name, i))
            if not os.path.exists(p):
                continue
            r = diff(cim2, load(p))
            ctrl.setdefault(name, {})["page%d" % i] = {
                "diff_px": r["diff_px"], "diff_bbox": r["diff_bbox"]}
    result["controls"] = ctrl

    # ---------- 4. crops for the report -----------------------------------
    crops = os.path.join(OUT, "crop")
    os.makedirs(crops, exist_ok=True)
    pad = 30
    box = (max(0, x0 - pad), max(0, y0 - pad), min(cim.size[0], x1 + pad),
           min(cim.size[1], y1 + pad))
    for label, im in (("corpus", cim),
                      ("dgm_pic_border", bim),
                      ("dgm_pic_checker", load(os.path.join(CTRL_PNG, "dgm_pic_checker-%d.png" % page))),
                      ("dgm_cached", load(os.path.join(CTRL_PNG, "dgm_cached-%d.png" % page))),
                      ("dgm_marker", load(os.path.join(CTRL_PNG, "dgm_marker-%d.png" % page)))):
        im.crop(box).save(os.path.join(crops, "band_%s.png" % label))
    result["crop_box"] = list(box)

    with open(os.path.join(OUT, "verify.json"), "w") as fh:
        json.dump(result, fh, indent=2)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
