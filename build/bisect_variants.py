#!/usr/bin/env python3
"""
Bisect the fixture into two halves so Microsoft Word can be asked which one it
rejects:

  A. same package (all parts, rels, content types) but a document.xml reduced
     to plain paragraphs + the final sectPr  -> tests the PACKAGE
  B. same package but the exotic PARTS removed from the zip and from
     document.xml.rels                     -> tests the EXOTIC PARTS
  C. full document.xml, exotic parts kept   -> the control

usage: bisect_variants.py
"""
import os
import re
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")
OUT = os.path.join(BASE, "out", "bisect")
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(SRC)
parts = {n: z.read(n) for n in z.namelist()}
doc = parts["word/document.xml"].decode("utf-8")

EXOTIC = [
    "word/charts/chart1.xml", "word/charts/_rels/chart1.xml.rels",
    "word/charts/style1.xml", "word/charts/colors1.xml",
    "word/diagrams/data1.xml", "word/diagrams/layout1.xml",
    "word/diagrams/quickStyle1.xml", "word/diagrams/colors1.xml",
    "word/embeddings/embedded1.docx",
    "word/embeddings/Microsoft_Excel_Worksheet.xlsx",
    "word/glossary/document.xml",
    "customXml/item1.xml", "customXml/itemProps1.xml",
    "customXml/_rels/item1.xml.rels",
    "word/afchunk.html",
]

# ---------------------------------------------------------------- A: plain body
paras = re.findall(r"<w:p\b.*?</w:p>", doc, re.S)
# drop paragraphs that carry drawings/objects/sdt-ish content
keep = []
for p in paras:
    if ("<w:drawing" in p or "<w:object" in p or "<w:altChunk" in p
            or "<mc:AlternateContent" in p or "<w:sdt" in p):
        continue
    keep.append(p)
sect = re.search(r"<w:sectPr\b[^>]*>.*?</w:sectPr>", doc, re.S)
head = doc[:doc.find("<w:body>") + len("<w:body>")]
tail = "</w:body></w:document>"
plain = head + "".join(keep) + (sect.group(0) if sect else "") + tail

with zipfile.ZipFile(os.path.join(OUT, "A_plain_body.docx"), "w", zipfile.ZIP_DEFLATED) as o:
    for n, data in parts.items():
        o.writestr(n, plain.encode("utf-8") if n == "word/document.xml" else data)
print("A_plain_body.docx  (package intact, body plain)")

# ---------------------------------------------------------------- B: no exotic parts
rels = parts["word/_rels/document.xml.rels"].decode("utf-8")
newrels = rels
for p in EXOTIC:
    base = p.split("/")[-1]
    # drop the relationship whose Target ends with this file
    newrels = re.sub(r'<Relationship\b[^>]*Target="[^"]*%s"[^>]*/>' % re.escape(base), "", newrels)
# also drop drawings/objects/altChunk from the body
b = doc
for marker in ("<w:drawing", "<w:object", "<w:altChunk", "<mc:AlternateContent"):
    while True:
        i = b.find(marker)
        if i < 0:
            break
        rs = max(b.rfind("<w:r>", 0, i), b.rfind("<w:r ", 0, i))
        end = b.find("</w:r>", i)
        if rs < 0 or end < 0:
            b = b[:i] + b[i + 1:]
            continue
        b = b[:rs] + b[end + len("</w:r>"):]

with zipfile.ZipFile(os.path.join(OUT, "B_no_exotic_parts.docx"), "w", zipfile.ZIP_DEFLATED) as o:
    for n, data in parts.items():
        if n in EXOTIC:
            continue
        if n == "word/document.xml":
            o.writestr(n, b.encode("utf-8"))
        elif n == "word/_rels/document.xml.rels":
            o.writestr(n, newrels.encode("utf-8"))
        elif n == "[Content_Types].xml":
            ct = data.decode("utf-8")
            for p in EXOTIC:
                base = "/" + p
                ct = re.sub(r'<Override PartName="%s"[^>]*/>' % re.escape(base), "", ct)
            o.writestr(n, ct.encode("utf-8"))
        else:
            o.writestr(n, data)
print("B_no_exotic_parts.docx  (body intact, exotic parts removed)")

print("\nTest each with /tmp/wwarm.sh <file> <basename>")
