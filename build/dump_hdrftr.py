#!/usr/bin/env python3
"""Dump header/footer/glossary parts of the fixture."""
import re
import sys
import zipfile

z = zipfile.ZipFile("/Users/arthrod/temp/T/editors_trial/fixture/complex.docx")
for n in ["word/header1.xml", "word/header2.xml", "word/footer1.xml",
          "word/footer2.xml"]:
    d = z.read(n).decode("utf-8")
    body = re.search(r"(<w:(?:hdr|ftr)\b[^>]*>)(.*)(</w:(?:hdr|ftr)>)", d, re.S)
    print("=" * 72)
    print(n, len(d), "bytes")
    print("=" * 72)
    print(body.group(2) if body else d[:2000])
    print()
