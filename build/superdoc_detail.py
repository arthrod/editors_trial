#!/usr/bin/env python3
"""
Re-derive the SuperDoc byte-level claims from the current corpus and output:
document.xml sizes, and the split between re-serialized and pass-through parts.

usage: python3 build/superdoc_detail.py
"""
import hashlib
import os
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
IN = os.path.join(BASE, "fixture", "complex.docx")
OUT = os.path.join(BASE, "out", "superdoc", "complex.docx")


def read(path):
    with zipfile.ZipFile(path) as z:
        return {n: z.read(n) for n in z.namelist()}


a = read(IN)
b = read(OUT)
print("input  document.xml: %d bytes" % len(a["word/document.xml"]))
print("output document.xml: %d bytes" % len(b["word/document.xml"]))

common = sorted(set(a) & set(b))
same, diff = [], []
for n in common:
    if a[n] == b[n]:
        same.append(n)
    else:
        diff.append(n)
added = sorted(set(b) - set(a))
removed = sorted(set(a) - set(b))
print("\nparts: input=%d output=%d" % (len(a), len(b)))
print("byte-identical pass-through: %d" % len(same))
print("re-serialized: %d" % len(diff))
for n in diff:
    print("   RESERIALIZED %s  (%d -> %d bytes)" % (n, len(a[n]), len(b[n])))
print("added: %s" % added)
print("removed: %s" % removed)

print("\ntext stream identical:",
      __import__("re").sub(rb"<[^>]+>", b"", a["word/document.xml"])
      == __import__("re").sub(rb"<[^>]+>", b"", b["word/document.xml"]))
