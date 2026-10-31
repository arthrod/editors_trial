#!/usr/bin/env python3
"""
Build a pandoc reference.docx for this report:
  - landscape Letter with narrow-ish margins, because the report carries a
    10-column measured matrix that is unreadable in portrait;
  - a Title style and a Table style that survive round-tripping in Word.

usage: make_reference_doc.py <out.docx>
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

OUT = sys.argv[1]
TMP = tempfile.mkdtemp()
REF = os.path.join(TMP, "reference.docx")

# pandoc's default reference document
with open(REF, "wb") as f:
    subprocess.run(["pandoc", "--print-default-data-file=reference.docx"],
                   stdout=f, check=True)

z = zipfile.ZipFile(REF)
parts = {n: z.read(n) for n in z.namelist()}

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

doc = parts["word/document.xml"].decode("utf-8")

# --- page setup: Letter landscape, 0.5in margins ----------------------------
sect = re.search(r"<w:sectPr\b.*?</w:sectPr>", doc, re.S)
if sect:
    s = sect.group(0)
    # CT_SectPr order: hdr/ftr refs, footnotePr, endnotePr, type, pgSz, pgMar, ...
    pg = ('<w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>'
          '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" '
          'w:header="360" w:footer="360" w:gutter="0"/>')
    s = re.sub(r"<w:pgSz\b[^>]*/>", "", s)
    s = re.sub(r"<w:pgMar\b[^>]*/>", "", s)
    if "<w:pgSz" in s:
        s = re.sub(r"<w:pgSz\b[^>]*/>", pg.split("><w:pgMar")[0] + "/>", s)
        s = re.sub(r"<w:pgMar\b[^>]*/>", '<w:pgMar w:top="720" w:right="720" '
                   'w:bottom="720" w:left="720" w:header="360" w:footer="360" '
                   'w:gutter="0"/>', s)
    else:
        # insert after the last of footnotePr/endnotePr/type, else at the start
        anchor = None
        for tagname in ("footnotePr", "endnotePr", "type"):
            m2 = re.search(r"<w:%s\b.*?</w:%s>" % (tagname, tagname), s, re.S)
            if m2:
                anchor = m2.end()
        if anchor is None:
            m2 = re.search(r"<w:type\b[^>]*/>", s)
            anchor = m2.end() if m2 else 0
        s = s[:anchor] + pg + s[anchor:]
    doc = doc[:sect.start()] + s + doc[sect.end():]
    parts["word/document.xml"] = doc.encode("utf-8")

# --- styles: readable sizes, and a compact Table style ----------------------
st = parts["word/styles.xml"].decode("utf-8")


STYLE_RE = re.compile(r"<w:style\b[^>]*>.*?</w:style>", re.S)


def set_style_size(xml, style_id, half_points, bold=None):
    """Set w:sz / w:szCs (and optionally w:b) inside one style's rPr.

    Uses re.sub over the whole document so everything outside the <w:style>
    blocks (the XML declaration, the <w:styles> root) is preserved verbatim.
    """
    found = [False]

    def repl(m):
        block = m.group(0)
        if ('w:styleId="%s"' % style_id) not in block:
            return block
        found[0] = True
        if "<w:rPr>" in block:
            body = re.sub(r'<w:sz w:val="\d+"\s*/>',
                          '<w:sz w:val="%d"/>' % half_points, block)
            body = re.sub(r'<w:szCs w:val="\d+"\s*/>',
                          '<w:szCs w:val="%d"/>' % half_points, body)
            if bold is True and "<w:b/>" not in body:
                body = body.replace("<w:rPr>", "<w:rPr><w:b/>", 1)
            elif bold is False and "<w:b/>" in body:
                body = body.replace("<w:b/>", "", 1)
        else:
            extra = "<w:rPr>"
            if bold:
                extra += "<w:b/>"
            extra += ('<w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>'
                      % (half_points, half_points))
            body = block.replace("</w:style>", extra + "</w:style>")
        return body

    return STYLE_RE.sub(repl, xml), found[0]


def apply(xml, sid, hp, bold=None):
    xml, ok = set_style_size(xml, sid, hp, bold)
    print("   style %-14s %s" % (sid, "ok" if ok else "NOT FOUND"))
    return xml


print("styles:")
for sid, hp, b in [("BodyText", 18, None), ("Compact", 16, None),
                   ("TableCaption", 16, None), ("ImageCaption", 16, None),
                   ("FirstParagraph", 18, None), ("Body", 18, None),
                   ("Heading1", 30, True), ("Heading2", 24, True),
                   ("Heading3", 21, True), ("Title", 44, True)]:
    st = apply(st, sid, hp, b)
parts["word/styles.xml"] = st.encode("utf-8")

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as o:
    for n, data in parts.items():
        o.writestr(n, data)
shutil.rmtree(TMP, ignore_errors=True)
print("wrote reference doc:", OUT, os.path.getsize(OUT), "bytes")
