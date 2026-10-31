#!/usr/bin/env python3
"""
Build SmartArt control variants of the corpus.

The report claims "Word does not draw the corpus's SmartArt at all".  A claim
like that needs a POSITIVE CONTROL: the method must be shown to detect ink in
the SmartArt band if ink were there.

Variants produced (all keep the exact 5486400 x 3200400 EMU = 6.0in x 3.5in
extent, so the layout / reflow is byte-identical to the corpus):

  dgm_pic_border   SmartArt replaced by a PNG that is white inside with a black
                    border.  diff(corpus, dgm_pic_border) =
                        border_ink  +  smartart_ink_inside_band
                    so the SmartArt's own ink can be computed exactly.

  dgm_pic_checker  SmartArt replaced by a PNG filled with a dense pattern.
                    This is the POSITIVE CONTROL: if the method is sound, this
                    must light up the band.

  dgm_marker       The corpus is untouched except that word/diagrams/data1.xml
                    now says "ZQSMARTARTMARKERQZ" instead of "Step one".
                    If Word renders the diagram from data1.xml the page must
                    change.  If the page does not change, Word is not drawing
                    this diagram from its data at all.

  dgm_cached       The corpus plus the missing cached-drawing part
                    word/diagrams/drawing1.xml (dsp:drawing) wired up through
                    dgm:extLst / dgm:dataModelExt, which is how Word stores a
                    diagram it has already laid out.  Tests whether the corpus
                    is unrenderable because the cached drawing is missing.

Usage: python3 build/smartart_controls.py <corpus.docx> <outdir>
"""
import os
import re
import shutil
import sys
import zipfile

EMU_W = 5486400
EMU_H = 3200400
IMG_W_PX = 576   # 6.0in at 96dpi
IMG_H_PX = 336   # 3.5in at 96dpi

REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PIC_URI = "http://schemas.openxmlformats.org/drawingml/2006/picture"


def find_smartart_drawing(doc: str):
    """Return (start, end) span of the <w:drawing> element holding dgm:relIds."""
    i = doc.find("dgm:relIds")
    if i < 0:
        raise SystemExit("no dgm:relIds in document.xml")
    start = doc.rfind("<w:drawing>", 0, i)
    end = doc.find("</w:drawing>", i) + len("</w:drawing>")
    return start, end


def picture_drawing(rid: str, name: str) -> str:
    return (
        '<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{EMU_W}" cy="{EMU_H}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="90" name="{name}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic><a:graphicData uri="' + PIC_URI + '">'
        '<pic:pic><pic:nvPicPr>'
        '<pic:cNvPr id="90" name="band.png"/><pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip r:embed="' + rid + '"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{EMU_W}" cy="{EMU_H}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>'
    )


