#!/usr/bin/env python3
"""
Build reduced variants of the fixture so Microsoft Word can be asked which
feature it rejects. Each variant removes one feature group from document.xml
(and, where needed, from the package) and is written to out/variants/.

usage: make_variants.py
"""
import os
import re
import shutil
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")
OUT = os.path.join(BASE, "out", "variants")
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(SRC)
parts = {n: z.read(n) for n in z.namelist()}
doc = parts["word/document.xml"].decode("utf-8")


def drop_element(xml, tag):
    """Remove every <tag ...>...</tag> and <tag .../> element (non-nested same tag)."""
    # self-closing
    xml = re.sub(r"<w:%s\b[^>]*/>" % tag, "", xml)
    # paired, allowing nested same-name (rare here)
    out = []
    i = 0
    pat = re.compile(r"<w:%s\b[^>]*?(/?)>" % tag)
    while True:
        m = pat.search(xml, i)
        if not m:
            out.append(xml[i:])
            break
        out.append(xml[i:m.start()])
        if m.group(1) == "/":
            i = m.end()
            continue
        # find matching close, counting nesting
        depth = 1
        j = m.end()
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


def drop_drawing_with(xml, marker):
    """Remove the whole <w:r> that contains the given marker."""
    out = []
    i = 0
    while True:
        m = xml.find(marker, i)
        if m < 0:
            out.append(xml[i:])
            break
        # find enclosing <w:r>
        rs = xml.rfind("<w:r>", 0, m)
        re_ = xml.rfind("<w:r ", 0, m)
        rs = max(rs, re_)
        end = xml.find("</w:r>", m)
        if rs < 0 or end < 0:
            out.append(xml[i:m.end()])
            i = m.end()
            continue
        out.append(xml[i:rs])
        i = end + len("</w:r>")
    return "".join(out)


def write(name, newdoc, drop_parts=(), mutate=None):
    p = os.path.join(OUT, name + ".docx")
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as o:
        for n, data in parts.items():
            if n in drop_parts:
                continue
            if n == "word/document.xml":
                data = newdoc.encode("utf-8")
            if mutate:
                data = mutate(n, data)
            o.writestr(n, data)
    print("wrote", p, os.path.getsize(p), "bytes")


# --- variants -----------------------------------------------------------------
d = drop_element(doc, "altChunk")
write("v1_no_altchunk", d, drop_parts=["word/afchunk.html"])

d = drop_drawing_with(doc, "<w:object")
write("v2_no_ole", d)

d = drop_drawing_with(doc, "rIdChart")
write("v3_no_chart", d)

d = drop_drawing_with(doc, "rIdDgmData")
write("v4_no_smartart", d)

d = drop_element(drop_element(doc, "sdt"), "object")
write("v5_no_sdt_no_ole", d)

d = doc.replace('<w:documentProtection w:edit="readOnly" w:enforcement="1" '
                'w:cryptProviderType="rsaAES" w:cryptAlgorithmClass="hash" '
                'w:cryptAlgorithmType="typeAny" w:cryptAlgorithmSid="14" '
                'w:cryptSpinCount="100000" w:hash="AAAA" w:salt="BBBB"/>', "")
write("v6_no_protection", d)

d = doc.replace('w14:textId="77777777"', "").replace('w14:paraId="1A2B3C4D"', "")
write("v7_no_w14attrs", d)

# strip the whole mc:AlternateContent block
m = re.search(r"<mc:AlternateContent>.*?</mc:AlternateContent>", doc, re.S)
d = doc[:m.start()] + doc[m.end():] if m else doc
write("v8_no_alternatecontent", d)

# everything exotic gone at once
d = drop_element(doc, "altChunk")
d = drop_drawing_with(d, "<w:object")
d = drop_drawing_with(d, "rIdChart")
d = drop_drawing_with(d, "rIdDgmData")
d = re.sub(r"<mc:AlternateContent>.*?</mc:AlternateContent>", "", d, flags=re.S)
d = drop_element(d, "sdt")
write("v9_minimal_exotic", d)

print("\nNow test each in Microsoft Word:")
print("  /tmp/wmatch.sh <file> <expected-basename>")
