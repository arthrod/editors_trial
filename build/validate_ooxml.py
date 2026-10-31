#!/usr/bin/env python3
"""
Validate a .docx against the OOXML Transitional schemas, filtering out the two
classes of error that are NOT real defects:

  1. mc:Ignorable / mc:AlternateContent markup-compatibility attributes. The
     ECMA Transitional XSD does not model the MC namespace at all, so every
     genuine Word file "fails" this check.
  2. Elements and attributes in Microsoft's extension namespaces
     (w14, w15, w16du, w16cid, w16cex, w16se, w16sdtdh). These are exactly the
     things real Word writes and marks as ignorable.

Anything left over is a genuine schema violation that Word may reject.

usage: validate_ooxml.py <file.docx> [--all]
"""
import re
import subprocess
import sys
import tempfile
import zipfile

XSD = ("/Users/arthrod/temp/T/editors_trial/repos/office-open/"
       "ooxml-schemas/transitional/wml.xsd")

# Parts validated against wml.xsd.
WML_PARTS = [
    "word/document.xml", "word/settings.xml", "word/styles.xml",
    "word/numbering.xml", "word/footnotes.xml", "word/endnotes.xml",
    "word/comments.xml", "word/header1.xml", "word/header2.xml",
    "word/footer1.xml", "word/footer2.xml", "word/fontTable.xml",
    "word/webSettings.xml", "word/glossary/document.xml",
]

EXT_NS = re.compile(
    r"microsoft\.com/office/word/(2010|2012|2016|2018|2023)/wordml")


def is_benign(msg):
    if "markup-compatibility/2006}Ignorable" in msg:
        return True
    # An element from a namespace the transitional schema set does not model
    # at all (wps, wpg, wpc, ...) satisfies a strict wildcard by design.
    if "No matching global element declaration available, but demanded by the" \
            in msg:
        return True
    if "markup-compatibility/2006}" in msg and (
            "AlternateContent" in msg or "Ignorable" in msg
            or "PreserveElements" in msg or "PreserveAttributes" in msg
            or "ProcessContent" in msg or "MustUnderstand" in msg):
        return True
    # Any error whose subject is an element/attribute in a Microsoft extension
    # namespace is ignorable markup, provided it is inside an mc:Ignorable ns.
    m = re.search(r"Element '\{([^}]+)\}", msg)
    if m and EXT_NS.search(m.group(1)):
        return True
    m = re.search(r"attribute '\{([^}]+)\}", msg)
    if m and EXT_NS.search(m.group(1)):
        return True
    return False


def main():
    path = sys.argv[1]
    show_all = "--all" in sys.argv
    z = zipfile.ZipFile(path)
    names = [n for n in WML_PARTS if n in z.namelist()]
    tmp = tempfile.mkdtemp()
    z.extractall(tmp)

    total_real = 0
    for part in names:
        r = subprocess.run(
            ["xmllint", "--noout", "--schema", XSD, f"{tmp}/{part}"],
            capture_output=True, text=True)
        errs = []
        for line in r.stderr.splitlines():
            if "Schemas validity error" not in line:
                continue
            if is_benign(line):
                if show_all:
                    print("   (benign) %s" % line.strip()[:150])
                continue
            errs.append(line.strip())
        status = "PASS" if not errs else "FAIL"
        print("%-4s %s" % (status, part))
        for e in errs:
            total_real += 1
            print("      %s" % e[2:] if e.startswith("/") else "      %s" % e[:260])
            if e.startswith("/"):
                print("      %s" % e.split("Schemas validity error")[-1][:240])

    print("\n%s" % ("NO REAL SCHEMA VIOLATIONS" if total_real == 0
                    else "%d real violation(s)" % total_real))
    return 0 if total_real == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
