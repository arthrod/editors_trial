#!/usr/bin/env python3
"""
Defect survival: does an editor REPAIR a malformed input, PRESERVE the damage,
or PROPAGATE it?

For each editor, this scans the output it produced from
fixture/complex_broken.docx and reports, per defect class, whether the defect
is still present, was silently removed, or was rewritten into a different one.
Report B's table is table(): these cells plus Word's verdict on the same
outputs (out/word_verdicts_broken.json, from build/word_verdicts.py --set broken).

usage: python3 build/defect_survival.py
"""
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = str(ROOT)
BROKEN = os.path.join(BASE, "fixture", "complex_broken.docx")

# Report B's row order.
EDITORS = [
    ("SuperDoc", "superdoc"), ("Folio", "folio"), ("GenOffice", "genoffice"),
    ("eigenpal", "eigenpal"), ("Docxodus", "docxodus"), ("office-open", "officeopen"),
    ("Docen", "docen"), ("WordCraft", "wordcraft"), ("Fidus Writer", "fidus"),
    ("Plate.js", "plate"), ("canvas-editor + plugin", "canvas"), ("docs.plus", "docsplus"),
    ("Apryse WebViewer", "apryse"),
    ("LibreOffice (baseline)", "lo_baseline"),
]

# The defect classes visible in a package, with Report B's column names.
DEFECTS = {
    1: "d1 order (settings)", 2: "d2 order (tcPr)", 3: "d3 order (trPr)",
    4: "d4 order (pPrChange)", 5: "d5 order (sectPr)", 6: "d6 durableId",
    9: "d9 OLE payload", 10: "d10 delText in moveFrom", 11: "d11 block math",
    12: "d12 dirty=true",
}
CELL = {"present": "YES", "absent": "no", "removed": "DROP"}

OUTROOT = os.path.join(BASE, "out_broken")
WORD = ROOT / "out" / "word_verdicts_broken.json"


def text_of(path, part):
    with zipfile.ZipFile(path) as z:
        if part not in z.namelist():
            return None
        return z.read(part).decode("utf-8", "replace")


def check(doc, settings, numbering, docx_bytes, ole_present):
    """-> dict defect-number -> 'present' | 'absent' | 'removed'."""
    r = {}
    # 1 documentProtection after evenAndOddHeaders
    r[1] = "present" if (settings and settings.find("w:documentProtection") >
                          settings.find("w:evenAndOddHeaders") > -1) else "absent"
    # 2 tcW after gridSpan/vMerge
    bad = False
    for m in re.finditer(r"<w:tcPr>.*?</w:tcPr>", doc, re.S):
        s2 = m.group(0)
        anchors = [s2.find("w:gridSpan"), s2.find("w:vMerge")]
        anchors = [a for a in anchors if a >= 0]
        if anchors and s2.find("w:tcW") > min(anchors):
            bad = True
            break
    r[2] = "present" if bad else "absent"
    # 3 cantSplit after tblHeader
    m = re.search(r"<w:trPr>(?:(?!</w:trPr>).)*</w:trPr>", doc, re.S)
    r[3] = "present" if (m and m.group(0).find("w:cantSplit") >
                         m.group(0).find("w:tblHeader") > -1) else "absent"
    # 4 spacing after jc inside pPrChange
    m = re.search(r"<w:pPrChange\b.*?</w:pPrChange>", doc, re.S)
    r[4] = "present" if (m and m.group(0).find("w:spacing") >
                         m.group(0).find("w:jc") > -1) else "absent"
    # 5 pgNumType after cols
    r[5] = "present" if re.search(
        r"<w:cols[^>]*/>\s*<w:pgNumType", doc) else "absent"
    # 6 durableId with ten hex digits (it lives in numbering.xml)
    r[6] = "present" if (numbering and re.search(
        r'w16cid:durableId="[0-9A-Fa-f]{10}"', numbering)) else "absent"
    # 9 OLE payload is filler
    if docx_bytes is None:
        r[9] = "removed"
    else:
        r[9] = "present" if len(docx_bytes) == 64 else "absent"
    # 10 delText inside moveFrom
    r[10] = "present" if any("w:delText" in x for x in
                             re.findall(r"<w:moveFrom\b.*?</w:moveFrom>", doc, re.S)) else "absent"
    # 11 block-level oMathPara
    body = doc[doc.find("<w:body>"):]
    r[11] = "present" if re.search(
        r"</w:p>\s*<m:oMathPara", body) else "absent"
    # 12 dirty=true
    r[12] = "present" if re.search(r'<w:fldChar[^>]*w:dirty="(?:true|1|on)"', doc) else "absent"
    return r


