#!/usr/bin/env python3
"""
Pass-through orphans and body-orphaned relationships.

Three distinct kinds of "the part is still there but nothing uses it":

  UNREFERENCED  the part is in the package and no .rels relationship points at
                it. (The corpus's chart style/colour companions are in this
                state by construction - they are bound to the chart by part-name
                convention and a content-types declaration, not by a
                relationship.)
  BODY-ORPHANED the part is in the package AND a relationship points at it, but
                the body no longer uses that relationship id. The link survives;
                the thing that used the link does not.
  DANGLING      a .rels relationship points at a part that is not in the package.

usage: python3 build/orphan_audit.py
"""
import os
import zipfile
from xml.etree import ElementTree as ET

BASE = "/Users/arthrod/temp/T/editors_trial"

R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

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

PAYLOAD = [
    "word/afchunk.html",
    "word/charts/chart1.xml", "word/charts/style1.xml", "word/charts/colors1.xml",
    "word/diagrams/data1.xml", "word/diagrams/layout1.xml",
    "word/diagrams/quickStyle1.xml", "word/diagrams/colors1.xml",
    "word/embeddings/embedded1.docx",
    "word/embeddings/Microsoft_Excel_Worksheet.xlsx",
    "word/media/image1.png",
]


def rels_targets(z, relpart):
    """(relationship id, resolved package-absolute target, is_external) triples."""
    out = []
    try:
        root = ET.fromstring(z.read(relpart))
    except Exception:
        return out
    base = relpart.rsplit("_rels/", 1)[0]
    for rel in root:
        if not rel.tag.endswith("}Relationship"):
            continue
        tgt = rel.get("Target", "")
        if rel.get("TargetMode") == "External" or tgt.startswith(("http", "mailto", "file:")):
            out.append((rel.get("Id"), tgt, True))
            continue
        resolved = (tgt[1:] if tgt.startswith("/")
                    else os.path.normpath(os.path.join(base, tgt)).replace("\\", "/"))
        out.append((rel.get("Id"), resolved, False))
    return out


def audit(label, path):
    full = os.path.join(BASE, path)
    if not os.path.exists(full):
        return None
    z = zipfile.ZipFile(full)
    have = set(n for n in z.namelist() if not n.endswith("/"))

    dangling, targets = [], {}
    for n in sorted(have):
        if not n.endswith(".rels"):
            continue
        for rid, tgt, external in rels_targets(z, n):
            if external:
                continue
            targets.setdefault(tgt, []).append((n, rid))
            if tgt not in have:
                dangling.append((n, rid, tgt))

    # relationship ids actually used anywhere in the package's XML
    used = set()
    for part in sorted(have):
        if not part.endswith(".xml"):
            continue
        try:
            root = ET.fromstring(z.read(part))
        except Exception:
            continue
        for e in root.iter():
            for a in e.attrib:
                if a.startswith(R):
                    # the VALUE is the relationship id, not the attribute name
                    used.add(e.attrib[a])

    unreferenced = [p for p in PAYLOAD if p in have and p not in targets]
    body_orphan = []
    for p in PAYLOAD:
        if p not in have:
            continue
        for relpart, rid in targets.get(p, []):
            if rid not in used:
                body_orphan.append((p, relpart, rid))

    return {
        "label": label, "parts": len(have),
        "dangling": dangling, "unreferenced": unreferenced,
        "body_orphan": body_orphan,
    }


def main():
    print("%-14s %5s %10s %13s %13s" % (
        "editor", "parts", "dangling", "unreferenced", "body-orphaned"))
    print("-" * 104)
    for label, path in TARGETS:
        r = audit(label, path)
        if not r:
            continue
        print("%-14s %5d %10d %13d %13d" % (
            r["label"], r["parts"], len(r["dangling"]),
            len(r["unreferenced"]), len(r["body_orphan"])))
        for p in r["unreferenced"]:
            print("      UNREFERENCED   %s" % p)
        for p, relpart, rid in r["body_orphan"]:
            print("      BODY-ORPHANED  %s  (rel %s, id %s)" % (p, relpart, rid))
        for relpart, rid, tgt in r["dangling"]:
            print("      DANGLING       %s -> %s (%s)" % (relpart, tgt, rid))


if __name__ == "__main__":
    main()
