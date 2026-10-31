#!/usr/bin/env python3
"""Dump raw XML of selected fixture body blocks (gap-free indexing)."""
import sys
import zipfile

sys.path.insert(0, "/Users/arthrod/temp/T/editors_trial/build")
from wxml import split_body  # noqa: E402

z = zipfile.ZipFile("/Users/arthrod/temp/T/editors_trial/fixture/complex.docx")
DOC = z.read("word/document.xml").decode("utf-8")
HEAD, BLOCKS, TAIL = split_body(DOC)

for want in sys.argv[1:]:
    idx = int(want)
    print("=" * 72)
    print("BLOCK %d" % idx)
    print("=" * 72)
    print(BLOCKS[idx])
    print()
