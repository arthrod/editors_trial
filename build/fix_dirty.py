#!/usr/bin/env python3
"""
Set w:dirty="true" to w:dirty="false" in every word/*.xml part of a .docx.

Microsoft Word 16.115 refuses to open a document in which any w:fldChar
carries w:dirty with a true value (see the "Word Compatibility" section of
the report). pandoc writes w:dirty="true" on the TOC field of its own output,
so every .docx this project produces has to be passed through this filter
before it can be handed to anyone.

usage: python3 build/fix_dirty.py <file.docx> [more.docx ...]
"""
import os
import re
import shutil
import sys
import tempfile
import zipfile

PATTERN = re.compile(r'(<w:fldChar\b[^>]*?)\s+w:dirty="true"')


def fix(path):
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    changed = []
    for n, data in list(parts.items()):
        if not n.startswith("word/") or not n.endswith(".xml"):
            continue
        text = data.decode("utf-8")
        new = PATTERN.sub(r'\1 w:dirty="false"', text)
        if new != text:
            parts[n] = new.encode("utf-8")
            changed.append(n)
    if not changed:
        print("%-60s (no w:dirty=\"true\" found)" % os.path.basename(path))
        return
    tmp = tempfile.mktemp(suffix=".docx", dir=os.path.dirname(path))
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as o:
        for n, data in parts.items():
            o.writestr(n, data)
    shutil.move(tmp, path)
    print("%-60s fixed in %s" % (os.path.basename(path), ", ".join(changed)))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        fix(p)
