#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=11"]
# ///
"""
Pixel-level page comparison between two rasterised PDFs' pages.

This is the rendering measurement that does not depend on the PDF text layer.
Word's PDF export contains runs that are drawn as vector outlines (a w14 text
outline, OMML math, a text box), and those glyphs are invisible to text
extraction while being perfectly visible on the page. So the text layer alone
cannot answer "did Word draw this?" - the pixels can.

Outputs, for each page:
  ink        the count of non-white pixels
  diff       the count of pixels that differ between the two pages
  pct        diff as a percentage of the reference page's ink

usage: python3 build/page_diff.py <ref.png-prefix> <other.png-prefix> <outdir>
       python3 build/page_diff.py --a <a.png> --b <b.png> --out <diff.png>
"""
import os
import sys

from PIL import Image, ImageChops

WHITE = (255, 255, 255)


def ink(im):
    """Count of pixels that are not (near-)white."""
    g = im.convert("L")
    px = g.load()
    w, h = g.size
    n = 0
    for y in range(h):
        for x in range(w):
            if px[x, y] < 245:
                n += 1
    return n


def compare(a_path, b_path):
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if a.size != b.size:
        return {"size_a": a.size, "size_b": b.size, "size_mismatch": True}
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    # count pixels with any channel differing by more than 8
    g = diff.convert("L").point(lambda v: 255 if v > 8 else 0)
    hist = g.histogram()
    ndiff = hist[255]
    return {
        "size_mismatch": False,
        "size": a.size,
        "ink_a": ink(a),
        "ink_b": ink(b),
        "diff_px": ndiff,
        "diff_bbox": bbox,
        "total_px": a.size[0] * a.size[1],
    }


def main():
    if sys.argv[1] == "--a":
        a, b, out = sys.argv[2], sys.argv[4], sys.argv[6]
        r = compare(a, b)
        print(r)
        if not r.get("size_mismatch") and r["diff_px"]:
            im = Image.open(a).convert("RGB")
            im2 = Image.open(b).convert("RGB")
            d = ImageChops.difference(im, im2).convert("L").point(lambda v: 255 if v > 8 else 0)
            canvas = Image.new("RGB", (im.size[0] * 2 + 12, im.size[1]), "white")
            canvas.paste(im, (0, 0))
            canvas.paste(im2, (im.size[0] + 12, 0))
            canvas.save(out)
            print("wrote", out)
        return

    ref_prefix, other_prefix, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(outdir, exist_ok=True)
    ref_pages = sorted(p for p in os.listdir(os.path.dirname(ref_prefix) or ".")
                       if p.startswith(os.path.basename(ref_prefix) + "-") and p.endswith(".png"))
    for rp in ref_pages:
        op = os.path.join(os.path.dirname(other_prefix), rp.replace(
            os.path.basename(ref_prefix), os.path.basename(other_prefix), 1))
        if not os.path.exists(op):
            continue
        r = compare(os.path.join(os.path.dirname(ref_prefix), rp), op)
        print("%-14s %s" % (rp, r))


if __name__ == "__main__":
    main()
