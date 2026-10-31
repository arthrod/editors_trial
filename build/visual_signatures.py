#!/usr/bin/env python3
"""
Visual signatures of the drawing constructs, measured on the rasterised page.

The corpus's picture, its mc:Choice text box and its OLE object's preview all
use the SAME image (word/media/image1.png), so they are one colour and cannot
be told apart by colour alone - but they can be COUNTED. The chart's bars use
a different default Office blue, so a chart is separately detectable.

  picture_blue  (31, 119, 180)   the corpus's image, used by 3 constructs
  chart_blue    (68, 114, 196)   the chart's bars

The corpus renders 3 picture-blue squares (the picture, the text box, the OLE
preview) and ~10.6k chart-blue pixels. An editor that drops the picture, the
text box or the OLE object shows one fewer square.

usage: python3 build/visual_signatures.py <render-dir>
"""
import json
import os
import sys

from PIL import Image

PICTURE_BLUE = (31, 119, 180)
CHART_BLUE = (68, 114, 196)


def close(a, b, tol=12):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol and abs(a[2] - b[2]) <= tol


def signature(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    pic = chart = 0
    # a connected-region count for the picture blue, row-band based
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if close(p, PICTURE_BLUE):
                pic += 1
            elif close(p, CHART_BLUE):
                chart += 1
    return {"picture_blue_px": pic, "chart_blue_px": chart}


def squares(path, tol=12):
    """Count connected regions of the picture blue (4-neighbour flood fill)."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    n = 0
    sizes = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if seen[i] or not close(px[x, y], PICTURE_BLUE, tol):
                continue
            n += 1
            size = 0
            stack = [(x, y)]
            seen[i] = 1
            while stack:
                cx, cy = stack.pop()
                size += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny * w + nx
                        if not seen[j] and close(px[nx, ny], PICTURE_BLUE, tol):
                            seen[j] = 1
                            stack.append((nx, ny))
            sizes.append(size)
    return n, sizes


def main():
    rend = sys.argv[1] if len(sys.argv) > 1 else "out/render"
    out = {}
    for side, d, labels in [
            ("word", os.path.join(rend, "png_word"),
             ["corpus", "superdoc", "genoffice", "eigenpal", "wordcraft",
              "canvas", "docs.plus", "plate", "docxodus", "libreoffice"]),
            ("lo", os.path.join(rend, "lo_png"),
             ["corpus", "superdoc", "folio", "genoffice", "eigenpal",
              "office-open", "docen", "wordcraft", "fidus", "canvas",
              "docs.plus", "plate", "docxodus", "libreoffice"])] :
        print("=== %s ===" % side.upper())
        for lab in labels:
            p1 = os.path.join(d, lab + "-1.png")
            if not os.path.exists(p1):
                continue
            tot = {"picture_blue_px": 0, "chart_blue_px": 0}
            sq = 0
            sizes = []
            i = 1
            while os.path.exists(os.path.join(d, "%s-%d.png" % (lab, i))):
                s = signature(os.path.join(d, "%s-%d.png" % (lab, i)))
                for k in tot:
                    tot[k] += s[k]
                n, sz = squares(os.path.join(d, "%s-%d.png" % (lab, i)))
                sq += n
                sizes += sz
                i += 1
            out.setdefault(side, {})[lab] = dict(tot, squares=sq, square_sizes=sizes)
            print("%-14s picture_blue=%-8d chart_blue=%-8d squares=%d  %s" % (
                lab, tot["picture_blue_px"], tot["chart_blue_px"], sq, sizes))
        print()
    with open(os.path.join(rend, "visual_signatures.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
