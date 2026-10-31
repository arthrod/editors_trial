#!/usr/bin/env python3
"""
Decisive test: are the five dangling relationship references what makes Word
refuse office-open's and Docen's output?

The body was regenerated with numeric relationship ids (rId17-rId21 for the
chart and the four SmartArt parts) while word/_rels/document.xml.rels kept
the descriptive ids (rIdChart, rIdDgmData, rIdDgmLayout, rIdDgmQuickStyle,
rIdDgmColors). This rewrites the body back to the declared ids and asks Word
to open both the original and the repaired file.

usage: python3 build/officeopen_rels_test.py
"""
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_open import open_file  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"
OUT = "/tmp/wt"
os.makedirs(OUT, exist_ok=True)

MAP = {
    "rId17": "rIdChart",
    "rId18": "rIdDgmData",
    "rId19": "rIdDgmLayout",
    "rId20": "rIdDgmQuickStyle",
    "rId21": "rIdDgmColors",
}

for editor in ["officeopen", "docen"]:
    src = os.path.join(BASE, "out", editor, "complex.docx")
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    doc = parts["word/document.xml"].decode("utf-8")
    fixed = doc
    for bad, good in MAP.items():
        fixed = re.sub(r'(r:(?:id|dm|lo|qs|cs)="%s")' % bad, r'\1'.replace('"', '"'),
                       fixed)
        fixed = fixed.replace('"%s"' % bad, '"%s"' % good)
    assert fixed != doc, "no rewrite"
    parts["word/document.xml"] = fixed.encode("utf-8")
    dst = os.path.join(OUT, "%s_rels_fixed.docx" % editor)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as o:
        for n, data in parts.items():
            o.writestr(n, data)
    print("%s: rewrote %d relationship ids" % (editor, len(MAP)))

    asis = os.path.join(OUT, "%s_as_is.docx" % editor)
    with zipfile.ZipFile(src) as z, \
            zipfile.ZipFile(asis, "w", zipfile.ZIP_DEFLATED) as o:
        for n in z.namelist():
            o.writestr(n, z.read(n))

    open_file(asis)
    open_file(dst)
    print()
