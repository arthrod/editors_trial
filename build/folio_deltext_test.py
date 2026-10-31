#!/usr/bin/env python3
"""
Decisive test: is the w:delText inside w:moveFrom what makes Word refuse
Folio's output?

Takes out/folio/complex.docx, rewrites that one construct back to w:t (the
form the corpus uses and the form Word accepts), and asks Word to open both.

usage: python3 build/folio_deltext_test.py
"""
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_open import open_file  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "out", "folio", "complex.docx")
OUT = "/tmp/wt"
os.makedirs(OUT, exist_ok=True)

with zipfile.ZipFile(SRC) as z:
    parts = {n: z.read(n) for n in z.namelist()}
doc = parts["word/document.xml"].decode("utf-8")

m = re.search(r"<w:moveFrom\b.*?</w:moveFrom>", doc, re.S)
print("as-is moveFrom:\n   %s\n" % (m.group(0) if m else "NOT FOUND"))

fixed = doc.replace(
    '<w:moveFrom w:id="202" w:author="Fixture Author" w:date="2026-01-15T09:30:00Z">'
    '<w:r><w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>',
    '<w:moveFrom w:id="202" w:author="Fixture Author" w:date="2026-01-15T09:30:00Z">'
    '<w:r><w:t xml:space="preserve">moved away</w:t></w:r></w:moveFrom>')
if fixed == doc:
    # fall back to a structural rewrite of the moveFrom subtree
    def fix(mm):
        blk = mm.group(0)
        return blk.replace("<w:delText", "<w:t").replace("</w:delText>", "</w:t>")
    fixed = re.sub(r"<w:moveFrom\b.*?</w:moveFrom>", fix, doc, flags=re.S)
assert fixed != doc, "no rewrite happened"
print("rewritten moveFrom:\n   %s\n" % re.search(
    r"<w:moveFrom\b.*?</w:moveFrom>", fixed, re.S).group(0))

parts["word/document.xml"] = fixed.encode("utf-8")
dst = os.path.join(OUT, "folio_movefrom_fixed.docx")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as o:
    for n, data in parts.items():
        o.writestr(n, data)

shutil.copy(SRC, os.path.join(OUT, "folio_as_is.docx"))
open_file(os.path.join(OUT, "folio_as_is.docx"))
open_file(dst)