def scan(path):
    """-> {defect: 'YES' | 'no' | 'DROP'} for one output package."""
    dd = text_of(path, "word/document.xml")
    ss = text_of(path, "word/settings.xml")
    nn = text_of(path, "word/numbering.xml")
    with zipfile.ZipFile(path) as z:
        ob = z.read("word/embeddings/embedded1.docx") if "word/embeddings/embedded1.docx" in z.namelist() else None
    res = check(dd or "", ss, nn, ob, ob is not None)
    return {k: CELL[res[k]] for k in DEFECTS}


def survival(outroot=OUTROOT, editors=EDITORS):
    """-> {dir: {defect: cell} | None}; None when the editor produced no output."""
    out = {}
    for _, d in editors:
        p = Path(outroot) / d / "complex.docx"
        out[d] = scan(p) if p.exists() else None
    return out


def table(rows, verdicts, word_version, editors=EDITORS):
    """Report B's markdown table: the defect cells, then Word's verdict on the same output."""
    head = ["Editor"] + list(DEFECTS.values()) + [f"Word {word_version}"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for label, d in editors:
        cells = rows.get(d)
        if cells is None:
            lines.append("| " + " | ".join([label] + ["—"] * len(DEFECTS) + ["no output"]) + " |")
            continue
        v = verdicts.get(d, "")
        word = f"**{v}**" if v in ("OPENED", "REFUSED") else "not measured"
        lines.append("| " + " | ".join([label] + [cells[k] for k in DEFECTS] + [word]) + " |")
    return "\n".join(lines)


FATAL = (10, 11, 12)   # the classes Report B 4.1 sets beside Word's verdict
COUNT = {0: "none", 1: "one", 2: "two", 3: "all three"}


def _verdict(v):
    return v if v in ("OPENED", "REFUSED") else "not measured"


def fatal_table(rows, verdicts, editors=EDITORS):
    """Report B 4.1: d10-d12 per editor beside Word's verdict on the same output."""
    lines = ["| Editor | d10 | d11 | d12 | Word verdict | Of d10, d11, d12 in the output |", "|---|---|---|---|---|---|"]
    for label, d in editors:
        cells = rows.get(d)
        if cells is None:
            lines.append(f"| {label} | — | — | — | no output | the importer refused the corpus |")
            continue
        alive = [k for k in FATAL if cells[k] == "YES"]
        n = COUNT[len(alive)] + (f" (d{alive[0]})" if len(alive) == 1 else "")
        lines.append("| " + " | ".join([label] + [cells[k] for k in FATAL] + [_verdict(verdicts.get(d)), n]) + " |")
    return "\n".join(lines)


def flip_table(rows, clean_opens, verdicts, editors=EDITORS):
    """Report B 4.2: Word on the clean corpus's output beside Word on the broken corpus's output."""
    lines = ["| Editor | Clean corpus | Broken corpus | Verdict flipped by the corpus? |", "|---|---|---|---|"]
    for label, d in editors:
        clean = {True: "OPENED", False: "REFUSED"}.get(clean_opens.get(d), "not measured")
        broken = "no output" if rows.get(d) is None else _verdict(verdicts.get(d))
        if "not measured" in (clean, broken):
            flip = "not measured"
        elif broken == "no output":
            flip = "**yes — the importer refused the corpus**" if clean == "OPENED" else "no"
        else:
            flip = "**yes**" if clean != broken else "no"
        lines.append(f"| {label} | {clean} | {broken} | {flip} |")
    return "\n".join(lines)


def main():
    doc = text_of(BROKEN, "word/document.xml")
    settings = text_of(BROKEN, "word/settings.xml")
    numbering = text_of(BROKEN, "word/numbering.xml")
    with zipfile.ZipFile(BROKEN) as z:
        ole = z.read("word/embeddings/embedded1.docx")
    base = check(doc, settings, numbering, ole, True)
    print("BROKEN CORPUS (input) defects present: %s"
          % ", ".join("%d:%s" % (k, v) for k, v in sorted(base.items())))
    print()
    word = json.loads(WORD.read_text()) if WORD.exists() else {"word": "?", "verdicts": {}}
    print(table(survival(), word["verdicts"], word["word"]))
    print()
    print("YES = the defect class is still present in that editor's output")
    print("no  = the defect class is gone (dropped with the feature, or rewritten)")
    print("DROP = the whole part carrying the defect was dropped")


if __name__ == "__main__":
    main()
