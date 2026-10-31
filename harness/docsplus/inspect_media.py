#!/usr/bin/env python3
"""Dump the fixture's media bytes and the document.xml region around w:drawing."""
import binascii
import re
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
img = z.read("word/media/image1.png")
print("image1.png len=%d" % len(img))
print("  first 32 bytes hex :", binascii.hexlify(img[:32]).decode())
print("  first 32 bytes repr:", repr(img[:32]))
print("  PNG magic ok       :", img[:8] == b"\x89PNG\r\n\x1a\n")

doc = z.read("word/document.xml").decode("utf8")
m = re.search(r".{200}<w:drawing.{900}", doc, re.S)
print("\n== around w:drawing ==")
print(m.group(0) if m else "not found")

m2 = re.search(r"<w:ins [^>]*>.{0,400}", doc, re.S)
print("\n== around first w:ins ==")
print(m2.group(0) if m2 else "not found")

m3 = re.search(r"<w:del [^>]*>.{0,400}", doc, re.S)
print("\n== around first w:del ==")
print(m3.group(0) if m3 else "not found")
