#!/usr/bin/env python3
"""
Content-types coherence: does every PartName declared in [Content_Types].xml
exist in the package, and does every XML part have a content type?

A package that declares a part it does not contain is malformed. This is the
check that catches "the part was dropped but its declaration was not".

usage: python3 build/ct_coherence.py
"""
import os
import zipfile
from xml.etree import ElementTree as ET

BASE = "/Users/arthrod/temp/T/editors_trial"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"

TARGETS = [
    ("corpus", "fixture/complex.docx"),
    ("superdoc", "out/superdoc/complex.docx"),
    ("folio", "out/folio/complex.docx"),
    ("genoffice", "out/genoffice/complex.docx"),
    ("eigenpal", "out/eigenpal/complex.docx"),
    ("office-open", "out/officeopen/complex.docx"),
    ("docen", "out/docen/complex.docx"),
    ("wordcraft", "out/wordcraft/complex.docx"),
    ("fidus", "out/fidus/complex.docx"),
    ("canvas", "out/canvas/complex.docx"),
    ("docs.plus", "out/docsplus/complex.docx"),
    ("plate", "out/plate/complex.docx"),
    ("docxodus", "out/docxodus/complex.docx"),
    ("apryse", "out/apryse/complex.docx"),
    ("libreoffice", "out/lo_baseline/complex.docx"),
]


def check(label, path):
    full = os.path.join(BASE, path)
    if not os.path.exists(full):
        return None
    z = zipfile.ZipFile(full)
    parts = set(n for n in z.namelist() if not n.endswith("/"))

    declared_over, declared_def = {}, {}
    try:
        root = ET.fromstring(z.read("[Content_Types].xml"))
    except Exception:
        return {"label": label, "error": "no [Content_Types].xml", "parts": len(parts)}
    for child in root:
        if child.tag == CT + "Override":
            declared_over[child.get("PartName", "").lstrip("/")] = child.get("ContentType")
        elif child.tag == CT + "Default":
            declared_def[child.get("Extension", "").lower()] = child.get("ContentType")

    missing = sorted(p for p in declared_over if p not in parts)

    # parts present but with no Override and no matching Default
    untyped = []
    for p in sorted(parts):
        if p == "[Content_Types].xml":
            continue
        if p in declared_over:
            continue
        ext = p.rsplit(".", 1)[-1].lower() if "." in p else ""
        if ext not in declared_def:
            untyped.append(p)

    return {
        "label": label,
        "parts": len(parts),
        "overrides": len(declared_over),
        "missing": missing,
        "untyped": untyped,
    }


def main():
    print("%-14s %6s %9s  %s" % ("editor", "parts", "overrides", "declared-but-absent parts"))
    print("-" * 110)
    for label, path in TARGETS:
        r = check(label, path)
        if not r:
            continue
        if r.get("error"):
            print("%-14s  %s" % (r["label"], r["error"]))
            continue
        miss = ", ".join(r["missing"]) if r["missing"] else "—"
        print("%-14s %6d %9d  %s" % (r["label"], r["parts"], r["overrides"], miss))
        if r["untyped"]:
            print("%-14s %6s %9s  untyped parts: %s" % (
                "", "", "", ", ".join(r["untyped"][:8])))


if __name__ == "__main__":
    main()
