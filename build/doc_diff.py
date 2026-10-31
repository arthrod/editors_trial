#!/usr/bin/env python3
"""
Structural diff of word/document.xml between the corpus and an editor output.

Walks both trees in parallel and reports the first differences: elements that
appear, vanish or change, with their position in the tree, so a Word refusal
can be traced to a specific construct.

usage: python3 build/doc_diff.py <editor-out-dir> [more dirs]
"""
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

BASE = "/Users/arthrod/temp/T/editors_trial"
IN = os.path.join(BASE, "fixture", "complex.docx")


def load(path):
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode("utf-8")


def short(tag):
    return tag.split("}")[-1]


def paths(root):
    out = []
    stack = [(root, "")]
    while stack:
        el, pre = stack.pop(0)
        p = pre + "/" + short(el.tag)
        out.append((p, el))
        for c in list(el):
            stack.append((c, p))
    return out


def main():
    targets = sys.argv[1:] or ["folio", "officeopen"]
    a_text = load(IN)
    a = ET.fromstring(a_text.encode("utf-8"))
    ap = dict(paths(a))
    for t in targets:
        path = os.path.join(BASE, "out", t, "complex.docx")
        b_text = load(path)
        b = ET.fromstring(b_text.encode("utf-8"))
        bp = dict(paths(b))
        print("=" * 74)
        print(t)
        print("=" * 74)
        onlya = sorted(set(ap) - set(bp))
        onlyb = sorted(set(bp) - set(ap))
        print("elements only in corpus : %d" % len(onlya))
        for p in onlya[:25]:
            print("   - %s" % p)
        print("elements only in output : %d" % len(onlyb))
        for p in onlyb[:25]:
            print("   + %s" % p)
        changed = []
        for p in sorted(set(ap) & set(bp)):
            ea, eb = ap[p], bp[p]
            if sorted(ea.attrib.items()) != sorted(eb.attrib.items()):
                changed.append((p, "attrs", dict(ea.attrib), dict(eb.attrib)))
            elif (ea.text or "") != (eb.text or ""):
                changed.append((p, "text", (ea.text or "")[:60], (eb.text or "")[:60]))
        print("changed attributes/text : %d" % len(changed))
        for p, kind, x, y in changed[:30]:
            if kind == "attrs":
                da = {k.split("}")[-1]: v for k, v in x.items()}
                db = {k.split("}")[-1]: v for k, v in y.items()}
                diff = {k: (da.get(k), db.get(k)) for k in set(da) | set(db)
                        if da.get(k) != db.get(k)}
                print("   ~ %-60s %s" % (p[-60:], diff))
            else:
                print("   ~ %-60s %r -> %r" % (p[-60:], x, y))
        print()


if __name__ == "__main__":
    main()
