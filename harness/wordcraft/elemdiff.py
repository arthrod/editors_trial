#!/usr/bin/env python3
"""Namespace-aware element/attribute comparison of word/document.xml (input vs output)."""
import zipfile
import xml.etree.ElementTree as ET

W  = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
W14= "{http://schemas.microsoft.com/office/word/2010/wordml}"
W16DU="{http://schemas.microsoft.com/office/word/2023/wordml/word16du}"

INP = "/Users/arthrod/temp/T/editors_trial/fixture/complex.docx"
OUT = "/Users/arthrod/temp/T/editors_trial/out/wordcraft/complex.docx"

def load(p):
    with zipfile.ZipFile(p) as z:
        return ET.fromstring(z.read("word/document.xml"))

def count(root, tag):
    return sum(1 for e in root.iter() if e.tag == tag)

def attrcount(root, attr):
    n = 0
    for e in root.iter():
        for k in e.attrib:
            if k == attr:
                n += 1
    return n

def rowrev(root, which):
    n = 0
    for tr in root.iter(W + "tr"):
        trpr = tr.find(W + "trPr")
        if trpr is None:
            continue
        n += len(trpr.findall(W + which))
    return n

i, o = load(INP), load(OUT)

tags = [("w:ins", W+"ins"), ("w:del", W+"del"), ("w:delText", W+"delText"),
        ("w:sdt", W+"sdt"), ("w:tbl", W+"tbl"), ("w:proofErr", W+"proofErr"),
        ("w:fldSimple", W+"fldSimple"), ("w:fldChar", W+"fldChar"),
        ("w:altChunk", W+"altChunk"), ("mc:AlternateContent", MC+"AlternateContent"),
        ("mc:Choice", MC+"Choice"), ("mc:Fallback", MC+"Fallback"),
        ("w:moveFrom", W+"moveFrom"), ("w:moveTo", W+"moveTo"),
        ("w:rPrChange", W+"rPrChange"), ("w:pPrChange", W+"pPrChange")]

print("%-24s %8s %8s" % ("element (word/document.xml)", "INPUT", "OUTPUT"))
print("-"*44)
for label, tag in tags:
    print("%-24s %8d %8d" % (label, count(i, tag), count(o, tag)))

print("-"*44)
print("%-24s %8d %8d" % ("w14:paraId attr", attrcount(i, W14+"paraId"), attrcount(o, W14+"paraId")))
print("%-24s %8d %8d" % ("w14:textId attr", attrcount(i, W14+"textId"), attrcount(o, W14+"textId")))
print("%-24s %8d %8d" % ("w16du:dateUtc attr", attrcount(i, W16DU+"dateUtc"), attrcount(o, W16DU+"dateUtc")))
print("%-24s %8d %8d" % ("trPr/w:ins", rowrev(i,"ins"), rowrev(o,"ins")))
print("%-24s %8d %8d" % ("trPr/w:del", rowrev(i,"del"), rowrev(o,"del")))

def nsdecls(root):
    return sorted(k for k in root.attrib if k.startswith("{http://www.w3.org/2000/xmlns/}") or "xmlns" in k)

print("\n--- root namespace declarations (document.xml root tag) ---")
for p, r in (("INPUT", i), ("OUTPUT", o)):
    raw = ET.tostring(r, encoding="unicode")[:0]
print("INPUT  xmlns:w16du declared :", "w16du" in ET.tostring(i, encoding="unicode")[:2000])
print("OUTPUT xmlns:w16du declared :", "w16du" in ET.tostring(o, encoding="unicode")[:2000])
