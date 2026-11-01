#!/usr/bin/env python3
"""
What is in the DOCX but NOT rendered?

For every construct in the corpus, decide three separate things:

  PACKAGE   the construct survives into the editor's output file
  WORD      the construct is visible in MICROSOFT WORD's own rendering of it
  LO        the construct is visible in a LIBREOFFICE rendering of it

Word is the ground truth - it is the application the document is written for.
LibreOffice is the rendering proxy, because it can open every output including
the four Word refuses, and because it is scriptable and parallel. Where the
two disagree on the CORPUS, that is itself a finding: it means LibreOffice
cannot render that construct at all, and any LibreOffice-only measurement of
it is meaningless.

usage: python3 build/render_inventory.py [outdir]
"""
import json
import os
import re
import subprocess
import sys
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"

# label -> (probe text, the part that carries it in the corpus)
PROBES = [
    ("Body heading", "Chapter 1: Heading with"),
    ("Body paragraph", "are significant"),
    ("Page break", "After a page break"),
    ("CR / w:cr run", "after CR"),
    ("w14 attributes and elements", "run with unknown w14 attributes"),
    ("w:sym symbol run", "softhyphen"),
    ("Tracked insertion (w:ins)", "inserted text"),
    ("Tracked deletion (w:delText)", "deleted text"),
    ("Run formatting changed (w:rPrChange)", "run whose formatting was changed"),
    ("Paragraph formatting changed (w:pPrChange)", "paragraph whose properties were changed"),
    ("Move source (w:moveFrom)", "moved away"),
    ("Move target (w:moveTo)", "moved here"),
    ("Inserted paragraph mark", "paragraph mark was inserted"),
    ("Inserted table row (w:trPr/w:ins)", "This row was inserted"),
    ("Deleted table row (w:trPr/w:del)", "This row was deleted"),
    ("Complex field (TOC)", "Right-click and choose Update Field"),
    ("Simple field (REF)", "bookmarked anchor"),
    ("Simple field (PAGE)", "MERGEFORMAT"),
    ("Bookmark", "bookmarked anchor"),
    ("Content control (w:sdt)", "content control content"),
    ("Date-picker control", "2026-01-15"),
    ("Data-bound control", "bound value"),
    ("Nested content control", "inner nested content"),
    ("List (2 levels)", "List item level 2"),
    ("Table header cells", "Header C"),
    ("Table merged cells", "vert merged, continuation"),
    ("Table vertical merge", "vert merged, first"),
    ("Nested table", "nested 1"),
    ("OMML math", "E = mc"),
    ("Footnote", "This is the footnote body"),
    ("Endnote", "This is the endnote body"),
    ("Comment", "This is a comment body"),
    ("Header", "Default header"),
    ("Footer", "Footer text"),
    ("Text box (mc:Choice)", "Text box content"),
    ("mc:Fallback text", "AlternateContent fallback text"),
    ("RTL / Hebrew run", "Hebrew text right to left"),
    ("Complex-script run", "complex script size"),
    ("Hidden text (w:vanish)", "hidden text"),
    ("Editable region (w:permStart)", "This region is editable by everyone"),
    ("Section 1 end", "End of section 1."),
    ("Landscape section", "Landscape section content."),
    ("Chart (series names)", "Cat A"),
    ("Chart (series title)", "Series 1"),
    ("SmartArt (step 1)", "Step one"),
    ("SmartArt (step 2)", "Step two"),
    ("Glossary / building block", "Click here to enter text"),
]

RASTER = [
    ("Image part", "word/media/image1.png"),
    ("OLE embedded document", "word/embeddings/embedded1.docx"),
    ("Embedded workbook", "word/embeddings/Microsoft_Excel_Worksheet.xlsx"),
    ("Chart part", "word/charts/chart1.xml"),
    ("SmartArt data part", "word/diagrams/data1.xml"),
    ("Header part", "word/header1.xml"),
    ("Footer part", "word/footer1.xml"),
    ("Footnotes part", "word/footnotes.xml"),
    ("Endnotes part", "word/endnotes.xml"),
    ("Comments part", "word/comments.xml"),
    ("Glossary part", "word/glossary/document.xml"),
    ("altChunk part", "word/afchunk.html"),
    ("customXml part", "customXml/item1.xml"),
]

