#!/usr/bin/env python3
"""
Render every editor output with MICROSOFT WORD, to PDF.

Word's own rendering is the ground truth: it is the application the document
was written for. LibreOffice is the proxy, because it can open the four files
Word refuses and because it is scriptable and parallel; this script produces
the reference series that the proxy series is checked against.

Word is driven by the audited driver (build/word_batch.py ->
build/vendor/word_pdf.py), which stages each file under a unique name, saves
the document it named (never `active document`), and answers Word's repair
prompt "No", so a refused file produces no PDF rather than Word's repair.

usage: python3 build/word_render_all.py <outdir>
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import word_batch  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"

TARGETS = [
    ("corpus", os.path.join(BASE, "fixture", "complex.docx")),
    ("superdoc", os.path.join(BASE, "out", "superdoc", "complex.docx")),
    ("folio", os.path.join(BASE, "out", "folio", "complex.docx")),
    ("genoffice", os.path.join(BASE, "out", "genoffice", "complex.docx")),
    ("eigenpal", os.path.join(BASE, "out", "eigenpal", "complex.docx")),
    ("office-open", os.path.join(BASE, "out", "officeopen", "complex.docx")),
    ("docen", os.path.join(BASE, "out", "docen", "complex.docx")),
    ("wordcraft", os.path.join(BASE, "out", "wordcraft", "complex.docx")),
    ("fidus", os.path.join(BASE, "out", "fidus", "complex.docx")),
    ("canvas", os.path.join(BASE, "out", "canvas", "complex.docx")),
    ("docs.plus", os.path.join(BASE, "out", "docsplus", "complex.docx")),
    ("plate", os.path.join(BASE, "out", "plate", "complex.docx")),
    ("docxodus", os.path.join(BASE, "out", "docxodus", "complex.docx")),
    ("apryse", os.path.join(BASE, "out", "apryse", "complex.docx")),
    ("libreoffice", os.path.join(BASE, "out", "lo_baseline", "complex.docx")),
]


def main(outdir):
    targets = {label: Path(path) for label, path in TARGETS if os.path.exists(path)}
    for label, path in TARGETS:
        if label not in targets:
            print("  %-12s MISSING" % label, flush=True)
    verdicts = word_batch.run(targets, Path(outdir))
    for label, v in verdicts.items():
        print("  %-12s %s" % (label, "OK" if v == "OPENED" else v), flush=True)
    ok = sum(v == "OPENED" for v in verdicts.values())
    print("rendered %d of %d with Word" % (ok, len(TARGETS)), flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render", "word"))
