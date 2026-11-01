#!/usr/bin/env python3
"""Build every bomb fixture for the Word experiment into fixtures/.

B1-B10: the doc's packages, built by editors_trial/build/make_bombs.py (unchanged), canary = ../canary.txt.
E*: element floods (valid docx, N MiB of one-run paragraphs).
D*: nesting depth steps (w:sdt chains, w:tbl chains).
X*: DOCTYPE variants (no subset; internal entity; '>' inside the subset).
"""
import sys, zipfile
from pathlib import Path
EXP = Path(__file__).resolve().parent.parent
FIX = EXP / "fixtures"
sys.path.insert(0, str(EXP.parent.parent / "build"))  # the repo's build/
import make_bombs  # noqa: E402

W = make_bombs.W
CT = ('<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
      '<Default Extension="xml" ContentType="application/xml"/>'
      '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')

def pack(path, document: bytes):
    """Write a minimal DOCX ZIP containing the supplied document bytes."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("[Content_Types].xml", CT)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", document)

def doc(body: str, prelude: str = "") -> bytes:
    """Return UTF-8 document XML containing body and an optional prelude."""
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>{prelude}'
            f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>').encode()

def flood(path, mib):
    """Write a DOCX with approximately mib MiB of repeated paragraph XML."""
    unit = "<w:p><w:r><w:t>a</w:t></w:r></w:p>"
    reps = mib * 1024 * 1024 // len(unit)
    pack(path, doc("<w:p><w:r><w:t>FLOOD_START</w:t></w:r></w:p>" + unit * reps + "<w:p><w:r><w:t>FLOOD_END</w:t></w:r></w:p>"))

def sdt_chain(n):
    """Return XML nesting a leaf paragraph inside n content controls."""
    s = "<w:p><w:r><w:t>DEEP_LEAF</w:t></w:r></w:p>"
    for _ in range(n):
        s = f"<w:sdt><w:sdtContent>{s}</w:sdtContent></w:sdt>"
    return s

def tbl_chain(n):
    """Return XML nesting a leaf paragraph inside n tables."""
    s = "<w:p><w:r><w:t>TBL_LEAF</w:t></w:r></w:p>"
    for _ in range(n):
        s = f"<w:tbl><w:tr><w:tc>{s}</w:tc></w:tr></w:tbl><w:p/>"
    return s

def main():
    """Build experiment fixtures under FIX and print their sizes."""
    FIX.mkdir(exist_ok=True)
    canary = (EXP / "canary.txt").as_uri()
    for bid, p in make_bombs.build(FIX, canary).items():
        print(bid, p.stat().st_size)
    OK = "<w:p><w:r><w:t>BODY_OK</w:t></w:r></w:p>"
    for name, mib in [("E1_flood1", 1), ("E2_flood8", 8), ("E3_flood60", 60), ("E4_flood70", 70)]:
        flood(FIX / f"{name}.docx", mib)
    for n in (200, 300, 600):
        pack(FIX / f"D_sdt{n}.docx", doc(OK + sdt_chain(n)))
    for n in (60, 200, 300):
        pack(FIX / f"D_tbl{n}.docx", doc(OK + tbl_chain(n)))
    pack(FIX / "X1_doctype.docx", doc(OK, "<!DOCTYPE w:document>"))
    pack(FIX / "X2_entity.docx", doc("<w:p><w:r><w:t>ENT[&a;]</w:t></w:r></w:p>", '<!DOCTYPE w:document [<!ENTITY a "EXPANDED">]>'))
    # '>' inside the internal subset: a naive skip-to-first-'>' ends inside the entity value
    pack(FIX / "X3_subset_gt.docx",
         doc(OK, '<!DOCTYPE w:document [<!ENTITY a "<w:p><w:r><w:t>SMUGGLED</w:t></w:r></w:p>">]>'))
    pack(FIX / "C0_control.docx", doc(OK))
    for p in sorted(FIX.glob("*.docx")):
        print(p.name, p.stat().st_size)

main()
