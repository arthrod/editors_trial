#!/usr/bin/env python3
"""
Build a corpus with exactly ONE defect class re-introduced.

The transformations are the ones build/make_broken_fixture.py applies; here
each is optional, so a single-defect corpus can be handed to an editor to see
which defect it detects.

usage: python3 build/make_single_defect.py <defect-number> [outfile]
       python3 build/make_single_defect.py all <outdir>
"""
import os
import re
import sys
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")

DESCRIPTIONS = {
    1: "w:documentProtection after w:evenAndOddHeaders (CT_Settings)",
    2: "w:tcW after w:gridSpan/w:vMerge in every w:tcPr (CT_TcPr)",
    3: "w:cantSplit after w:tblHeader in w:trPr (CT_TrPr)",
    4: "w:spacing after w:jc inside w:pPrChange/w:pPr (CT_PPrBase)",
    5: "w:pgNumType after w:cols in the landscape w:sectPr (CT_SectPr)",
    6: "w16cid:durableId with ten hex digits (ST_LongHexNumber)",
    7: "dgm:style as a direct child of dgm:styleDef",
    8: "mc:Fallback nesting a w:r inside the outer w:r",
    9: "the OLE object pointing at 64 bytes of filler",
    10: "w:delText inside w:moveFrom",
    11: "m:oMathPara as a direct child of w:body",
    12: 'w:dirty="true" on the TOC begin fldChar',
}


def build(defects):
    """Return the package parts with exactly `defects` applied."""
    with zipfile.ZipFile(SRC) as z:
        parts = {n: z.read(n) for n in z.namelist()}

    doc = parts["word/document.xml"].decode("utf-8")

    if 12 in defects:
        doc, k = re.subn(r'<w:fldChar w:fldCharType="begin" w:dirty="false"/>',
                         '<w:fldChar w:fldCharType="begin" w:dirty="true"/>', doc)
        assert k == 1, "dirty flag"

    if 10 in defects:
        doc = doc.replace(
            '<w:moveFrom w:id="202" w:author="Fixture Author" '
            'w:date="2026-01-15T09:30:00Z"><w:r><w:t xml:space="preserve">moved away</w:t></w:r></w:moveFrom>',
            '<w:moveFrom w:id="202" w:author="Fixture Author" '
            'w:date="2026-01-15T09:30:00Z"><w:r>'
            '<w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>')
        assert "<w:delText xml:space=\"preserve\">moved away</w:delText>" in doc

    if 11 in defects:
        doc, k = re.subn(r'<w:p><m:oMathPara>(.*?)</m:oMathPara></w:p>',
                         r'<m:oMathPara>\1</m:oMathPara>', doc, flags=re.S)
        assert k == 1, "math"

    if 4 in defects:
        doc, k = re.subn(r'(<w:pPrChange\b[^>]*><w:pPr>)<w:spacing([^/]*)/><w:jc([^/]*)/>',
                         r'\1<w:jc\3/><w:spacing\2/>', doc)
        assert k == 1, "pPrChange"

    if 8 in defects:
        doc = doc.replace("<mc:Fallback><w:pict>", "<mc:Fallback><w:r><w:pict>")
        doc = doc.replace("</w:pict></mc:Fallback>", "</w:pict></w:r></mc:Fallback>")
        assert "<mc:Fallback><w:r><w:pict>" in doc

    if 5 in defects:
        def swap_pgnum(m):
            blk = m.group(0)
            pm = re.search(r"<w:pgNumType[^>]*/>", blk)
            if not pm:
                return blk
            blk2 = blk.replace(pm.group(0), "")
            cm = re.search(r"<w:cols[^>]*/>", blk2)
            return blk2[:cm.end()] + pm.group(0) + blk2[cm.end():]

        doc = re.sub(r"<w:sectPr\b.*?</w:sectPr>", swap_pgnum, doc, flags=re.S)

    parts["word/document.xml"] = doc.encode("utf-8")

    if 2 in defects:
        def swap_tcw(m):
            blk = m.group(0)
            w = re.search(r"<w:tcW[^>]*/>", blk)
            if not w:
                return blk
            rest = blk.replace(w.group(0), "")
            anchors = list(re.finditer(r"<w:(?:gridSpan|vMerge)[^>]*/>", rest))
            if not anchors:
                return blk
            at = anchors[-1].end()
            return rest[:at] + w.group(0) + rest[at:]

        doc = parts["word/document.xml"].decode("utf-8")
        doc, k = re.subn(r"<w:tcPr>.*?</w:tcPr>", swap_tcw, doc, flags=re.S)
        assert k > 0, "tcPr"
        parts["word/document.xml"] = doc.encode("utf-8")

    if 3 in defects:
        def swap_cant(m):
            blk = m.group(0)
            cs = re.search(r"<w:cantSplit[^>]*/>", blk)
            if not cs:
                return blk
            rest = blk.replace(cs.group(0), "")
            th = re.search(r"<w:tblHeader[^>]*/>", rest)
            if not th:
                return blk
            at = th.end()
            return rest[:at] + cs.group(0) + rest[at:]

        doc = parts["word/document.xml"].decode("utf-8")
        doc, k = re.subn(r"<w:trPr>.*?</w:trPr>", swap_cant, doc, flags=re.S)
        assert k > 0, "trPr"
        parts["word/document.xml"] = doc.encode("utf-8")

    if 6 in defects:
        for p in list(parts):
            if not p.endswith(".xml"):
                continue
            d = parts[p].decode("utf-8")
            if 'w16cid:durableId="12345678"' in d:
                parts[p] = d.replace('w16cid:durableId="12345678"',
                                     'w16cid:durableId="1234567890"').encode("utf-8")

    if 7 in defects:
        d = parts["word/diagrams/quickStyle1.xml"].decode("utf-8")
        m = re.search(r"<dgm:style>(.*?)</dgm:style>", d, re.S)
        if m:
            style = m.group(0)
            d2 = d.replace(style, "")
            d2 = d2.replace("</dgm:styleDef>", style + "</dgm:styleDef>")
            parts["word/diagrams/quickStyle1.xml"] = d2.encode("utf-8")

    if 9 in defects:
        parts["word/embeddings/embedded1.docx"] = b"\x00" * 64

    if 1 in defects:
        s = parts["word/settings.xml"].decode("utf-8")
        m = re.search(r"<w:documentProtection[^>]*/>", s)
        if m:
            dp = m.group(0)
            s2 = s.replace(dp, "")
            s2 = s2.replace("<w:evenAndOddHeaders/>", "<w:evenAndOddHeaders/>" + dp)
            parts["word/settings.xml"] = s2.encode("utf-8")

    return parts


def write(parts, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as o:
        for n, data in parts.items():
            o.writestr(n, data)


if __name__ == "__main__":
    arg = sys.argv[1]
    if arg == "all":
        outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, "out", "defects")
        for n in sorted(DESCRIPTIONS):
            dst = os.path.join(outdir, "d%02d.docx" % n)
            write(build({n}), dst)
            print("wrote %s  (%s)" % (dst, DESCRIPTIONS[n]))
    else:
        n = int(arg)
        dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
            BASE, "out", "defects", "d%02d.docx" % n)
        write(build({n}), dst)
        print("wrote %s  (%s)" % (dst, DESCRIPTIONS[n]))
