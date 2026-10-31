#!/usr/bin/env python3
"""Track the fate of the fixture's revision content through the bridge."""
import re
import zipfile

INP = "/Users/arthrod/temp/T/editors_trial/fixture/complex.docx"
OUT = "/Users/arthrod/temp/T/editors_trial/out/docsplus/complex.docx"
EV = "/Users/arthrod/temp/T/editors_trial/harness/docsplus/evidence"

inp = zipfile.ZipFile(INP).read("word/document.xml").decode("utf8")
out = zipfile.ZipFile(OUT).read("word/document.xml").decode("utf8")
mammoth = open(EV + "/mammoth.html").read()
rendered = open(EV + "/rendered.html").read()
tiptap = open(EV + "/import.tiptap.json").read()

print("== revision-content fate ==")
print("  marker text            fixture  mammoth.html  rendered.html  tiptap.json  output.docx")
for marker in ["inserted text", "deleted text", "moved from", "moved to",
               "run whose formatting was changed"]:
    row = [marker.ljust(22)]
    for text in (inp, mammoth, rendered, tiptap, out):
        row.append(("YES" if marker in text else "no ").ljust(13))
    print("  " + "  ".join(row))

print("\n== revision markup counts (element occurrences) ==")
names = ["w:ins", "w:del", "w:delText", "w:moveFrom", "w:moveTo",
         "w:rPrChange", "w:pPrChange", "w:trPr"]
print("  %-12s %8s %13s %13s %11s %11s" % ("marker", "fixture", "mammoth.html", "rendered.html", "tiptap", "output"))
for n in names:
    print("  %-12s %8d %13d %13d %11d %11d" % (
        n, len(re.findall("<" + n + "[ >/]", inp)),
        len(re.findall("<" + n + "[ >/]", mammoth)),
        len(re.findall("<" + n + "[ >/]", rendered)),
        len(re.findall(n, tiptap)),
        len(re.findall("<" + n + "[ >/]", out))))

print("\n== revision ATTRIBUTES (author/date/id) anywhere in the bridge ==")
for text, label in ((mammoth, "mammoth.html"), (rendered, "rendered.html"),
                    (tiptap, "tiptap.json"), (out, "output.docx")):
    hits = {a: text.count(a) for a in ("w:author", "Fixture Author", "dateUtc",
                                       "w16du", "moveFrom", "rPrChange", "pPrChange",
                                       "delText", "proofErr", "dataBinding")}
    hits = {k: v for k, v in hits.items() if v}
    print("  %-15s %s" % (label, hits if hits else "none"))

print("\n== whitespace case: the w:ins run 'inserted text ' ==")
for text, label in ((inp, "fixture"), (mammoth, "mammoth.html"),
                    (rendered, "rendered.html"), (out, "output.docx")):
    m = re.search(r".{60}inserted text.{60}", text, re.S)
    print("  %-15s %s" % (label, repr(m.group(0)) if m else "NOT FOUND"))

print("\n== the <w:del> block in the fixture ==")
m = re.search(r"<w:del [^>]*>.*?</w:del>", inp, re.S)
print("  " + (m.group(0) if m else "not found"))
print("\n== does 'deleted text' appear ANYWHERE downstream? ==")
for text, label in ((mammoth, "mammoth.html"), (rendered, "rendered.html"),
                    (tiptap, "tiptap.json"), (out, "output.docx")):
    print("  %-15s %s" % (label, "YES" if "deleted text" in text else "NO"))
