#!/usr/bin/env python3
"""
Package-level serialization map: what did each editor actually do with each part?

Classifies every part of every editor's output against the input corpus:

  PASSTHROUGH   the ZIP entry is byte-identical to the input's
  REWRITTEN     the bytes differ but the XML tree is semantically identical
                (re-serialized: attribute order, namespace prefixes, quoting,
                XML declaration, self-closing tags)
  CHANGED       the XML tree differs - real content was added, dropped or altered
  DROPPED       present in the input, absent from the output
  ADDED         absent from the input, present in the output
  NONXML        not XML (media, embeddings) - compared byte-wise

Usage:
  python3 build/part_map.py            # table for every editor
  python3 build/part_map.py --detail   # per-part listing
"""
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
IN = os.path.join(BASE, "fixture", "complex.docx")

EDITORS = [
    ("Plate.js", "plate"),
    ("Docxodus", "docxodus"),
    ("Apryse WebViewer", "apryse"),
    ("SuperDoc", "superdoc"),
    ("Folio", "folio"),
    ("GenOffice", "genoffice"),
    ("eigenpal", "eigenpal"),
    ("office-open", "officeopen"),
    ("Docen", "docen"),
    ("WordCraft", "wordcraft"),
    ("Fidus Writer", "fidus"),
    ("canvas-editor + plugin", "canvas"),
    ("docs.plus", "docsplus"),
    ("LibreOffice (baseline)", "lo_baseline"),
]

XSI = "{http://www.w3.org/2001/XMLSchema-instance}"


def read(path):
    with zipfile.ZipFile(path) as z:
        # skip ZIP directory entries - they are not package parts
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def canon(elem):
    """Prefix-independent canonical form of an element tree."""
    attrs = {}
    for k, v in elem.attrib.items():
        attrs[k] = v
    return (elem.tag, tuple(sorted(attrs.items())),
            (elem.text or ""), (elem.tail or ""),
            tuple(canon(c) for c in elem))


def tree(data):
    try:
        return canon(ET.fromstring(data))
    except Exception:
        return None


def classify(inp, out):
    """-> dict part -> status."""
    result = {}
    for name in sorted(set(inp) | set(out)):
        if name not in out:
            result[name] = "DROPPED"
            continue
        if name not in inp:
            result[name] = "ADDED"
            continue
        a, b = inp[name], out[name]
        if a == b:
            result[name] = "PASSTHROUGH"
            continue
        if name.endswith(".xml") or name.endswith(".rels"):
            ta, tb = tree(a), tree(b)
            if ta is not None and ta == tb:
                result[name] = "REWRITTEN"
            else:
                result[name] = "CHANGED"
        else:
            result[name] = "CHANGED"
    return result


def main():
    detail = "--detail" in sys.argv
    matrix = "--matrix" in sys.argv
    inp = read(IN)
    print("INPUT: %s (%d parts)" % (os.path.basename(IN), len(inp)))
    print()
    header = ("Editor", "PASSTHRU", "REWRITT", "CHANGED", "DROPPED", "ADDED", "parts out")
    print("%-24s %8s %8s %8s %8s %7s %9s" % header)
    print("-" * 78)
    allmaps = {}
    for name, d in EDITORS:
        path = os.path.join(BASE, "out", d, "complex.docx")
        if not os.path.exists(path):
            print("%-24s  (no output)" % name)
            continue
        out = read(path)
        m = classify(inp, out)
        allmaps[name] = m
        c = {k: 0 for k in ("PASSTHROUGH", "REWRITTEN", "CHANGED", "DROPPED", "ADDED")}
        for v in m.values():
            c[v] += 1
        print("%-24s %8d %8d %8d %8d %7d %9d"
              % (name, c["PASSTHROUGH"], c["REWRITTEN"], c["CHANGED"],
                 c["DROPPED"], c["ADDED"], len(out)))
    print()
    if matrix:
        order = [n for n, _ in EDITORS if n in allmaps]
        parts = sorted(set(inp) | set().union(*[set(allmaps[n]) for n in order]))
        print("| Package part | " + " | ".join(order) + " |")
        print("|---|" + "---|" * len(order))
        glyph = {"PASSTHROUGH": "P", "REWRITTEN": "w", "CHANGED": "C",
                 "DROPPED": "D", "ADDED": "A"}
        for p in parts:
            row = [glyph.get(allmaps[n].get(p), "·") for n in order]
            print("| `%s` | %s |" % (p, " | ".join(row)))
        print()
    if detail:
        for name, m in allmaps.items():
            print("=" * 78)
            print(name)
            print("=" * 78)
            for part, st in m.items():
                if st != "PASSTHROUGH":
                    print("   %-11s %s" % (st, part))
            print()


if __name__ == "__main__":
    main()
