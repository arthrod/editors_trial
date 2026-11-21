#!/usr/bin/env python3
"""Control documents for the OnlyOffice host: the corpus with one, then two, constructs removed.

usage: python3 -I harness/ui/onlyoffice/make_controls.py <corpus.docx> <out dir>

OnlyOffice (CryptPad build) does not open the corpus, for two separate reasons
(Report C): its converter does not return on the `w:altChunk`, and its editor
raises an error on the SmartArt. Each control removes exactly the construct
that stops it, so the capture can show how far the next stage gets:

  no_altchunk.docx          the corpus without its <w:altChunk> element
  no_altchunk_no_dgm.docx   that, and without the run that holds the SmartArt

The removals are build/make_variants.py's (v1_no_altchunk, v4_no_smartart):
elements leave word/document.xml, every part stays in the package.
"""
import re
import sys
import zipfile
from pathlib import Path


def drop_run_with(xml: str, marker: str) -> str:
    """Remove the whole <w:r> that contains ``marker``."""
    at = xml.index(marker)
    start = max(xml.rfind("<w:r>", 0, at), xml.rfind("<w:r ", 0, at))
    end = xml.index("</w:r>", at) + len("</w:r>")
    return xml[:start] + xml[end:]


def main() -> int:
    corpus, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(corpus) as z:
        parts = [(i.filename, z.read(i.filename)) for i in z.infolist()]
    doc = dict(parts)["word/document.xml"].decode("utf-8")
    no_alt, n = re.subn(r"<w:altChunk\b[^>]*/>", "", doc)
    if n != 1:
        raise SystemExit(f"expected one w:altChunk in the corpus, found {n}")
    variants = {"no_altchunk": no_alt, "no_altchunk_no_dgm": drop_run_with(no_alt, "rIdDgmData")}
    for name, xml in variants.items():
        path = out / f"{name}.docx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as o:
            for part, data in parts:
                o.writestr(part, xml.encode("utf-8") if part == "word/document.xml" else data)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
