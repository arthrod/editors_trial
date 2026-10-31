#!/usr/bin/env python3
"""
Controlled A/B: does Word draw the corpus's SmartArt?

Build a variant of the corpus with ONE construct removed from the body, so the
difference between the two renderings isolates that construct.

usage: python3 build/ab_test.py <remove> <out.docx>
  remove: dgm | chart | pic | wps | ole
"""
import os
import re
import shutil
import sys
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")


def main():
    what = sys.argv[1]
    out = sys.argv[2]

    zin = zipfile.ZipFile(SRC)
    doc = zin.read("word/document.xml").decode("utf-8")

    if what == "dgm":
        pat = re.compile(r"<w:drawing>(?:(?!</w:drawing>).)*dgm:relIds.*?</w:drawing>", re.S)
    elif what == "chart":
        pat = re.compile(r"<w:drawing>(?:(?!</w:drawing>).)*c:chart.*?</w:drawing>", re.S)
    elif what == "pic":
        pat = re.compile(r"<w:drawing>(?:(?!</w:drawing>).)*pic:pic.*?</w:drawing>", re.S)
    elif what == "wps":
        pat = re.compile(
            r"<mc:AlternateContent>.*?</mc:AlternateContent>", re.S)
    elif what == "ole":
        pat = re.compile(r"<w:object.*?</w:object>", re.S)
    elif what == "w14":
        # the run that carries w14:textOutline - Word draws it as vector
        # outlines, so its glyphs are invisible to the PDF text layer
        pat = re.compile(r"<w:r>(?:(?!</w:r>).)*w14:textOutline.*?</w:r>", re.S)
    elif what == "math":
        # the m:oMathPara block
        pat = re.compile(r"<m:oMathPara.*?</m:oMathPara>", re.S)
    else:
        raise SystemExit("unknown target " + what)

    new, n = pat.subn("", doc)
    print("removed %d <%s> element(s)" % (n, what))
    if n == 0:
        raise SystemExit("pattern did not match")

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = new.encode("utf-8")
            zout.writestr(item, data)
    print("wrote", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
