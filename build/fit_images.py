#!/usr/bin/env python3
"""
Fit every image in a generated .docx to the page.

pandoc sizes an image from the PNG's own pixel size and DPI metadata.  A
browser screenshot is 1440x1400 px with no useful DPI, so pandoc would place
it at 15in wide on a 10in content area and Word would either shrink it or
push it onto a page of its own.

This pass walks the document, finds every inline drawing, and - if the extent
is wider than the section's content width - scales cx and cy by the same
factor, so the aspect ratio is preserved.  It also fixes the matching
<a:ext> inside <a:xfrm>, which Word otherwise ignores.

usage: python3 build/fit_images.py <file.docx> [...]
"""
import os
import re
import shutil
import sys
import zipfile

EMU_PER_INCH = 914400


def content_width_twips(xml):
    m = re.search(r'<w:pgSz[^>]*w:w="(\d+)"', xml)
    pw = int(m.group(1)) if m else 12240
    m = re.search(r'<w:pgMar[^>]*w:left="(\d+)"[^>]*w:right="(\d+)"', xml)
    if m:
        left, right = int(m.group(1)), int(m.group(2))
    else:
        m2 = re.search(r'<w:pgMar[^>]*w:right="(\d+)"[^:]*w:left="(\d+)"', xml)
        left, right = (int(m2.group(2)), int(m2.group(1))) if m2 else (1440, 1440)
    return pw - left - right


def fit(xml, max_emu):
    """Scale down every inline drawing whose cx exceeds max_emu."""
    changed = 0

    def repl(m):
        nonlocal changed
        whole = m.group(0)
        cx = int(m.group(1))
        cy = int(m.group(2))
        if cx <= max_emu:
            return whole
        f = max_emu / cx
        ncx = max_emu
        ncy = max(1, int(round(cy * f)))
        changed += 1
        return whole.replace('cx="%d" cy="%d"' % (cx, cy),
                             'cx="%d" cy="%d"' % (ncx, ncy), 1)

    # <wp:extent cx="..." cy="..."/>
    xml = re.sub(r'<wp:extent cx="(\d+)" cy="(\d+)"\s*/>', repl, xml)
    # <a:ext cx="..." cy="..."/> inside the drawing's xfrm
    def repl_x(m):
        nonlocal changed
        cx = int(m.group(1)); cy = int(m.group(2))
        if cx <= max_emu:
            return m.group(0)
        f = max_emu / cx
        return '<a:ext cx="%d" cy="%d"/>' % (max_emu, max(1, int(round(cy * f))))

    xml = re.sub(r'<a:ext cx="(\d+)" cy="(\d+)"\s*/>', repl_x, xml)
    return xml, changed


def main(paths):
    for path in paths:
        tmp = path + ".tmp"
        zin = zipfile.ZipFile(path)
        doc = zin.read("word/document.xml").decode("utf-8")
        width_tw = content_width_twips(doc)
        max_emu = int(width_tw / 1440.0 * EMU_PER_INCH)
        doc, n = fit(doc, max_emu)
        zout = zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED)
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = doc.encode("utf-8")
            zout.writestr(item, data)
        zout.close()
        zin.close()
        shutil.move(tmp, path)
        print("%s: content %.2fin, %d image(s) refitted" %
              (os.path.basename(path), width_tw / 1440.0, n))


if __name__ == "__main__":
    main(sys.argv[1:])
