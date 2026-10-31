#!/usr/bin/env python3
"""
Which editor outputs contain the constructs Microsoft Word refuses?

Checks the three semantic defect classes the first report measured, plus the
relationship-integrity defect, in every editor's output.

usage: python3 build/scan_word_hostile.py
"""
import os
import re
import sys
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"

TARGETS = [
    ("INPUT (corpus)", "fixture/complex.docx"),
    ("SuperDoc", "out/superdoc/complex.docx"),
    ("Folio", "out/folio/complex.docx"),
    ("GenOffice", "out/genoffice/complex.docx"),
    ("eigenpal", "out/eigenpal/complex.docx"),
    ("office-open", "out/officeopen/complex.docx"),
    ("Docen", "out/docen/complex.docx"),
    ("WordCraft", "out/wordcraft/complex.docx"),
    ("Fidus Writer", "out/fidus/complex.docx"),
    ("canvas-editor + plugin", "out/canvas/complex.docx"),
    ("docs.plus", "out/docsplus/complex.docx"),
    ("LibreOffice (baseline)", "out/lo_baseline/complex.docx"),
]


def scan(path):
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        doc = z.read("word/document.xml").decode("utf-8")
        rels_bytes = z.read("word/_rels/document.xml.rels") \
            if "word/_rels/document.xml.rels" in names else None
    out = {}

    # 1. w:delText inside w:moveFrom
    hits = 0
    for m in re.finditer(r"<w:moveFrom\b.*?</w:moveFrom>", doc, re.S):
        if "w:delText" in m.group(0):
            hits += 1
    out["delText in moveFrom"] = hits

    # 2. block-level m:oMathPara
    body = doc[doc.index("<w:body>"):]
    depth = 0
    block_math = 0
    i = 0
    while i < len(body):
        m = re.compile(r"<(/?)w:(p|tbl|sdt)\b[^>]*?(/?)>|<(/?)m:oMathPara\b[^>]*>").search(body, i)
        if not m:
            break
        if m.group(1) == "/":
            depth -= 1
        elif m.group(2) is not None and m.group(3) != "/":
            depth += 1
        elif m.group(2) is None and m.group(4) is None and depth == 0:
            block_math += 1
        i = m.end()
    out["block-level oMathPara"] = block_math

    # 3. w:dirty with a true value on any w:fldChar
    out['w:dirty="true"'] = len(re.findall(
        r"<w:fldChar[^>]*w:dirty=\"(?:true|1|on)\"", doc))

    # 4. dangling relationship references
    used = set(re.findall(r'r:(?:id|embed|link|pict|dm|lo|qs|cs|href)="([^"]+)"', doc))
    declared = set()
    if rels_bytes is not None:
        import xml.etree.ElementTree as ET
        declared = {x.get("Id") for x in ET.fromstring(rels_bytes)}
    out["dangling r:id"] = len(used - declared)

    # 5. w:object / OLE whose target is not a real package
    return out


if __name__ == "__main__":
    cols = ["delText in moveFrom", "block-level oMathPara",
            'w:dirty="true"', "dangling r:id"]
    print("%-26s %s" % ("Package", "  ".join("%-24s" % c for c in cols)))
    print("-" * 130)
    for label, rel in TARGETS:
        p = os.path.join(BASE, rel)
        if not os.path.exists(p):
            continue
        s = scan(p)
        print("%-26s %s" % (label, "  ".join("%-24d" % s[c] for c in cols)))
