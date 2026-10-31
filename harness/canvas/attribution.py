#!/usr/bin/env python3
"""Attribute the round-trip loss to the import side or the export side.

  input.docx  --import-->  editor model (model.json)  --export-->  output.docx

Method: build a paragraph list for each stage and compare paragraph texts
after whitespace normalisation. Paragraph-level comparison is immune to the
run-merging that the exporter does (a merged run still contains the same
text), so a paragraph that is absent downstream is a genuine loss.

Also prints the ZIP part symmetric difference between input and output.
"""
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

INP = "/Users/arthrod/temp/T/editors_trial/fixture/complex.docx"
OUT = "/Users/arthrod/temp/T/editors_trial/out/canvas/complex.docx"
MODEL = "/Users/arthrod/temp/T/editors_trial/out/canvas/model.json"


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- docx paras
def docx_paras(path, parts=("word/document.xml",)):
    z = zipfile.ZipFile(path)
    paras = []
    for part in parts:
        if part not in z.namelist():
            continue
        t = ET.fromstring(z.read(part))
        for p in t.iter(W + "p"):
            buf = []
            for e in p.iter():
                if e.tag in (W + "t", W + "delText"):
                    buf.append(e.text or "")
                elif e.tag == M + "t":
                    buf.append(e.text or "")
                elif e.tag == W + "tab":
                    buf.append("\t")
                elif e.tag in (W + "br", W + "cr"):
                    buf.append("\n")
            paras.append(norm("".join(buf)))
    return paras


def all_body_parts(path):
    z = zipfile.ZipFile(path)
    return [
        n
        for n in sorted(z.namelist())
        if n == "word/document.xml"
        or (n.startswith("word/header") or n.startswith("word/footer"))
        and n.endswith(".xml")
    ]


# --------------------------------------------------------------- model paras
def model_paras(path):
    data = json.load(open(path))
    paras = []

    def emit(text):
        for line in text.split("\n"):
            p = norm(line)
            if p:
                paras.append(p)

    def walk(elems):
        for e in elems or []:
            t = e.get("type")
            if t == "table":
                for tr in e.get("trList") or []:
                    for td in tr.get("tdList") or []:
                        walk(td.get("value"))
                continue
            if t == "control":
                walk((e.get("control") or {}).get("value"))
                continue
            if t == "image":
                continue
            vl = e.get("valueList")
            if vl:
                buf = ""
                for c in vl:
                    v = c.get("value") or ""
                    if v == "\n":          # a run break ends the paragraph
                        emit(buf)
                        buf = ""
                    else:
                        buf += v
                emit(buf)
                continue
            v = e.get("value")
            if isinstance(v, str):
                emit(v)

    for zone in ("header", "main", "footer"):
        walk(data.get(zone))
    return paras


def main():
    in_paras = [p for p in docx_paras(INP) if p]
    md_paras = [p for p in model_paras(MODEL) if p]
    # the exporter writes headers/footers into their own parts, so the output
    # comparison has to look at those too (the checker's text metric only
    # reads word/document.xml, which is why it reports 42 vs 41 paragraphs).
    out_paras = [p for p in docx_paras(OUT, all_body_parts(OUT)) if p]

    out_blob = norm(" \n ".join(out_paras))
    md_blob = norm(" \n ".join(md_paras))

    def present(p, blob):
        # tolerate the exporter's literal list-number prefix ("1. List item ...")
        if p in blob:
            return True
        stripped = re.sub(r"^\d+[.)]\s*", "", p)
        return stripped in blob and stripped != p

    lost_import = [p for p in in_paras if not present(p, md_blob)]
    lost_export = [p for p in md_paras if not present(p, out_blob)]

    print("=" * 72)
    print("PARAGRAPH COUNTS")
    print("  input docx paragraphs (non-empty): %d" % len(in_paras))
    print("  editor model paragraphs (non-empty): %d" % len(md_paras))
    print("  output docx paragraphs (non-empty): %d" % len(out_paras))
    print()
    print("ATTRIBUTION (paragraph level)")
    print("  input paragraphs NOT in the editor model (LOST BY IMPORTER): %d"
          % len(lost_import))
    for p in lost_import:
        print("     - %r" % p[:110])
    print()
    print("  model paragraphs NOT in the output docx (LOST BY EXPORTER): %d"
          % len(lost_export))
    for p in lost_export:
        print("     - %r" % p[:110])
    print()

    # ------------------------------------------------------- part diff
    zi, zo = zipfile.ZipFile(INP), zipfile.ZipFile(OUT)
    ni, no = set(zi.namelist()), set(zo.namelist())
    print("ZIP PART SYMMETRIC DIFFERENCE")
    print("  in INPUT but not in OUTPUT (%d):" % len(ni - no))
    for n in sorted(ni - no):
        print("     - %s" % n)
    print("  in OUTPUT but not in INPUT (%d):" % len(no - ni))
    for n in sorted(no - ni):
        print("     + %s" % n)
    print("  in BOTH (%d):" % len(ni & no))
    for n in sorted(ni & no):
        print("     = %s" % n)

    json.dump(
        {
            "input_paragraphs": len(in_paras),
            "model_paragraphs": len(md_paras),
            "output_paragraphs": len(out_paras),
            "lost_by_importer": lost_import,
            "lost_by_exporter": lost_export,
            "parts_input_only": sorted(ni - no),
            "parts_output_only": sorted(no - ni),
            "parts_both": sorted(ni & no),
        },
        open("/Users/arthrod/temp/T/editors_trial/out/canvas/attribution.json", "w"),
        indent=2,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
