#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=11"]
# ///
"""
Compose the labelled comparison figures used in the Rendering report.

Each figure is a grid of rasterised pages with a caption bar under each panel.
Panels are cropped to the region of interest so the grid is WIDER than it is
tall - a grid of whole portrait pages is nearly square and cannot fit a
landscape page without overflowing it.

Each figure is written with a pHYs resolution so that pandoc lays it out at
the intended size: pandoc takes the image's pixel width divided by its stored
DPI as the print width, and keeps the aspect ratio.

usage: python3 build/strips.py <render-dir>
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixels  # noqa: E402  (build/pixels.py: the release resolution)

BASE = "/Users/arthrod/temp/T/editors_trial"
LABEL_H = 24
GAP = 10
BG = (255, 255, 255)
BAR = (236, 236, 236)
INK = (20, 20, 20)

# the target print width of every figure, in inches (the page is 10in wide)
FULL_W = 5.3        # a whole portrait page, printed at 5.3in -> 6.9in tall
FIG_W = 9.6         # a comparison grid


def find(d, label, page):
    p = os.path.join(d, "%s-%d.png" % (label, page))
    return p if os.path.exists(p) else None


def panel(path, caption, width, crop=None):
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    scale = width / im.width
    im = im.resize((width, max(1, int(im.height * scale))), Image.LANCZOS)
    out = Image.new("RGB", (width, im.height + LABEL_H), BG)
    out.paste(im, (0, LABEL_H))
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, width - 1, LABEL_H - 1], fill=BAR)
    d.text((6, LABEL_H // 2 - 5), caption, fill=INK)
    return out


def grid(panels, out_path, cols=1, target_w_in=FIG_W):
    if not panels:
        return None
    pw = max(p.width for p in panels)
    ph = max(p.height for p in panels)
    rows = (len(panels) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * pw + (cols - 1) * GAP,
                               rows * ph + (rows - 1) * GAP), BG)
    for i, p in enumerate(panels):
        r, c = divmod(i, cols)
        canvas.paste(p, (c * (pw + GAP), r * (ph + GAP)))
    dpi = canvas.width / target_w_in
    canvas.save(out_path, dpi=(dpi, dpi))
    h_in = canvas.height / dpi
    print("wrote %-46s %4dx%-4d -> %.2f x %.2f in" % (
        os.path.basename(out_path), canvas.width, canvas.height, target_w_in, h_in))
    return canvas


def main():
    rend = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render")
    w = os.path.join(rend, "png_word")
    lo = os.path.join(rend, "lo_png")
    ab = os.path.join(BASE, "out", "ab", "png")
    fig = os.path.join(rend, "figures")
    os.makedirs(fig, exist_ok=True)

    PW = 400
    # crops in inches on the page, so they hold at any resolution (build/pixels.py)
    def box(*inches):
        return tuple(round(i * pixels.DPI) for i in inches)
    # the drawing region of page 3 (the picture + the chart)
    CROP3 = box(0.55, 2.73, 5.64, 7.36)
    # the top of page 1 (the heading, the header, the first table)
    CROP1 = box(0.55, 1.36, 5.64, 5.64)
    # the middle of page 4 (the text box and the math)
    CROP4 = box(0.55, 4.36, 5.64, 7.82)

    # 1. the corpus as WORD renders it - one full page at a time
    for i in range(1, 7):
        p = find(w, "corpus", i)
        if not p:
            continue
        g = grid([panel(p, "Word's rendering of the corpus - page %d" % i, 460)],
                 os.path.join(fig, "fig1_corpus_p%d.png" % i), cols=1,
                 target_w_in=FULL_W)

    # 2. the drawing page across every editor Word could open
    ps = []
    for lab, cap in [("corpus", "corpus (Word's own)"),
                     ("superdoc", "SuperDoc"), ("genoffice", "GenOffice"),
                     ("eigenpal", "eigenpal"), ("wordcraft", "WordCraft"),
                     ("libreoffice", "LibreOffice baseline"),
                     ("canvas", "canvas-editor"), ("docs.plus", "docs.plus"),
                     ("plate", "Plate.js")]:
        p = find(w, lab, 3)
        if p:
            ps.append(panel(p, cap, PW, crop=CROP3))
    grid(ps, os.path.join(fig, "fig2_page3_drawings.png"), cols=3)

    # 3. page 1 of the collapsed editors
    ps = []
    for lab, cap in [("corpus", "corpus (Word's own)"), ("superdoc", "SuperDoc"),
                     ("wordcraft", "WordCraft"), ("canvas", "canvas-editor"),
                     ("docs.plus", "docs.plus"), ("plate", "Plate.js"),
                     ("docxodus", "Docxodus")]:
        p = find(w, lab, 1)
        if p:
            ps.append(panel(p, cap, PW, crop=CROP1))
    grid(ps, os.path.join(fig, "fig3_page1_word.png"), cols=3)

    # 4. the A/B evidence
    ps = [panel(find(w, "corpus", 3), "corpus page 3 (Word)", PW, crop=CROP3)]
    for v, cap, pg in [("no_chart", "chart removed", 3),
                       ("no_dgm", "SmartArt removed", 3),
                       ("no_pic", "picture removed", 3),
                       ("no_wps", "mc:Choice text box removed", 4),
                       ("no_ole", "OLE object removed", 4)]:
        p = find(ab, v, pg)
        if p:
            ps.append(panel(p, cap + " - page %d" % pg, PW,
                            crop=CROP3 if pg == 3 else CROP4))
    grid(ps, os.path.join(fig, "fig4_ab_variants.png"), cols=3)

    # 5. the dangling chart, in LibreOffice's rendering
    ps = []
    for lab, cap in [("corpus", "corpus (LibreOffice)"),
                     ("office-open", "office-open"),
                     ("docen", "Docen"),
                     ("superdoc", "SuperDoc")]:
        p = find(lo, lab, 3)
        if p:
            ps.append(panel(p, cap, PW, crop=CROP3))
    grid(ps, os.path.join(fig, "fig5_dangling_chart.png"), cols=4)

    # 6. the four editors Word refuses, rendered by LibreOffice
    ps = []
    for lab, cap in [("corpus", "corpus (LibreOffice)"), ("folio", "Folio"),
                     ("office-open", "office-open"), ("docen", "Docen"),
                     ("fidus", "Fidus Writer")]:
        p = find(lo, lab, 3) or find(lo, lab, 1)
        if p:
            ps.append(panel(p, cap, PW, crop=CROP3))
    grid(ps, os.path.join(fig, "fig6_word_refused.png"), cols=5)


if __name__ == "__main__":
    main()
