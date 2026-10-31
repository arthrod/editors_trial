#!/usr/bin/env python3
"""ZIP-part symmetric difference + word/document.xml element census for the WordCraft round-trip."""
import sys, zipfile, re
import xml.etree.ElementTree as ET

INP = "/Users/arthrod/temp/T/editors_trial/fixture/complex.docx"
OUT = "/Users/arthrod/temp/T/editors_trial/out/wordcraft/complex.docx"

def parts(p):
    with zipfile.ZipFile(p) as z:
        return set(z.namelist())

i_parts, o_parts = parts(INP), parts(OUT)
only_in = sorted(i_parts - o_parts)
only_out = sorted(o_parts - i_parts)
both = sorted(i_parts & o_parts)

print("=== ZIP ENTRY COUNTS ===")
print("input parts : %d" % len(i_parts))
print("output parts: %d" % len(o_parts))
print("common      : %d" % len(both))
print("\n=== IN INPUT BUT MISSING FROM OUTPUT (%d) ===" % len(only_in))
for p in only_in:
    print("  - %s" % p)
print("\n=== IN OUTPUT BUT NOT IN INPUT (%d) ===" % len(only_out))
for p in only_out:
    print("  + %s" % p)

# sanity: output zip valid, document.xml well-formed
print("\n=== OUTPUT SANITY ===")
with zipfile.ZipFile(OUT) as z:
    bad = z.testzip()
    print("zip testzip (None==ok): %s" % bad)
    data = z.read("word/document.xml")
    print("word/document.xml bytes: %d" % len(data))
    root = ET.fromstring(data)
    print("word/document.xml well-formed: True (root=%s)" % root.tag)

print("\n=== word/document.xml ELEMENT CENSUS (output) ===")
raw = data.decode("utf-8", "replace")
for name in ["w:ins", "w:del", "w:sdt", "w:tbl", "w:proofErr", "w:delText",
             "w:moveFrom", "w:moveTo", "w:fldSimple", "w:fldChar", "w:altChunk",
             "mc:AlternateContent", "w14:paraId", "w14:textId", "w16du:dateUtc"]:
    # count element occurrences
    open_tags = len(re.findall(r"<%s(?=[\s/>])" % re.escape(name), raw))
    print("  %-22s elements: %d" % (name, open_tags))

print("\n=== w16du / w14 / mc namespace + attr survival (output document.xml) ===")
for probe in ["w16du:dateUtc", "xmlns:w16du", "xmlns:w14", "xmlns:mc",
              "mc:AlternateContent", "mc:Choice", "mc:Fallback", "w14:paraId"]:
    print("  %-22s occurrences: %d" % (probe, raw.count(probe)))

print("\n=== same probes in INPUT document.xml (for contrast) ===")
with zipfile.ZipFile(INP) as z:
    iraw = z.read("word/document.xml").decode("utf-8", "replace")
for probe in ["<w:ins", "<w:del", "<w:sdt", "<w:tbl", "<w:proofErr",
              "w16du:dateUtc", "xmlns:w16du", "xmlns:mc", "mc:AlternateContent",
              "w14:paraId", "<w:fldSimple", "<w:altChunk"]:
    print("  %-22s occurrences: %d" % (probe, iraw.count(probe)))
