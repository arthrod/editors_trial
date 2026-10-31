#!/usr/bin/env python3
"""
Rebuild the deliberately broken corpus: the current, Word-clean corpus with
every defect class re-introduced.

Used to answer a question the first report could not: when an editor is handed
a document that Word refuses, does the editor REPAIR it, preserve the damage,
or emit something worse?

The twelve defects are the ones the first report measured (see its "Word
Compatibility of the Corpus" section):

  1  w:documentProtection after w:defaultTabStop/w:evenAndOddHeaders (CT_Settings)
  2  w:tcW after w:gridSpan/w:vMerge in every w:tcPr               (CT_TcPr)
  3  w:cantSplit after w:tblHeader in w:trPr                       (CT_TrPr)
  4  w:spacing after w:jc inside w:pPrChange/w:pPr                (CT_PPrBase)
  5  w:pgNumType after w:cols in the landscape w:sectPr            (CT_SectPr)
  6  w16cid:durableId with ten hex digits (ST_LongHexNumber = 4 bytes)
  7  dgm:style as a direct child of dgm:styleDef
  8  mc:Fallback nesting a w:r inside the outer w:r
  9  the OLE object pointing at 64 bytes of filler
 10  w:delText inside w:moveFrom (belongs to w:del only)
 11  m:oMathPara as a direct child of w:body
 12  w:dirty="true" on a w:fldChar

usage: python3 build/make_broken_fixture.py
"""
import os
import re
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")
DST = os.path.join(BASE, "fixture", "complex_broken.docx")

with zipfile.ZipFile(SRC) as z:
    PARTS = {n: z.read(n) for n in z.namelist()}

applied = []


def note(n, why):
    applied.append((n, why))


doc = PARTS["word/document.xml"].decode("utf-8")

# 12 - w:dirty="true" on the field's begin fldChar
doc, k = re.subn(r'<w:fldChar w:fldCharType="begin" w:dirty="false"/>',
                 '<w:fldChar w:fldCharType="begin" w:dirty="true"/>', doc)
assert k == 1, "dirty flag"
note(12, 'w:dirty="true" on the TOC begin fldChar')

# 10 - w:delText inside w:moveFrom
doc, k = re.subn(r'(<w:moveFrom\b[^>]*><w:r><w:t[^>]*>)moved away(</w:t></w:r></w:moveFrom>)',
                 r'\1moved away\2', doc)
assert k == 1, "moveFrom"
doc = doc.replace('<w:moveFrom w:id="202" w:author="Fixture Author" '
                  'w:date="2026-01-15T09:30:00Z"><w:r><w:t xml:space="preserve">moved away</w:t></w:r></w:moveFrom>',
                  '<w:moveFrom w:id="202" w:author="Fixture Author" '
                  'w:date="2026-01-15T09:30:00Z"><w:r>'
                  '<w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>')
assert "<w:delText xml:space=\"preserve\">moved away</w:delText>" in doc, "moveFrom delText"
note(10, "w:delText inside w:moveFrom")

# 11 - m:oMathPara at block level
doc, k = re.subn(r'<w:p><m:oMathPara>(.*?)</m:oMathPara></w:p>', r'<m:oMathPara>\1</m:oMathPara>',
                 doc, flags=re.S)
assert k == 1, "math"
note(11, "m:oMathPara as a direct child of w:body")

# 4 - w:spacing after w:jc inside w:pPrChange/w:pPr
doc, k = re.subn(r'(<w:pPrChange\b[^>]*><w:pPr>)<w:spacing([^/]*)/><w:jc([^/]*)/>',
                 r'\1<w:jc\3/><w:spacing\2/>', doc)
assert k == 1, "pPrChange"
note(4, "w:spacing after w:jc inside w:pPrChange/w:pPr")

# 8 - mc:Fallback nesting a w:r inside the outer w:r
doc = doc.replace(
    "<mc:Fallback><w:pict>",
    "<mc:Fallback><w:r><w:pict>")
doc = doc.replace(
    "</w:pict></mc:Fallback>",
    "</w:pict></w:r></mc:Fallback>")
assert "<mc:Fallback><w:r><w:pict>" in doc, "fallback"
note(8, "mc:Fallback nesting a w:r inside the outer w:r")

