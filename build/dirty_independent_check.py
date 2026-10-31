#!/usr/bin/env python3
"""
Independent confirmation of the w:dirty rule, on a package that has nothing
to do with the fixture.

Takes the pandoc-built report .docx, injects w:dirty="true" into its TOC
field's begin fldChar, and asks Word to open both the untouched and the
injected copy. If the injected copy is refused while the original opens, the
rule is a property of Word, not of the corpus.

usage: python3 build/dirty_independent_check.py
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_open import open_file  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"
REPORT = os.path.join(BASE, "Open-Source DOCX Editors Re-verified Against "
                               "Code and Measured Round-Trip (2026).docx")
OUT = "/tmp/wt"

os.makedirs(OUT, exist_ok=True)

plain = os.path.join(OUT, "report_clean.docx")
shutil.copy(REPORT, plain)

dirty = os.path.join(OUT, "report_dirty.docx")
with zipfile.ZipFile(REPORT) as z:
    parts = {n: z.read(n) for n in z.namelist()}
doc = parts["word/document.xml"].decode("utf-8")
before = doc
doc = re.sub(r'<w:fldChar w:fldCharType="begin"\s*/>',
             '<w:fldChar w:fldCharType="begin" w:dirty="true"/>', doc)
if doc == before:
    # pandoc may write the attribute with a different spacing; fall back
    doc = before.replace('<w:fldChar w:fldCharType="begin"/>',
                          '<w:fldChar w:fldCharType="begin" w:dirty="true"/>')
assert doc != before, "no begin fldChar found to mark dirty"
parts["word/document.xml"] = doc.encode("utf-8")
with zipfile.ZipFile(dirty, "w", zipfile.ZIP_DEFLATED) as o:
    for n, data in parts.items():
        o.writestr(n, data)

open_file(plain)
open_file(dirty)
