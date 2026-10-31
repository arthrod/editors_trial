#!/usr/bin/env python3
"""Show the body of an arbitrary docx's document.xml (block-per-paragraph)."""
import re
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
d = z.read("word/document.xml").decode("utf-8")
m = re.search(r"(<w:body>)(.*)(</w:body>)", d, re.S)
body = m.group(2)
print("--- body (%d chars) ---" % len(body))
print(body)
