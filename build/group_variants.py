#!/usr/bin/env python3
"""
Remove one part-group at a time from the fixture, so Microsoft Word can be
asked which group it rejects. Removing a group also drops its content-type
overrides and its relationships, so each variant stays internally consistent.

usage: group_variants.py
"""
import os
import re
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")
OUT = os.path.join(BASE, "out", "groups")
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(SRC)
parts = {n: z.read(n) for n in z.namelist()}

GROUPS = {
    "chart": ["word/charts/chart1.xml", "word/charts/_rels/chart1.xml.rels",
              "word/charts/style1.xml", "word/charts/colors1.xml"],
    "diagram": ["word/diagrams/data1.xml", "word/diagrams/layout1.xml",
                "word/diagrams/quickStyle1.xml", "word/diagrams/colors1.xml"],
    "embeddings": ["word/embeddings/embedded1.docx",
                   "word/embeddings/Microsoft_Excel_Worksheet.xlsx"],
    "glossary": ["word/glossary/document.xml"],
    "customxml": ["customXml/item1.xml", "customXml/itemProps1.xml",
                  "customXml/_rels/item1.xml.rels"],
    "altchunk": ["word/afchunk.html"],
    "headers": ["word/header1.xml", "word/header2.xml",
                "word/footer1.xml", "word/footer2.xml"],
    "notes": ["word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"],
}


def build(name, drop, drop_markers=()):
    """Write a variant with `drop` parts removed and their refs stripped."""
    ct = parts["[Content_Types].xml"].decode("utf-8")
    rels = parts["word/_rels/document.xml.rels"].decode("utf-8")
    doc = parts["word/document.xml"].decode("utf-8")
    for p in drop:
        ct = re.sub(r'<Override PartName="/%s"[^>]*/>' % re.escape(p), "", ct)
        base = p.split("/")[-1]
        rels = re.sub(r'<Relationship\b[^>]*Target="[^"]*%s"[^>]*/>'
                      % re.escape(base), "", rels)
    # a Default for an extension that is no longer used is harmless, keep it.
    for marker in drop_markers:
        i = doc.find(marker)
        if i < 0:
            continue
        rs = max(doc.rfind("<w:r>", 0, i), doc.rfind("<w:r ", 0, i))
        end = doc.find("</w:r>", i)
        if rs >= 0 and end >= 0:
            doc = doc[:rs] + doc[end + len("</w:r>"):]
        else:
            doc = doc[:i] + doc[i + len(marker):]
    # a sectPr header/footer reference to a dropped part must go too
    if "word/header1.xml" in drop or "word/header2.xml" in drop:
        doc = re.sub(r'<w:headerReference\b[^>]*/>', "", doc)
    if "word/footer1.xml" in drop or "word/footer2.xml" in drop:
        doc = re.sub(r'<w:footerReference\b[^>]*/>', "", doc)

    path = os.path.join(OUT, name + ".docx")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as o:
        for n, data in parts.items():
            if n in drop:
                continue
            if n == "[Content_Types].xml":
                data = ct.encode("utf-8")
            elif n == "word/_rels/document.xml.rels":
                data = rels.encode("utf-8")
            elif n == "word/document.xml":
                data = doc.encode("utf-8")
            o.writestr(n, data)
    print("wrote", path)


MARKERS = {
    "chart": ["<w:drawing"],
    "diagram": ["<w:drawing"],
    "embeddings": ["<w:object", "<w:drawing"],
    "glossary": [],
    "customxml": [],
    "altchunk": ["<w:altChunk"],
    "headers": [],
    "notes": [],
}
# the two <w:drawing> runs (picture, chart, smartart) need distinct handling:
# remove the run that contains each specific relationship id.
for g in GROUPS:
    drop = GROUPS[g]
    name = "no_" + g
    build(name, drop, MARKERS.get(g, ()))

# Also: a variant with EVERY group removed at once (the floor).
allg = [p for ps in GROUPS.values() for p in ps]
build("none_left", allg, ["<w:altChunk"])

print("\nTest each with /tmp/wwarm.sh <file> <basename>")
