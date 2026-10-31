#!/usr/bin/env python3
"""
Render the namespace-survival matrix in the GROUPED shape Report A uses:
one table per namespace group, one column per editor.

This is the same measurement as build/ns_tables.py, laid out the way the
report reads it - grouped rather than split into column halves, with a
partial cell bolded when less than half of the namespace's distinct names
survived.

usage: python3 build/ns_group_tables.py            # print the three tables
       python3 build/ns_group_tables.py --patch <report.md>
"""
import json
import os
import sys

BASE = "/Users/arthrod/temp/T/editors_trial"

GROUPS = [
    ("WordprocessingML and revision namespaces",
     ["w", "r", "xml", "mc", "w14", "w15", "w16cid", "w16cex", "w16du"]),
    ("Drawing, chart, diagram and legacy namespaces",
     ["a", "wp", "pic", "dgm", "c", "cs", "wps", "v", "o", "w10"]),
    ("Package, metadata and foreign namespaces",
     ["ct", "rels", "app", "cp", "dc", "dcterms", "ds", "ns0", "xsi"]),
]

EDITORS = ["superdoc", "folio", "genoffice", "eigenpal", "office-open",
           "docen", "wordcraft", "fidus", "canvas", "docs.plus", "plate",
           "docxodus", "libreoffice"]

PRETTY = {
    "superdoc": "SuperDoc", "folio": "Folio", "genoffice": "GenOffice",
    "eigenpal": "eigenpal", "office-open": "office-open", "docen": "Docen",
    "wordcraft": "WordCraft", "fidus": "Fidus", "canvas": "canvas",
    "docs.plus": "docs.plus", "plate": "Plate.js", "docxodus": "Docxodus",
    "libreoffice": "LibreOffice",
}


def cell(s):
    """One matrix cell. A partial cell is bold when under half survived."""
    if s is None:
        return "—"
    kept, total = s["kept"], s["total"]
    if kept == total:
        return "all"
    if kept == 0:
        return "**none**"
    if total and (kept / total) < 0.5:
        return "**%d/%d**" % (kept, total)
    return "%d/%d" % (kept, total)


def tables():
    with open(os.path.join(BASE, "out", "ns_map.json")) as f:
        data = json.load(f)
    by = {n["prefix"]: n for n in data["namespaces"]}
    out = []
    for title, prefixes in GROUPS:
        out.append("**%s**\n" % title)
        out.append("| Namespace | Corpus names | " +
                   " | ".join(PRETTY[e] for e in EDITORS) + " |")
        out.append("|---|---:|" + "---:|" * len(EDITORS))
        for p in prefixes:
            ns = by.get(p)
            if ns is None:
                continue
            total = len(ns["corpus_names"])
            cells = [cell(ns["survival"].get(e)) for e in EDITORS]
            out.append("| `%s` | %d | %s |" % (p, total, " | ".join(cells)))
        out.append("")
    return "\n".join(out).rstrip()


def patch(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    start = None
    for i, l in enumerate(lines):
        if l.startswith("| Namespace | Corpus names | SuperDoc | Folio |"):
            start = i
            break
    if start is None:
        print("!! could not find the survival matrix in %s" % path)
        return 1
    # consume the table rows, the group headings and the blank lines between
    # them, until a paragraph that is not a table or a group heading begins
    end = start
    while end < len(lines):
        l = lines[end]
        if l.startswith("|") or l.startswith("**") or l.strip() == "":
            nxt = end + 1
            while nxt < len(lines) and lines[nxt].strip() == "":
                nxt += 1
            if l.strip() == "" and nxt < len(lines) and not (
                    lines[nxt].startswith("|") or lines[nxt].startswith("**")):
                break
            end += 1
            continue
        break
    new = tables().split("\n")
    lines[start:end] = new
    open(path, "w", encoding="utf-8").write("\n".join(lines))
    print("patched %s (lines %d-%d -> %d lines)" % (path, start + 1, end, len(new)))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--patch":
        sys.exit(patch(sys.argv[2]))
    print(tables())
