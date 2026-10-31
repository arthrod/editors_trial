#!/usr/bin/env python3
"""
Validate every editor's output against the ECMA-376 Transitional XSDs, using
the same benign-class filter as build/validate_ooxml.py.

usage: python3 build/validate_all_outputs.py
"""
import os
import subprocess
import sys
import tempfile
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
XSD = os.path.join(BASE, "repos", "office-open", "ooxml-schemas",
                    "transitional", "wml.xsd")
sys.path.insert(0, os.path.join(BASE, "build"))
from validate_ooxml import WML_PARTS, is_benign  # noqa: E402

TARGETS = [
    ("SuperDoc", "out/superdoc/complex.docx"),
    ("Folio", "out/folio/complex.docx"),
    ("GenOffice", "out/genoffice/complex.docx"),
    ("eigenpal", "out/eigenpal/complex.docx"),
    ("office-open", "out/officeopen/complex.docx"),
    ("Docen", "out/docen/complex.docx"),
    ("WordCraft", "out/wordcraft/complex.docx"),
    ("Fidus Writer", "out/fidus/complex.docx"),
    ("canvas-editor + plugin", "out/canvas/complex.docx"),
    ("docs.plus", "out/docsplus/complex.docx"),
    ("LibreOffice (baseline)", "out/lo_baseline/complex.docx"),
]


def validate(path):
    z = zipfile.ZipFile(path)
    names = [n for n in WML_PARTS if n in z.namelist()]
    tmp = tempfile.mkdtemp()
    z.extractall(tmp)
    errs = []
    for part in names:
        r = subprocess.run(["xmllint", "--noout", "--schema", XSD,
                            os.path.join(tmp, part)],
                           capture_output=True, text=True)
        for line in r.stderr.splitlines():
            if "Schemas validity error" not in line:
                continue
            if is_benign(line):
                continue
            msg = line.split("Schemas validity error")[-1].strip()
            errs.append((part, msg[:150]))
    return errs


if __name__ == "__main__":
    for label, rel in TARGETS:
        p = os.path.join(BASE, rel)
        if not os.path.exists(p):
            continue
        errs = validate(p)
        print("%-26s %s" % (label, "PASS (no real violations)" if not errs
                            else "%d REAL VIOLATION(S)" % len(errs)))
        seen = set()
        for part, msg in errs:
            key = msg[:110]
            if key in seen:
                continue
            seen.add(key)
            print("      %-28s %s" % (part, msg))
