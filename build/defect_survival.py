#!/usr/bin/env python3
"""
Defect survival: does an editor REPAIR a malformed input, PRESERVE the damage,
or PROPAGATE it?

For each editor, this scans the output it produced from
fixture/complex_broken.docx and reports, per defect class, whether the defect
is still present, was silently removed, or was rewritten into a different one.

usage: python3 build/defect_survival.py
"""
import os
import re
import sys
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
BROKEN = os.path.join(BASE, "fixture", "complex_broken.docx")

EDITORS = [
    ("Plate.js", "plate"),
    ("Docxodus", "docxodus"),
    ("SuperDoc", "superdoc"), ("Folio", "folio"), ("GenOffice", "genoffice"),
    ("eigenpal", "eigenpal"), ("office-open", "officeopen"), ("Docen", "docen"),
    ("WordCraft", "wordcraft"), ("Fidus Writer", "fidus"),
    ("canvas-editor + plugin", "canvas"), ("docs.plus", "docsplus"),
    ("Apryse WebViewer", "apryse"),
    ("LibreOffice (baseline)", "lo_baseline"),
]

OUTROOT = os.path.join(BASE, "out_broken")


def text_of(path, part):
    with zipfile.ZipFile(path) as z:
        if part not in z.namelist():
            return None
        return z.read(part).decode("utf-8", "replace")


def check(doc, settings, numbering, docx_bytes, ole_present):
    """-> dict defect-number -> 'present' | 'absent' | 'removed'."""
    r = {}
    # 1 documentProtection after evenAndOddHeaders
    r[1] = "present" if (settings and settings.find("w:documentProtection") >
                          settings.find("w:evenAndOddHeaders") > -1) else "absent"
    # 2 tcW after gridSpan/vMerge
    bad = False
    for m in re.finditer(r"<w:tcPr>.*?</w:tcPr>", doc, re.S):
        s2 = m.group(0)
        anchors = [s2.find("w:gridSpan"), s2.find("w:vMerge")]
        anchors = [a for a in anchors if a >= 0]
        if anchors and s2.find("w:tcW") > min(anchors):
            bad = True
            break
    r[2] = "present" if bad else "absent"
    # 3 cantSplit after tblHeader
    m = re.search(r"<w:trPr>(?:(?!</w:trPr>).)*</w:trPr>", doc, re.S)
    r[3] = "present" if (m and m.group(0).find("w:cantSplit") >
                         m.group(0).find("w:tblHeader") > -1) else "absent"
    # 4 spacing after jc inside pPrChange
    m = re.search(r"<w:pPrChange\b.*?</w:pPrChange>", doc, re.S)
    r[4] = "present" if (m and m.group(0).find("w:spacing") >
                         m.group(0).find("w:jc") > -1) else "absent"
    # 5 pgNumType after cols
    r[5] = "present" if re.search(
        r"<w:cols[^>]*/>\s*<w:pgNumType", doc) else "absent"
    # 6 durableId with ten hex digits (it lives in numbering.xml)
    r[6] = "present" if (numbering and re.search(
        r'w16cid:durableId="[0-9A-Fa-f]{10}"', numbering)) else "absent"
    # 9 OLE payload is filler
    if docx_bytes is None:
        r[9] = "removed"
    else:
        r[9] = "present" if len(docx_bytes) == 64 else "absent"
    # 10 delText inside moveFrom
    r[10] = "present" if any("w:delText" in x for x in
                             re.findall(r"<w:moveFrom\b.*?</w:moveFrom>", doc, re.S)) else "absent"
    # 11 block-level oMathPara
    body = doc[doc.find("<w:body>"):]
    r[11] = "present" if re.search(
        r"</w:p>\s*<m:oMathPara", body) else "absent"
    # 12 dirty=true
    r[12] = "present" if re.search(r'<w:fldChar[^>]*w:dirty="(?:true|1|on)"', doc) else "absent"
    return r


def main():
    doc = text_of(BROKEN, "word/document.xml")
    settings = text_of(BROKEN, "word/settings.xml")
    numbering = text_of(BROKEN, "word/numbering.xml")
    with zipfile.ZipFile(BROKEN) as z:
        ole = z.read("word/embeddings/embedded1.docx")
    base = check(doc, settings, numbering, ole, True)
    print("BROKEN CORPUS (input) defects present: %s"
          % ", ".join("%d:%s" % (k, v) for k, v in sorted(base.items())))
    print()
    hdr = ["editor"] + ["d%d" % k for k in sorted(base)]
    print("%-24s %s" % ("", " ".join("%-4s" % h for h in hdr[1:])))
    print("-" * (24 + 5 * len(hdr[1:])))
    for label, d in EDITORS:
        p = os.path.join(OUTROOT, d, "complex.docx")
        if not os.path.exists(p):
            print("%-24s (no output)" % label)
            continue
        try:
            dd = text_of(p, "word/document.xml")
            ss = text_of(p, "word/settings.xml")
            nn = text_of(p, "word/numbering.xml")
            with zipfile.ZipFile(p) as z:
                if "word/embeddings/embedded1.docx" in z.namelist():
                    ob = z.read("word/embeddings/embedded1.docx")
                else:
                    ob = None
            res = check(dd, ss, nn, ob, ob is not None)
        except Exception as ex:
            print("%-24s ERROR %s" % (label, ex))
            continue
        def cell(v):
            return {"present": "YES", "absent": "no", "removed": "DROP"}[v]
        print("%-24s %s" % (label, " ".join("%-4s" % cell(res[k]) for k in sorted(base))))
    print()
    print("YES = the defect class is still present in that editor's output")
    print("no  = the defect class is gone (dropped with the feature, or rewritten)")
    print("DROP = the whole part carrying the defect was dropped")


if __name__ == "__main__":
    main()
