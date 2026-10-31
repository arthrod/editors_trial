#!/usr/bin/env python3
"""
Check, per editor output, whether the binary payload parts survived AND
whether the body still references them.

A part can survive while its reference is dropped (and vice versa), and the
report's claims depend on which of the two actually happened.

usage: python3 build/payload_audit.py
"""
import os
import re
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
IN = os.path.join(BASE, "fixture", "complex.docx")

PAYLOAD_PARTS = [
    "word/charts/chart1.xml",
    "word/charts/style1.xml",
    "word/charts/colors1.xml",
    "word/diagrams/data1.xml",
    "word/diagrams/layout1.xml",
    "word/diagrams/quickStyle1.xml",
    "word/diagrams/colors1.xml",
    "word/embeddings/embedded1.docx",
    "word/embeddings/Microsoft_Excel_Worksheet.xlsx",
    "word/media/image1.png",
]

REF_PATTERNS = {
    "chart": r'<c:chart\b',
    "smartart": r'<dgm:relIds\b',
    "ole": r'<o:OLEObject\b',
    "image": r'<pic:pic\b|<a:blip\b',
}


def audit(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        doc = z.read("word/document.xml").decode("utf-8")
    parts = [p for p in PAYLOAD_PARTS if p in names]
    refs = {k: bool(re.search(v, doc)) for k, v in REF_PATTERNS.items()}
    return len(parts), len(PAYLOAD_PARTS), refs


def show(label, path):
    if not os.path.exists(path):
        print("%-26s MISSING" % label)
        return
    n, total, refs = audit(path)
    print("%-26s parts %2d/%2d   refs: chart=%s smartart=%s ole=%s image=%s"
          % (label, n, total, "Y" if refs["chart"] else "n",
             "Y" if refs["smartart"] else "n", "Y" if refs["ole"] else "n",
             "Y" if refs["image"] else "n"))


if __name__ == "__main__":
    show("INPUT (corpus)", IN)
    for d in ["superdoc", "folio", "genoffice", "eigenpal", "officeopen",
              "docen", "wordcraft", "fidus", "canvas", "docsplus",
              "lo_baseline"]:
        show(d, os.path.join(BASE, "out", d, "complex.docx"))
