#!/usr/bin/env python3
"""Inspect comments / footnotes / endnotes / rels of the fixture."""
import re
import zipfile

z = zipfile.ZipFile("/Users/arthrod/temp/T/editors_trial/fixture/complex.docx")
for n in ["word/comments.xml", "word/footnotes.xml", "word/endnotes.xml",
          "word/_rels/document.xml.rels", "[Content_Types].xml"]:
    d = z.read(n).decode()
    print("=" * 70)
    print(n, len(d), "bytes")
    print("=" * 70)
    if n == "[Content_Types].xml":
        for m in re.finditer(r'<Override[^>]*/>|<Default[^>]*/>', d):
            print("  ", m.group(0))
    else:
        print(d[:4000])
    print()