TARGETS = [
    ("corpus", "fixture/complex.docx"),
    ("superdoc", "out/superdoc/complex.docx"),
    ("folio", "out/folio/complex.docx"),
    ("genoffice", "out/genoffice/complex.docx"),
    ("eigenpal", "out/eigenpal/complex.docx"),
    ("office-open", "out/officeopen/complex.docx"),
    ("docen", "out/docen/complex.docx"),
    ("wordcraft", "out/wordcraft/complex.docx"),
    ("fidus", "out/fidus/complex.docx"),
    ("canvas", "out/canvas/complex.docx"),
    ("docs.plus", "out/docsplus/complex.docx"),
    ("plate", "out/plate/complex.docx"),
    ("docxodus", "out/docxodus/complex.docx"),
    ("apryse", "out/apryse/complex.docx"),
    ("libreoffice", "out/lo_baseline/complex.docx"),
]


def norm(s):
    return re.sub(r"\s+", " ", s)


def package(path):
    """(part names, concatenated XML text) of a package."""
    names, blob = [], []
    try:
        z = zipfile.ZipFile(path)
    except Exception:
        return None, None
    for n in z.namelist():
        if n.endswith("/"):
            continue
        names.append(n)
        if n.endswith((".xml", ".rels", ".html")):
            try:
                blob.append(z.read(n).decode("utf-8", "replace"))
            except Exception:
                pass
    return names, norm(" ".join(blob))


def pdf_text(pdf):
    if not pdf or not os.path.exists(pdf):
        return None
    r = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                       capture_output=True, text=True)
    return r.stdout


def pdf_info(pdf):
    if not pdf or not os.path.exists(pdf):
        return None, None
    r = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True)
    pages = None
    for ln in r.stdout.split("\n"):
        if ln.startswith("Pages:"):
            pages = int(ln.split()[-1])
    imgs = subprocess.run(["pdfimages", "-list", pdf],
                           capture_output=True, text=True)
    nimg = len([l for l in imgs.stdout.split("\n")[2:] if l.strip()]) \
        if imgs.returncode == 0 else 0
    return pages, nimg


def build(outdir):
    rows = {}
    for label, rel in TARGETS:
        path = os.path.join(BASE, rel)
        if not os.path.exists(path):
            continue
        names, blob = package(path)
        lo_pdf = os.path.join(outdir, "lo", label, "doc.pdf")
        wd_pdf = os.path.join(outdir, "word", label + ".pdf")
        # Word's export is named after the staged directory
        for cand in (wd_pdf,
                     os.path.join(outdir, "word", label, "complex.pdf"),
                     os.path.join(outdir, "word", label, "doc.pdf")):
            if os.path.exists(cand):
                wd_pdf = cand
                break
        else:
            wd_pdf = None
        lo_txt = pdf_text(lo_pdf)
        wd_txt = pdf_text(wd_pdf)
        lo_n = norm(lo_txt) if lo_txt is not None else None
        wd_n = norm(wd_txt) if wd_txt is not None else None
        pages, nimg = pdf_info(lo_pdf)
        wpages, wnimg = pdf_info(wd_pdf)

        e = {"pkg": {}, "word": {}, "lo": {},
             "lo_pages": pages, "lo_images": nimg,
             "word_pages": wpages, "word_images": wnimg,
             "has_word_pdf": wd_pdf is not None}
        for name, probe in PROBES:
            e["pkg"][name] = norm(probe) in blob
            e["word"][name] = None if wd_n is None else (norm(probe) in wd_n)
            e["lo"][name] = None if lo_n is None else (norm(probe) in lo_n)
        for name, part in RASTER:
            e["pkg"][name] = part in names
            e["word"][name] = None
            e["lo"][name] = None
        rows[label] = e

    with open(os.path.join(outdir, "render_inventory.json"), "w") as f:
        json.dump(rows, f, indent=1)
    return rows


def cell(e, name):
    p = e["pkg"].get(name)
    if p is None:
        return "-"
    r = e["lo"].get(name)
    w = e["word"].get(name)
    if r is None and w is None:
        return "P" if p else "-"
    rendered = (w is True) or (w is None and r is True)
    if p and rendered:
        return "both"
    if p:
        return "**file**"
    if rendered:
        return "render"
    return "-"


def main(outdir):
    rows = build(outdir)
    labels = list(rows.keys())
    names = [n for n, _ in PROBES] + [n for n, _ in RASTER]
    print("| Construct | " + " | ".join(labels) + " |")
    print("|---|" + "---|" * len(labels))
    for n in names:
        print("| %s | %s |" % (n, " | ".join(cell(rows[l], n) for l in labels)))
    print()
    print("| Output | LO pages | LO images | Word pages | Word images |")
    print("|---|---:|---:|---:|---:|")
    for l in labels:
        e = rows[l]
        print("| %s | %s | %s | %s | %s |" % (
            l, e["lo_pages"], e["lo_images"],
            e["word_pages"] if e["has_word_pdf"] else "-",
            e["word_images"] if e["has_word_pdf"] else "-"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render"))
