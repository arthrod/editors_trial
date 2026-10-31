#!/usr/bin/env python3
"""
Bisect the fixture BODY by feature group: each variant removes one group from
document.xml (package untouched) so Word can name the group it rejects.

usage: body_groups.py
"""
import os
import re
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")
OUT = os.path.join(BASE, "out", "bodygroups")
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(SRC)
parts = {n: z.read(n) for n in z.namelist()}
DOC = parts["word/document.xml"].decode("utf-8")


def drop_tag(xml, tag):
    """Remove <tag .../> and <tag ...>...</tag> (nesting-aware) for one tag name."""
    pat = re.compile(r"<w:%s\b[^>]*?(/?)>" % tag)
    out, i = [], 0
    while True:
        m = pat.search(xml, i)
        if not m:
            out.append(xml[i:])
            break
        out.append(xml[i:m.start()])
        if m.group(1) == "/":
            i = m.end()
            continue
        depth, j = 1, m.end()
        scan = re.compile(r"<w:%s\b[^>]*?(/?)>|</w:%s>" % (tag, tag))
        while depth > 0:
            mm = scan.search(xml, j)
            if not mm:
                j = len(xml)
                break
            if mm.group(0).startswith("</"):
                depth -= 1
            elif mm.group(1) != "/":
                depth += 1
            j = mm.end()
        i = j
    return "".join(out)


def drop_run_containing(xml, marker):
    """Remove the enclosing <w:r> of a marker (also handles table-level blocks)."""
    out, i = [], 0
    while True:
        m = xml.find(marker, i)
        if m < 0:
            out.append(xml[i:])
            break
        rs = max(xml.rfind("<w:r>", 0, m), xml.rfind("<w:r ", 0, m))
        end = xml.find("</w:r>", m)
        if rs < 0 or end < 0:
            out.append(xml[i:m.end()])
            i = m.end()
            continue
        out.append(xml[i:rs])
        i = end + len("</w:r>")
    return "".join(out)


def write(name, doc):
    p = os.path.join(OUT, name + ".docx")
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as o:
        for n, data in parts.items():
            o.writestr(n, doc.encode("utf-8") if n == "word/document.xml" else data)
    print("wrote", name)


# --- group removals ----------------------------------------------------------
d = drop_run_containing(DOC, "<w:object")
write("no_ole", d)

d = drop_run_containing(DOC, "rIdChart")
write("no_chart", d)

d = drop_run_containing(DOC, "rIdDgmData")
write("no_smartart", d)

d = drop_tag(DOC, "altChunk")
write("no_altchunk", d)

d = drop_tag(DOC, "sdt")
write("no_sdt", d)

d = DOC
for t in ("ins", "del", "moveFrom", "moveTo", "moveFromRangeStart",
          "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd",
          "rPrChange", "pPrChange"):
    d = drop_tag(d, t)
write("no_tracked", d)

d = drop_tag(DOC, "tbl")
write("no_tables", d)

d = DOC
for t in ("fldChar", "instrText", "fldSimple", "bookmarkStart", "bookmarkEnd"):
    d = drop_tag(d, t)
write("no_fields", d)

d = drop_tag(DOC, "proofErr")
write("no_prooferr", d)

d = drop_tag(DOC, "permStart")
d = drop_tag(d, "permEnd")
write("no_perm", d)

d = DOC.replace("<m:oMathPara>", "").replace("</m:oMathPara>", "")
write("no_math", d)

d = re.sub(r"<w:sectPr\b.*?</w:sectPr>", "", DOC, flags=re.S)
write("no_sections", d)

print("\nTest each with /tmp/wwarm.sh <file> <basename>")