def make_pngs(outdir: str):
    from PIL import Image, ImageDraw
    os.makedirs(outdir, exist_ok=True)

    # border: white interior, 6px black border
    im = Image.new("RGB", (IMG_W_PX, IMG_H_PX), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, IMG_W_PX - 1, IMG_H_PX - 1], outline="black", width=6)
    border = os.path.join(outdir, "band_border.png")
    im.save(border)

    # checker: dense pattern, guaranteed high ink
    im2 = Image.new("RGB", (IMG_W_PX, IMG_H_PX), "white")
    d2 = ImageDraw.Draw(im2)
    for y in range(0, IMG_H_PX, 12):
        for x in range(0, IMG_W_PX, 12):
            if ((x // 12) + (y // 12)) % 2 == 0:
                d2.rectangle([x, y, x + 11, y + 11], fill="black")
    checker = os.path.join(outdir, "band_checker.png")
    im2.save(checker)
    return border, checker


def add_rel(rels: str, rid: str, target: str) -> str:
    if f'Id="{rid}"' in rels:
        raise SystemExit("rel id collision " + rid)
    entry = (f'<Relationship Id="{rid}" '
             f'Type="{REL_NS}/image" Target="{target}"/>')
    return rels.replace("</Relationships>", entry + "</Relationships>")


def rewrite(src_docx: str, out_docx: str, transform=None, extra_files=None,
            extra_rels=None, replace_media=None):
    """Copy a docx, optionally transforming document.xml / rels / adding parts."""
    zin = zipfile.ZipFile(src_docx)
    if os.path.exists(out_docx):
        os.remove(out_docx)
    zout = zipfile.ZipFile(out_docx, "w", zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        data = zin.read(item.filename)
        if transform:
            new = transform(item.filename, data)
            if new is None:
                continue
            data = new
        zout.writestr(item, data)
    for name, payload in (extra_files or {}).items():
        if isinstance(payload, bytes):
            zout.writestr(name, payload)
        else:
            zout.write(payload, name)
    zout.close()
    zin.close()


def main():
    src = sys.argv[1]
    outdir = sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    pngdir = os.path.join(outdir, "png_src")
    border, checker = make_pngs(pngdir)

    # ---------- dgm_pic_border ----------
    def t_border(name, data):
        if name == "word/document.xml":
            s = doc = data.decode("utf-8")
            a, b = find_smartart_drawing(doc)
            doc = doc[:a] + picture_drawing("rIdBandBorder", "Band Border") + doc[b:]
            return doc.encode("utf-8")
        if name == "word/_rels/document.xml.rels":
            return add_rel(data.decode("utf-8"), "rIdBandBorder",
                           "media/band_border.png").encode("utf-8")
        return data

    rewrite(src, os.path.join(outdir, "dgm_pic_border.docx"), t_border,
            extra_files={"word/media/band_border.png": border})

    # ---------- dgm_pic_checker ----------
    def t_checker(name, data):
        if name == "word/document.xml":
            doc = data.decode("utf-8")
            a, b = find_smartart_drawing(doc)
            doc = doc[:a] + picture_drawing("rIdBandChecker", "Band Checker") + doc[b:]
            return doc.encode("utf-8")
        if name == "word/_rels/document.xml.rels":
            return add_rel(data.decode("utf-8"), "rIdBandChecker",
                           "media/band_checker.png").encode("utf-8")
        return data

    rewrite(src, os.path.join(outdir, "dgm_pic_checker.docx"), t_checker,
            extra_files={"word/media/band_checker.png": checker})

    # ---------- dgm_marker ----------
    def t_marker(name, data):
        if name == "word/diagrams/data1.xml":
            doc = data.decode("utf-8")
            doc = doc.replace("Step one", "ZQSMARTARTMARKERQZ")
            doc = doc.replace("Step two", "ZQSMARTARTMARKER2QZ")
            return doc.encode("utf-8")
        return data

    rewrite(src, os.path.join(outdir, "dgm_marker.docx"), t_marker)

    # ---------- dgm_cached ----------
    # Word stores a diagram it has laid out as a cached dsp:drawing part,
    # referenced from data1.xml through dgm:extLst/dgm:dataModelExt.
    cached = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<dsp:drawing xmlns:dsp="http://schemas.microsoft.com/office/drawing/2008/diagram" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><dsp:spTree><dsp:nvGrpSpPr><dsp:cNvPr id="0" name=""/><dsp:cNvGrpSpPr/></dsp:nvGrpSpPr><dsp:grpSpPr/><dsp:sp modelId="{11111111-1111-1111-1111-111111111111}"><dsp:nvSpPr><dsp:cNvPr id="0" name=""/><dsp:cNvSpPr/></dsp:nvSpPr><dsp:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="5486400" cy="3200400"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:ln w="12700"><a:solidFill><a:srgbClr val="000000"/></a:solidFill></a:ln></dsp:spPr><dsp:style><a:lnRef idx="0"><a:scrgbClr r="0" g="0" b="0"/></a:lnRef><a:fillRef idx="0"><a:scrgbClr r="0" g="0" b="0"/></a:fillRef><a:effectRef idx="0"><a:scrgbClr r="0" g="0" b="0"/></a:effectRef><a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></dsp:style><dsp:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="1800"/><a:t>CACHEDDGM</a:t></a:r></a:p></dsp:txBody><dsp:txXfrm><a:off x="0" y="0"/><a:ext cx="5486400" cy="3200400"/></dsp:txXfrm></dsp:sp></dsp:spTree></dsp:drawing>'''

    def t_cached(name, data):
        if name == "word/diagrams/data1.xml":
            doc = data.decode("utf-8")
            ext = ('<dgm:extLst><a:ext uri="http://schemas.microsoft.com/office/drawing/2008/diagram">'
                   '<dsp:dataModelExt xmlns:dsp="http://schemas.microsoft.com/office/drawing/2008/diagram" '
                   'relId="rIdDgmDrawing" minVer="12.0"/></a:ext></dgm:extLst>')
            if "</dgm:dataModel>" in doc:
                doc = doc.replace("</dgm:dataModel>", ext + "</dgm:dataModel>")
            else:
                # append inside the root element
                i = doc.rfind("</")
                doc = doc[:i] + ext + doc[i:]
            return doc.encode("utf-8")
        if name == "word/diagrams/_rels/data1.xml.rels":
            return add_rel(data.decode("utf-8"), "rIdDgmDrawing",
                           "drawing1.xml").encode("utf-8")
        if name == "[Content_Types].xml":
            ct = data.decode("utf-8")
            ov = ('<Override PartName="/word/diagrams/drawing1.xml" '
                  'ContentType="application/vnd.ms-office.drawingml.diagramDrawing+xml"/>')
            if "diagramDrawing+xml" not in ct:
                ct = ct.replace("</Types>", ov + "</Types>")
            return ct.encode("utf-8")
        return data

    # The cached-drawing relationship belongs to data1.xml's OWN rels part
    # (word/diagrams/_rels/data1.xml.rels), not to the document's.
    data1_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                  '</Relationships>')

    rewrite(src, os.path.join(outdir, "dgm_cached.docx"), t_cached,
            extra_files={"word/diagrams/drawing1.xml": cached.encode("utf-8"),
                         "word/diagrams/_rels/data1.xml.rels": data1_rels.encode("utf-8")})

    for f in sorted(os.listdir(outdir)):
        p = os.path.join(outdir, f)
        if os.path.isfile(p):
            print("%-24s %8d bytes" % (f, os.path.getsize(p)))


if __name__ == "__main__":
    main()
