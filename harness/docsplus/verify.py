#!/usr/bin/env python3
"""Verify the produced .docx and diff its ZIP parts against the input."""
import json
import sys
import xml.etree.ElementTree as ET
import zipfile

INP = "/Users/arthrod/temp/T/editors_trial/fixture/complex.docx"
OUT = "/Users/arthrod/temp/T/editors_trial/out/docsplus/complex.docx"

zi, zo = zipfile.ZipFile(INP), zipfile.ZipFile(OUT)

print("== integrity ==")
print("  input  testzip :", zi.testzip())
print("  output testzip :", zo.testzip())
doc = zo.read("word/document.xml")
root = ET.fromstring(doc)
print("  output word/document.xml well-formed: True (%d bytes)" % len(doc))
print("  output root tag:", root.tag)
bad = []
for n in zo.namelist():
    if n.endswith(".xml") or n.endswith(".rels"):
        try:
            ET.fromstring(zo.read(n))
        except Exception as exc:
            bad.append((n, str(exc)))
print("  malformed xml parts in output:", bad if bad else "none")

ni, no = set(zi.namelist()), set(zo.namelist())
missing = sorted(ni - no)
new = sorted(no - ni)
common = sorted(ni & no)

print("\n== ZIP part symmetric difference ==")
print("  input parts  : %d" % len(ni))
print("  output parts : %d" % len(no))
print("  common       : %d" % len(common))
print("\n  MISSING from output (%d):" % len(missing))
for n in missing:
    print("    - %-45s (%d B)" % (n, zi.getinfo(n).file_size))
print("\n  NEW in output (%d):" % len(new))
for n in new:
    print("    + %-45s (%d B)" % (n, zo.getinfo(n).file_size))
print("\n  common parts with changed size:")
for n in common:
    a, b = zi.getinfo(n).file_size, zo.getinfo(n).file_size
    if a != b:
        print("    ~ %-45s %d B -> %d B" % (n, a, b))

print("\n== failed checks (from score.json) ==")
res = json.load(open("/Users/arthrod/temp/T/editors_trial/out/docsplus/score.json"))
failed = [c for c in res["checks"] if not c["pass"]]
for c in failed:
    print("  FAIL %-24s %-52s w=%d %s" % (c["id"], c["label"], c["weight"], c["detail"]))
print("\n  failed count: %d / %d" % (len(failed), len(res["checks"])))
print("  score:", json.dumps(res["score"]))
print("  text_retention_pct:", res["text_retention_pct"])
