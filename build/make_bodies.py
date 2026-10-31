#!/usr/bin/env python3
"""Build body fragments for the Word disambiguation probes."""
import os
import re
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
OUT = os.path.join(BASE, "out", "bodies")
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(os.path.join(BASE, "fixture", "complex.docx"))
DOC = z.read("word/document.xml").decode("utf-8")
body = re.search(r"(<w:body>)(.*)(</w:body>)", DOC, re.S).group(2)

blocks, i = [], 0
opener = re.compile(
    r"<w:(p|tbl|sdt|bookmarkStart|bookmarkEnd|sectPr|proofErr|permStart|"
    r"permEnd|commentRangeStart|commentRangeEnd)\b")
while i < len(body):
    mm = opener.search(body, i)
    if not mm:
        break
    tag = mm.group(1)
    depth, j = 0, mm.start()
    scan = re.compile(r"<w:%s\b[^>]*?(/?)>|</w:%s>" % (tag, tag))
    while True:
        s = scan.search(body, j)
        if not s:
            j = len(body)
            break
        if s.group(0).startswith("</"):
            depth -= 1
        elif s.group(1) != "/":
            depth += 1
        j = s.end()
        if depth == 0:
            break
    blocks.append(body[mm.start():j])
    i = j

SECTPR = blocks[-1]
assert SECTPR.startswith("<w:sectPr")
SECTPR_NOHF = re.sub(r"<w:(header|footer)Reference[^>]*/>", "", SECTPR)


def w(name, content):
    p = os.path.join(OUT, name + ".xml")
    with open(p, "w") as f:
        f.write(content)
    print(p)


w("empty_nosect", "")
w("empty_sect", SECTPR)
w("empty_sect_nohf", SECTPR_NOHF)
w("blk0_nosect", blocks[0])
w("blk0_sect", blocks[0] + SECTPR)
w("blk3_nosect", blocks[3])
w("blk3_sect", blocks[3] + SECTPR)
w("plain3", "<w:p><w:r><w:t>one</w:t></w:r></w:p>")
w("plain3_sect", "<w:p><w:r><w:t>one</w:t></w:r></w:p>" + SECTPR)
w("plain3_sect_nohf", "<w:p><w:r><w:t>one</w:t></w:r></w:p>" + SECTPR_NOHF)