# 5 - w:pgNumType after w:cols in the landscape sectPr
def swap_pgnum(m):
    blk = m.group(0)
    pm = re.search(r"<w:pgNumType[^>]*/>", blk)
    if not pm:
        return blk
    blk2 = blk.replace(pm.group(0), "")
    cm = re.search(r"<w:cols[^>]*/>", blk2)
    return blk2[:cm.end()] + pm.group(0) + blk2[cm.end():]


doc, k = re.subn(r"<w:sectPr\b.*?</w:sectPr>", swap_pgnum, doc, flags=re.S)
note(5, "w:pgNumType after w:cols in the landscape sectPr")

PARTS["word/document.xml"] = doc.encode("utf-8")

# 2 - w:tcW after w:gridSpan/w:vMerge in every w:tcPr
def swap_tcw(m):
    blk = m.group(0)
    w = re.search(r"<w:tcW[^>]*/>", blk)
    if not w:
        return blk
    rest = blk.replace(w.group(0), "")
    anchors = list(re.finditer(r"<w:(?:gridSpan|vMerge)[^>]*/>", rest))
    if not anchors:
        return blk
    at = anchors[-1].end()
    return rest[:at] + w.group(0) + rest[at:]


doc = PARTS["word/document.xml"].decode("utf-8")
doc, k = re.subn(r"<w:tcPr>.*?</w:tcPr>", swap_tcw, doc, flags=re.S)
assert k > 0, "tcPr"
PARTS["word/document.xml"] = doc.encode("utf-8")
note(2, "w:tcW after w:gridSpan/w:vMerge in every w:tcPr")

# 3 - w:cantSplit after w:tblHeader in w:trPr
def swap_cant(m):
    blk = m.group(0)
    cs = re.search(r"<w:cantSplit[^>]*/>", blk)
    if not cs:
        return blk
    rest = blk.replace(cs.group(0), "")
    th = re.search(r"<w:tblHeader[^>]*/>", rest)
    if not th:
        return blk
    at = th.end()
    return rest[:at] + cs.group(0) + rest[at:]


doc = PARTS["word/document.xml"].decode("utf-8")
doc, k = re.subn(r"<w:trPr>.*?</w:trPr>", swap_cant, doc, flags=re.S)
assert k > 0, "trPr"
PARTS["word/document.xml"] = doc.encode("utf-8")
note(3, "w:cantSplit after w:tblHeader in w:trPr")

# 6 - w16cid:durableId with ten hex digits
for p in list(PARTS):
    if not p.endswith(".xml"):
        continue
    d = PARTS[p].decode("utf-8")
    if 'w16cid:durableId="12345678"' in d:
        PARTS[p] = d.replace('w16cid:durableId="12345678"',
                             'w16cid:durableId="1234567890"').encode("utf-8")
        note(6, "w16cid:durableId with ten hex digits")

# 7 - dgm:style as a direct child of dgm:styleDef
d = PARTS["word/diagrams/quickStyle1.xml"].decode("utf-8")
m = re.search(r"<dgm:style>(.*?)</dgm:style>", d, re.S)
if m:
    style = m.group(0)
    d2 = d.replace(style, "")
    d2 = d2.replace("</dgm:styleDef>", style + "</dgm:styleDef>")
    PARTS["word/diagrams/quickStyle1.xml"] = d2.encode("utf-8")
    note(7, "dgm:style as a direct child of dgm:styleDef")

# 9 - the OLE object pointing at 64 bytes of filler
PARTS["word/embeddings/embedded1.docx"] = b"\x00" * 64
note(9, "OLE object pointing at 64 bytes of filler")

# 1 - w:documentProtection after w:defaultTabStop/w:evenAndOddHeaders
s = PARTS["word/settings.xml"].decode("utf-8")
m = re.search(r"<w:documentProtection[^>]*/>", s)
if m:
    dp = m.group(0)
    s2 = s.replace(dp, "")
    anchor = "<w:evenAndOddHeaders/>"
    s2 = s2.replace(anchor, anchor + dp)
    PARTS["word/settings.xml"] = s2.encode("utf-8")
    note(1, "w:documentProtection after w:evenAndOddHeaders")

with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as o:
    for n, data in PARTS.items():
        o.writestr(n, data)

print("wrote %s (%d bytes)" % (DST, os.path.getsize(DST)))
for n, why in sorted(applied):
    print("   defect %2d  %s" % (n, why))
missing = set(range(1, 13)) - {n for n, _ in applied}
if missing:
    print("   NOT APPLIED: %s" % sorted(missing))
