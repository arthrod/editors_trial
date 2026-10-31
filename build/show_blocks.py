#!/usr/bin/env python3
"""Show the fixture's body blocks with the gap-free splitter's indexing."""
import sys
import zipfile

sys.path.insert(0, "/Users/arthrod/temp/T/editors_trial/build")
from wxml import label, split_body  # noqa: E402

z = zipfile.ZipFile("/Users/arthrod/temp/T/editors_trial/fixture/complex.docx")
DOC = z.read("word/document.xml").decode("utf-8")
HEAD, BLOCKS, TAIL = split_body(DOC)
print("blocks: %d, body chars: %d" % (len(BLOCKS), len(DOC)))
for i, b in enumerate(BLOCKS):
    print("%2d %5d  %s" % (i, len(b), label(b)))
