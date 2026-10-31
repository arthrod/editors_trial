#!/usr/bin/env python3
"""
Build the side-by-side figures for the rendering report.

Each figure is a two-panel image:

    left   the page of WORD's own rendering that shows the same content
    right  the SCREENSHOT of the editor's running UI

with a thin gutter and a caption strip above each panel, so a reader can see
the two renderings of the same document side by side without having to hold
two pictures in their head.

usage: python3 build/ui_figures.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

BASE = "/Users/arthrod/temp/T/editors_trial"
UI = os.path.join(BASE, "out/ui")
WORD = os.path.join(BASE, "out/render/png_word")
FIGS = os.path.join(BASE, "out/ui/figures")
SMART = os.path.join(BASE, "out/smartart")

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def font(size):
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                pass
    return ImageFont.load_default()


def fit_width(im, w):
    if im.width <= w:
        return im
    h = max(1, int(round(im.height * w / im.width)))
    return im.resize((w, h), Image.LANCZOS)


def pair(out_name, left_path, left_label, right_path, right_label,
         panel_w=760, strip=34, gutter=18):
    if not (os.path.exists(left_path) and os.path.exists(right_path)):
        print("skip %s (missing %s)" % (out_name, os.path.basename(left_path)
                                        if not os.path.exists(left_path)
                                        else os.path.basename(right_path)))
        return None
    L = fit_width(Image.open(left_path).convert("RGB"), panel_w)
    R = fit_width(Image.open(right_path).convert("RGB"), panel_w)
    h = max(L.height, R.height)
    W = panel_w * 2 + gutter
    H = h + strip
    canvas = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W - 1, H - 1], outline=(190, 190, 190), width=2)
    d.line([(panel_w + gutter // 2, 0), (panel_w + gutter // 2, H)], fill=(190, 190, 190), width=2)
    f = font(22)
    d.text((12, 7), left_label, fill=(20, 20, 20), font=f)
    d.text((panel_w + gutter + 12, 7), right_label, fill=(20, 20, 20), font=f)
    canvas.paste(L, (0, strip))
    canvas.paste(R, (panel_w + gutter, strip))
    os.makedirs(FIGS, exist_ok=True)
    out = os.path.join(FIGS, out_name)
    canvas.save(out)
    print("wrote %s (%dx%d)" % (os.path.basename(out), W, H))
    return out


# slug -> (label, page-1 shot, page-3 shot)
EDITORS = [
    ("superdoc", "SuperDoc"),
    ("docen", "Docen"),
    ("genoffice", "GenOffice"),
    ("officeopen", "Office-Open"),
    ("canvas", "Canvas-Editor"),
    ("eigenpal", "eigenpal"),
    ("plate", "Plate.js"),
    ("docxodus", "Docxodus"),
    ("docsplus", "docs.plus"),
    ("folio", "Folio"),
    ("fidus", "Fidus Writer"),
    ("wordcraft", "WordCraft"),
    ("libreoffice", "LibreOffice"),
]


def smartart_figure():
    """corpus band vs the two controls, side by side."""
    crops = os.path.join(SMART, "crop")
    a = os.path.join(crops, "band_corpus.png")
    b = os.path.join(crops, "band_dgm_pic_checker.png")
    c = os.path.join(crops, "band_dgm_pic_border.png")
    if not (os.path.exists(a) and os.path.exists(b) and os.path.exists(c)):
        print("skip smartart figure (crops missing)")
        return
    ims = [Image.open(p).convert("RGB") for p in (a, b, c)]
    labels = [
        "CORPUS, as Word renders it",
        "POSITIVE CONTROL (checkerboard)",
        "BORDER CONTROL (outlined box)",
    ]
    w = max(i.width for i in ims)
    h = max(i.height for i in ims)
    strip = 30
    canvas = Image.new("RGB", (w * 3 + 24, h + strip + 8), "white")
    d = ImageDraw.Draw(canvas)
    f = font(15)
    for k, (im, lab) in enumerate(zip(ims, labels)):
        x = k * (w + 12)
        d.text((x + 4, 6), lab, fill=(20, 20, 20), font=f)
        canvas.paste(im, (x, strip))
        d.rectangle([x, strip, x + im.width - 1, strip + im.height - 1],
                    outline=(160, 160, 160), width=1)
    out = os.path.join(FIGS, "fig_smartart_band.png")
    os.makedirs(FIGS, exist_ok=True)
    canvas.save(out)
    print("wrote %s (%dx%d)" % (os.path.basename(out), canvas.width, canvas.height))


def main():
    smartart_figure()
    # Docxodus is not a browser-hosted editor: its artefact is the product's
    # own materialized page, produced by its own pagination engine.
    OWN_RENDER = {"docxodus"}

    for slug, label in EDITORS:
        right_label = ("%s - the application's own render" % label
                       if slug in OWN_RENDER else "%s - the editor's own UI" % label)
        p1 = os.path.join(UI, slug + ".png")
        p3 = os.path.join(UI, slug + "_p3.png")
        p4 = os.path.join(UI, slug + "_p4.png")
        if os.path.exists(p4):
            pair("fig_ui_%s_p4.png" % slug,
                 os.path.join(WORD, "corpus-4.png"),
                 "Microsoft Word - page 4 of 6",
                 p4, right_label)
        if os.path.exists(p3):
            pair("fig_ui_%s_p3.png" % slug,
                 os.path.join(WORD, "corpus-3.png"),
                 "Microsoft Word - page 3 of 6",
                 p3, right_label)
        if os.path.exists(p1):
            pair("fig_ui_%s_p1.png" % slug,
                 os.path.join(WORD, "corpus-1.png"),
                 "Microsoft Word - page 1 of 6",
                 p1, right_label)

    # WordCraft and LibreOffice are native applications: their "screenshot"
    # is the application's own rendered page, produced by its own renderer.
    for slug, label, base, page3 in (
            ("wordcraft", "WordCraft", os.path.join(UI, "wordcraft"), "page3.png"),
            ("libreoffice", "LibreOffice", os.path.join(UI, "libreoffice"), "page-3.png")):
        p3 = os.path.join(base, page3)
        if os.path.exists(p3):
            pair("fig_ui_%s_p3.png" % slug,
                 os.path.join(WORD, "corpus-3.png"),
                 "Microsoft Word - page 3 of 6",
                 p3, "%s - the application's own render" % label)
        p1 = os.path.join(base, "page1.png" if slug == "wordcraft" else "page-1.png")
        if os.path.exists(p1):
            pair("fig_ui_%s_p1.png" % slug,
                 os.path.join(WORD, "corpus-1.png"),
                 "Microsoft Word - page 1 of 6",
                 p1, "%s - the application's own render" % label)


if __name__ == "__main__":
    main()
