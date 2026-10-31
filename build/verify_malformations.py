#!/usr/bin/env python3
"""Verify the specific malformation findings by reading the packages directly."""
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"


def show(label, path, want_ct=False, want_rels=None, want_doc_rels=None):
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if not n.endswith("/")]
    print("=" * 72)
    print(label)
    print("=" * 72)
    if want_ct:
        ct = z.read("[Content_Types].xml").decode("utf-8")
        print("[Content_Types].xml (%d bytes)" % len(ct))
        for m in re.finditer(r'<Default\s+Extension="([^"]+)"\s+ContentType="([^"]+)"', ct):
            print("   Default  %-8s %s" % (m.group(1), m.group(2)[:70]))
        ov = re.findall(r'<Override\s+PartName="([^"]+)"', ct)
        print("   Overrides: %d -> %s" % (len(ov), ", ".join(o.split("/")[-1] for o in ov[:12])))
        missing = [n for n in names
                   if n != "[Content_Types].xml"
                   and n.rsplit(".", 1)[-1].lower() not in
                   {d.lower() for d in re.findall(r'<Default\s+Extension="([^"]+)"', ct)}
                   and n not in {o.lstrip("/") for o in ov}]
        print("   UNCOVERED BY CONTENT TYPE: %s" % (missing or "none"))
    if want_rels:
        rp = want_rels
        if rp in names:
            r = ET.fromstring(z.read(rp))
            ids = {x.get("Id") for x in r}
            print("\n%s -> %d relationships" % (rp, len(ids)))
            for x in r:
                print("   %-10s %-95s %s" % (x.get("Id"), x.get("Type").rsplit("/", 1)[-1],
                                             x.get("Target")))
        else:
            print("\n%s : ABSENT" % rp)
    if want_doc_rels:
        print("\n--- r: references used in %s vs declared in its .rels ---" % want_doc_rels)
        doc = z.read(want_doc_rels).decode("utf-8")
        used = set(re.findall(r'r:(?:id|embed|link|pict|dm|lo|qs|cs|href)="([^"]+)"', doc))
        rp = "word/_rels/%s.rels" % os.path.basename(want_doc_rels)
        declared = set()
        if rp in names:
            declared = {x.get("Id") for x in ET.fromstring(z.read(rp))}
        print("   used      : %s" % sorted(used))
        print("   declared  : %s" % sorted(declared))
        print("   DANGLING  : %s" % sorted(used - declared))
        print("   unused    : %s" % sorted(declared - used))
    print()


import os  # noqa: E402

if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "canvas"):
        show("canvas-editor + plugin", BASE + "/out/canvas/complex.docx", want_ct=True)
    if which in ("all", "fidus"):
        show("Fidus Writer", BASE + "/out/fidus/complex.docx", want_ct=True)
    if which in ("all", "officeopen"):
        show("office-open", BASE + "/out/officeopen/complex.docx",
             want_rels="word/_rels/document.xml.rels", want_doc_rels="word/document.xml")
    if which in ("all", "docen"):
        show("Docen", BASE + "/out/docen/complex.docx",
             want_rels="word/_rels/document.xml.rels", want_doc_rels="word/document.xml")
