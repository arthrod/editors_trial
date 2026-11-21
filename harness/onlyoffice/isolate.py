#!/usr/bin/env python3
"""
Evidence for the OnlyOffice lane's failure on the corpus: which construct x2t
does not return from.

x2t (CryptPad's WebAssembly build) converts other documents in well under a
second and does not return from the trial's corpus. This writes two variants of
a .docx so the cause can be shown with the lane's own driver:

  <outdir>/without_altchunk.docx   the input with its w:altChunk element removed
  <outdir>/only_altchunk.docx      the input's body reduced to the w:altChunk
                                   (and the section properties)

usage: python3 -I harness/onlyoffice/isolate.py fixture/complex.docx <outdir>
then:  node harness/onlyoffice/roundtrip.mjs <outdir>/without_altchunk.docx <out.docx>   # returns
       node harness/onlyoffice/roundtrip.mjs <outdir>/only_altchunk.docx <out.docx>      # does not

Neither variant is a measurement of the editor on the corpus; the lane's result
on the corpus is the failure itself.
"""
import re
import sys
import zipfile
from pathlib import Path

ALT = re.compile(r"<w:altChunk\b[^>]*/>|<w:altChunk\b.*?</w:altChunk>", re.S)
BODY = re.compile(r"(<w:body>)(.*)(<w:sectPr[ >].*?</w:sectPr>\s*</w:body>)", re.S)


def write(src: zipfile.ZipFile, document: str, dst: Path) -> None:
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as out:
        for name in src.namelist():
            out.writestr(name, document.encode() if name == "word/document.xml" else src.read(name))


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(sys.argv[1]) as src:
        doc = src.read("word/document.xml").decode()
        chunks = ALT.findall(doc)
        if not chunks:
            print("the input has no w:altChunk")
            return 1
        write(src, ALT.sub("", doc), outdir / "without_altchunk.docx")
        m = BODY.search(doc)
        write(src, doc[:m.start(2)] + "".join(chunks) + doc[m.end(2):], outdir / "only_altchunk.docx")
    print(f"{len(chunks)} w:altChunk element(s); wrote {outdir}/without_altchunk.docx and {outdir}/only_altchunk.docx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
