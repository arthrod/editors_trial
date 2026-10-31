#!/usr/bin/env python3
"""
Forward relationship resolution: does every r:id / r:embed / r:dm / r:lo /
r:qs / r:cs used in a part have a matching <Relationship Id=...> in that
part's .rels file?

This is the direction a reader cares about. The reverse direction (a .rels
entry pointing at a part that is not in the package) is a dangling part; a body
that references a relationship id which does not exist is a dangling REFERENCE,
and it is invisible to every checker that only validates the relationship graph
in one direction.

usage: python3 build/rel_forward.py
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
    ("libreoffice", "out/lo_baseline/complex.docx"),
]


def rels_ids(z, part):
    """The set of relationship ids defined for `part`."""
    d = os.path.dirname(part)
    relpart = (d + "/" if d else "") + "_rels/" + os.path.basename(part) + ".rels"
    ids = {}
    try:
        root = ET.fromstring(z.read(relpart))
    except Exception:
        return ids, relpart
    for rel in root:
        if rel.tag.endswith("}Relationship"):
            ids[rel.get("Id")] = rel.get("Target")
    return ids, relpart


def main():
    print("%-14s %5s %8s  %s" % ("editor", "parts", "bad-refs", "detail"))
    print("-" * 108)
    for label, path in TARGETS:
        full = os.path.join(BASE, path)
        if not os.path.exists(full):
            continue
        z = zipfile.ZipFile(full)
        have = set(n for n in z.namelist() if not n.endswith("/"))
        bad = []
        for part in sorted(have):
            if not part.endswith(".xml") or part.startswith("docProps"):
                continue
            if part == "[Content_Types].xml":
                continue
            try:
                root = ET.fromstring(z.read(part))
            except Exception:
                continue
            ids, relpart = rels_ids(z, part)
            used = set()
            for e in root.iter():
                for a, v in e.attrib.items():
                    if a.startswith(R):
                        used.add((a[len(R):], v))
            for attr, rid in sorted(used):
                if rid not in ids:
                    bad.append((part, attr, rid, relpart))
        print("%-14s %5d %8d  %s" % (
            label, len(have), len(bad),
            "; ".join("%s uses %s=%r (not in %s)" % (p.split("/")[-1], a, r, rp.split("/")[-1])
                      for p, a, r, rp in bad[:4]) if bad else "—"))
        if len(bad) > 4:
            print("%-14s %5s %8s  ... and %d more" % ("", "", "", len(bad) - 4))


if __name__ == "__main__":
    main()
