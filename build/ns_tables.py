#!/usr/bin/env python3
"""
Render the namespace-survival measurement as report-ready markdown tables.

Three shapes:
  condensed  - one row per namespace: who kept it all, who dropped it, who kept part
  partial    - one row per (namespace, editor) that lost something, with the exact lost names
  matrix     - the full matrix, split into two column-halves

usage: python3 build/ns_tables.py [section]
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

# editor order used everywhere in the reports
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


def load():
    with open(os.path.join(BASE, "out", "ns_map.json")) as f:
        return json.load(f)


def ns_by_prefix(data):
    return {n["prefix"]: n for n in data["namespaces"]}


def condensed(data):
    by = ns_by_prefix(data)
    out = []
    for title, prefixes in GROUPS:
        out.append("**%s**\n" % title)
        out.append("| Namespace | Corpus names | Kept by all | Kept partially | Dropped entirely |")
        out.append("|---|---:|---:|---:|---:|")
        for p in prefixes:
            ns = by.get(p)
            if ns is None:
                continue
            total = len(ns["corpus_names"])
            allk, partial, none_ = [], [], []
            for lab in EDITORS:
                s = ns["survival"].get(lab)
                if s is None:
                    continue
                if s["kept"] == s["total"]:
                    allk.append(lab)
                elif s["kept"] == 0:
                    none_.append(lab)
                else:
                    partial.append(lab)
            fmt = lambda xs: ", ".join(PRETTY[x] for x in xs) if xs else "—"
            out.append("| `%s` | %d | %s | %s | %s |" % (
                p, total, fmt(allk), fmt(partial), fmt(none_)))
        out.append("")
    return "\n".join(out)


def partial(data, cap=8):
    by = ns_by_prefix(data)
    out = []
    out.append("| Namespace | Editor | Kept | Lost names |")
    out.append("|---|---|---:|---|")
    for title, prefixes in GROUPS:
        for p in prefixes:
            ns = by.get(p)
            if ns is None:
                continue
            for lab in EDITORS:
                s = ns["survival"].get(lab)
                if s is None or s["kept"] == s["total"] or s["kept"] == 0:
                    continue
                lost = s["lost"]
                if len(lost) > cap:
                    shown = ", ".join("`%s`" % x for x in lost[:cap])
                    shown += " … (+%d more)" % (len(lost) - cap)
                else:
                    shown = ", ".join("`%s`" % x for x in lost)
                out.append("| `%s` | %s | %d/%d | %s |" % (
                    p, PRETTY[lab], s["kept"], s["total"], shown))
    return "\n".join(out)


def matrix(data):
    by = ns_by_prefix(data)
    order = [t for g in GROUPS for t in g[1]]
    halves = [EDITORS[:6], EDITORS[6:]]
    out = []
    for hi, half in enumerate(halves):
        out.append("**Column half %d of 2**\n" % (hi + 1))
        out.append("| Namespace | Corpus | " + " | ".join(PRETTY[x] for x in half) + " |")
        out.append("|---|---:|" + "---:|" * len(half))
        for p in order:
            ns = by.get(p)
            if ns is None:
                continue
            total = len(ns["corpus_names"])
            cells = []
            for lab in half:
                s = ns["survival"].get(lab)
                if s is None:
                    cells.append("—")
                elif s["kept"] == s["total"]:
                    cells.append("all")
                elif s["kept"] == 0:
                    cells.append("**none**")
                else:
                    cells.append("%d/%d" % (s["kept"], s["total"]))
            out.append("| `%s` | %d | %s |" % (p, total, " | ".join(cells)))
        out.append("")
    return "\n".join(out)


def _cell(s):
    if s is None:
        return "—"
    if s["kept"] == s["total"]:
        return "all"
    if s["kept"] == 0:
        return "**none**"
    frac = "%d/%d" % (s["kept"], s["total"])
    # Report A bolds a namespace an editor keeps less than half of.
    return "**%s**" % frac if 2 * s["kept"] < s["total"] else frac


def report_matrix(data, group):
    """One of Report A's three full-width tables (every editor, one group)."""
    by = ns_by_prefix(data)
    out = ["| Namespace | Corpus names | " + " | ".join(PRETTY[x] for x in EDITORS) + " |",
           "|---|---:|" + "---:|" * len(EDITORS)]
    for p in GROUPS[group][1]:
        ns = by.get(p)
        if ns is None:
            continue
        cells = [_cell(ns["survival"].get(lab)) for lab in EDITORS]
        out.append("| `%s` | %d | %s |" % (p, len(ns["corpus_names"]), " | ".join(cells)))
    return "\n".join(out)


def main():
    data = load()
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "condensed"):
        print(condensed(data))
    if which in ("all", "partial"):
        print(partial(data))
    if which in ("all", "matrix"):
        print(matrix(data))


if __name__ == "__main__":
    main()
