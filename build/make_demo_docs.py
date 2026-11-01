#!/usr/bin/env python3
"""Sanitized copies of fixture/complex.docx for the live editor demos on benchmarks.law.

usage: python3 build/make_demo_docs.py [OUT_DIR]      (default out/demo)

Writes OUT_DIR/<editor>.docx and OUT_DIR/<editor>.json for every editor in EDITORS.

The scored fixture is adversarial on purpose. A demo has to open in each editor's browser build,
so every copy goes through BASE_STEPS, which turn the two parts that carry a foreign payload into
ordinary WordprocessingML:

  altchunk_to_paragraphs   the altChunk (an HTML part the consumer must import) becomes ordinary
                           paragraphs with the same text
  ole_to_picture           the OLE-embedded .docx becomes the icon picture Word shows for it

Everything else (tracked changes, moves, comments, notes, fields, tables, SmartArt, the chart and its
workbook, headers, footers, sections) is kept byte for byte. An editor that still cannot open its copy
gets extra steps in EDITORS, each with a reason; the .json manifest lists what was removed so the site
can say so next to the demo, and links the scored original.
"""
import hashlib
import html
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixture" / "complex.docx"

DOC = "word/document.xml"
DOC_RELS = "word/_rels/document.xml.rels"
CT = "[Content_Types].xml"


def _rel(rels: str, rid: str) -> tuple[str, str]:
    m = re.search(rf'<Relationship [^>]*Id="{re.escape(rid)}"[^>]*/>', rels)
    if not m:
        raise ValueError(f"relationship {rid} not found")
    target = re.search(r'Target="([^"]*)"', m.group(0)).group(1)
    return m.group(0), "word/" + target if not target.startswith("/") else target.lstrip("/")


def altchunk_to_paragraphs(p: dict) -> dict:
    doc, rels = p[DOC].decode(), p[DOC_RELS].decode()
    m = re.search(r'<w:altChunk r:id="([^"]+)"\s*/>', doc)
    if not m:
        return {}
    rel, part = _rel(rels, m.group(1))
    texts = [html.unescape(re.sub(r"<[^>]+>", "", t)).strip() for t in re.findall(r"<p[^>]*>([\s\S]*?)</p>", p[part].decode())]
    paras = "".join(f"<w:p><w:r><w:t>{html.escape(t, quote=False)}</w:t></w:r></w:p>" for t in texts if t)
    p[DOC] = (doc[: m.start()] + paras + doc[m.end():]).encode()
    p[DOC_RELS] = rels.replace(rel, "").encode()
    del p[part]
    return {"what": f"the altChunk ({part}, an HTML part) is replaced by {len(texts)} ordinary paragraphs with the same text",
            "why": "an altChunk asks the consumer to import foreign HTML; most browser editors drop or reject it"}


def ole_to_picture(p: dict) -> dict:
    doc, rels = p[DOC].decode(), p[DOC_RELS].decode()
    m = re.search(r"<w:object\b[^>]*>([\s\S]*?)</w:object>", doc)
    if not m:
        return {}
    inner = m.group(1)
    shape = re.search(r"<v:shape\b[\s\S]*?</v:shape>", inner)
    ole = re.search(r'<o:OLEObject\b[^>]*r:id="([^"]+)"[^>]*/>', inner)
    if not shape or not ole:
        raise ValueError("w:object without a v:shape icon and an o:OLEObject")
    rel, part = _rel(rels, ole.group(1))
    p[DOC] = (doc[: m.start()] + "<w:pict>" + shape.group(0) + "</w:pict>" + doc[m.end():]).encode()
    p[DOC_RELS] = rels.replace(rel, "").encode()
    del p[part]
    return {"what": f"the OLE-embedded document ({part}) is replaced by the icon picture Word shows for it",
            "why": "an embedded OLE package is an opaque binary a browser editor cannot open"}


STEPS = {"altchunk_to_paragraphs": altchunk_to_paragraphs, "ole_to_picture": ole_to_picture}
BASE_STEPS = ["altchunk_to_paragraphs", "ole_to_picture"]

# Extra steps per editor, added only with evidence that the editor's browser build cannot open the base copy.
EDITORS: dict[str, list[str]] = {
    "superdoc": [], "eigenpal": [], "folio": [], "plate": [], "canvas-editor": [], "docen": [],
    "genoffice": [], "docxodus": [], "wordcraft": [], "fidus-writer": [], "docs-plus": [], "office-open": [],
}


def _drop_unused_overrides(p: dict) -> None:
    """Drop an Override naming a removed part. Default extensions stay: an unused one is harmless."""
    ct = p[CT].decode()
    ct = re.sub(r'<Override [^>]*PartName="/([^"]+)"[^>]*/>', lambda m: m.group(0) if m.group(1) in p else "", ct)
    p[CT] = ct.encode()


def sanitize(data: bytes, steps: list[str]) -> tuple[bytes, list[dict]]:
    fns = [STEPS[s] for s in steps]  # KeyError on an unknown step, before anything runs
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        order = z.namelist()
        p = {n: z.read(n) for n in order}
    removed = []
    for name, fn in zip(steps, fns):
        r = fn(p)
        if r:
            removed.append({"step": name, **r})
    _drop_unused_overrides(p)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in [CT] + [n for n in order if n != CT and n in p]:
            z.writestr(n, p[n])
    return out.getvalue(), removed


def build(fixture: Path, out_dir: Path, editors: dict[str, list[str]]) -> None:
    src = fixture.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)
    for slug, extra in editors.items():
        data, removed = sanitize(src, BASE_STEPS + extra)
        (out_dir / f"{slug}.docx").write_bytes(data)
        (out_dir / f"{slug}.json").write_text(json.dumps({
            "editor": slug,
            "source": "fixture/complex.docx",
            "source_sha256": hashlib.sha256(src).hexdigest(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "removed": removed,
        }, indent=2) + "\n")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "demo"
    build(FIXTURE, out, EDITORS)
    print(f"{len(EDITORS)} demo documents in {out}")
