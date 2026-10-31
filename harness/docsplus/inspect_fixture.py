#!/usr/bin/env python3
"""Report which OOXML feature markers are present in a docx part."""
import re
import sys
import zipfile

MARKERS = [
    "w:ins ", "w:del ", "w:delText", "w:moveFrom", "w:moveTo", "w:rPrChange",
    "w:pPrChange", "w:sdt>", "w:dataBinding", "w:proofErr", "m:oMath",
    "w:gridSpan", "w:vMerge", "w:tblHeader", "w:sectPr", "w:fldChar",
    "w:instrText", "w:fldSimple", "w:bookmarkStart", "w:numPr", "w:bidi",
    "w:rtl", "w:sym", "w:vanish", "w:vertAlign", "w:eastAsianLayout",
    "w:noProof", "w:noBreakHyphen", "w:softHyphen", "w:drawing", "c:chart",
    "dgm:relIds", "w:object", "w:altChunk", "w:footnoteReference",
    "w:endnoteReference", "w:commentReference", "w:trPr", "w:lock",
    "w:tblLook", "w:shd", "w:textDirection", "w:pgBorders", "w:docGrid",
]


def main(path):
    z = zipfile.ZipFile(path)
    doc = z.read("word/document.xml").decode("utf8")
    print("== document.xml markers ==")
    for m in MARKERS:
        print("  %-24s %d" % (m, doc.count("<" + m)))
    print("\n== revision elements (raw) ==")
    for m in re.finditer(r"<w:(ins|del|moveFrom|moveTo|rPrChange|pPrChange)[ >][^>]{0,170}>", doc):
        print("  " + m.group(0)[:180])
    print("\n== namespace decls ==")
    head = doc[:doc.find(">") + 1]
    for ns in re.findall(r'xmlns:(\w+)="([^"]+)"', head):
        print("  %-8s %s" % ns)


if __name__ == "__main__":
    main(sys.argv[1])
