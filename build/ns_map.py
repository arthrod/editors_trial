#!/usr/bin/env python3
"""
Measured namespace survival: per namespace, per editor.

The static code reading says what an editor SHOULD do with each namespace.
This says what it DID, by counting the elements and attributes of each
namespace in the corpus and in every editor's output.

The comparison is prefix-independent: namespaces are matched by URI, so a
writer that renames `w14:` to `wordml:` (which mammoth does) is not mistaken
for a writer that dropped it.

usage: python3 build/ns_map.py
"""
import os
import re
import zipfile
from collections import Counter
from xml.etree import ElementTree as ET

BASE = "/Users/arthrod/temp/T/editors_trial"

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

# a friendly name for each namespace URI
NAMES = {
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main": "w",
    "http://schemas.openxmlformats.org/drawingml/2006/main": "a",
    "http://schemas.openxmlformats.org/drawingml/2006/diagram": "dgm",
    "http://schemas.openxmlformats.org/drawingml/2006/chart": "c",
    "http://schemas.openxmlformats.org/package/2006/content-types": "ct",
    "http://schemas.openxmlformats.org/package/2006/relationships": "rels",
    "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing": "wp",
    "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties": "app",
    "http://schemas.microsoft.com/office/drawing/2012/chartStyle": "cs",
    "http://schemas.openxmlformats.org/drawingml/2006/picture": "pic",
    "http://schemas.microsoft.com/office/word/2010/wordml": "w14",
    "http://schemas.microsoft.com/office/word/2010/wordprocessingShape": "wps",
    "http://schemas.openxmlformats.org/package/2006/metadata/core-properties": "cp",
    "http://purl.org/dc/elements/1.1/": "dc",
    "http://schemas.openxmlformats.org/officeDocument/2006/math": "m",
    "urn:schemas-microsoft-com:vml": "v",
    "http://schemas.openxmlformats.org/markup-compatibility/2006": "mc",
    "http://schemas.openxmlformats.org/officeDocument/2006/customXml": "ds",
    "http://example.com/fixture": "ns0",
    "http://purl.org/dc/terms/": "dcterms",
    "urn:schemas-microsoft-com:office:office": "o",
    "urn:schemas-microsoft-com:office:word": "w10",
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships": "r",
    "http://www.w3.org/XML/1998/namespace": "xml",
    "http://schemas.microsoft.com/office/word/2023/wordml/word16du": "w16du",
    "http://www.w3.org/2001/XMLSchema-instance": "xsi",
    "http://schemas.microsoft.com/office/word/2012/wordml": "w15",
    "http://schemas.microsoft.com/office/word/2016/wordml/cid": "w16cid",
    "http://schemas.microsoft.com/office/word/2018/wordml/cex": "w16cex",
    "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing": "wp14",
}


def scan(path):
    """(element counts by URI, attribute counts by URI) over every XML part.

    Also returns, per URI, the SET of distinct local names used. The count is
    a poor signal - a regenerating writer can emit more `w:` elements than the
    source and still have lost every revision wrapper. The distinct-name set
    is what answers "is this construct still there at all?".
    """
    el = Counter()
    at = Counter()
    parts = Counter()
    names = {}
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        return None, None, None, None
    for n in z.namelist():
        if not n.endswith((".xml", ".rels")) or n.endswith("/"):
            continue
        try:
            data = z.read(n)
            root = ET.fromstring(data)
        except Exception:
            continue
        for e in root.iter():
            tag = e.tag
            if not isinstance(tag, str):
                continue
            if tag.startswith("{"):
                uri, local = tag[1:].split("}", 1)
                el[uri] += 1
                parts[uri] += 1
                names.setdefault(uri, set()).add(local)
            for a in e.attrib:
                if a.startswith("{"):
                    au, al = a[1:].split("}", 1)
                    at[au] += 1
                    parts[au] += 1
                    names.setdefault(au, set()).add("@" + al)
    return el, at, parts, names


def main():
    print("%-16s %8s %8s" % ("namespace", "elements", "attrs"))
    base_el, base_at, base_parts, base_names = scan(os.path.join(BASE, "fixture", "complex.docx"))
    uris = sorted(set(base_el) | set(base_at),
                  key=lambda u: -(base_el[u] + base_at[u]))
    for u in uris:
        print("%-16s %8d %8d   parts=%d" % (
            NAMES.get(u, u.split("/")[-1][:16]), base_el[u], base_at[u], base_parts[u]))

    print()
    labels = [t[0] for t in TARGETS]
    # The header carries a literal corpus COUNT column plus one column per
    # editor, so the cell loop must skip the corpus target. Iterating the full
    # TARGETS list here shifts every editor label one place to the left and
    # silently drops the last editor's value.
    print("| namespace | corpus | " + " | ".join(labels[1:]) + " |")
    print("|---|---:|" + "---:|" * len(labels[1:]))
    for u in uris:
        name = NAMES.get(u, u.split("/")[-1][:16])
        cells = []
        for label, rel in TARGETS[1:]:
            p = os.path.join(BASE, rel)
            if not os.path.exists(p):
                cells.append("-")
                continue
            e, a, _, names = scan(p)
            if e is None:
                cells.append("-")
                continue
            want = base_names.get(u, set())
            got = names.get(u, set())
            if not want:
                cells.append("-")
                continue
            kept = len(want & got)
            frac = kept / len(want)
            if frac == 0:
                cells.append("**none**")
            elif frac >= 0.999:
                cells.append("all")
            elif frac >= 0.5:
                cells.append("%d/%d" % (kept, len(want)))
            else:
                cells.append("**%d/%d**" % (kept, len(want)))
        print("| `%s` | %d | %s |" % (
            name, len(base_names.get(u, set())), " | ".join(cells)))


if __name__ == "__main__":
    main()
