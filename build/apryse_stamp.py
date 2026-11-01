#!/usr/bin/env python3
"""
Identify Apryse's trial stamp in its output, and say which failed checks it
could have caused. The output is never edited: the score stays the score of
the file Apryse wrote, and this file only labels it.

A trial license makes WebViewer anchor a watermark picture (docPr name
"trn_d_stamp") in every header, adding header parts to carry it. So a failed
check that concerns a header part or a header reference cannot be separated
from the stamp; every other failure is the editor's own.

usage: python3 -I build/apryse_stamp.py [out/apryse]   # writes <dir>/stamp.json
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK = "trn_d_stamp"
HEADER = re.compile(r"header", re.I)


def stamp_parts(data: bytes) -> list[str]:
    """Header parts carrying the stamp, their relationship parts, and the images those name."""
    found: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = set(zf.namelist())
        for name in names:
            if not re.fullmatch(r"word/header\d+\.xml", name):
                continue
            if MARK not in zf.read(name).decode("utf-8", "replace"):
                continue
            found.add(name)
            rels = f"word/_rels/{name.split('/')[-1]}.rels"
            if rels in names:
                found.add(rels)
                for target in re.findall(r'Target="([^"]+)"', zf.read(rels).decode("utf-8", "replace")):
                    part = f"word/{target}" if not target.startswith("/") else target.lstrip("/")
                    if part in names and part.startswith("word/media/"):
                        found.add(part)
    return sorted(found)


def attribute(checks: list[dict], stamped: bool) -> dict[str, list[str]]:
    """Split failed checks into those the stamp could have caused and the editor's own."""
    unseparable, own = [], []
    for check in checks:
        if check.get("pass"):
            continue
        about_headers = HEADER.search(check["id"]) or HEADER.search(check.get("label", ""))
        (unseparable if stamped and about_headers else own).append(check["id"])
    return {"unseparable": unseparable, "own": own}


def main() -> int:
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "apryse"
    data = (d / "complex.docx").read_bytes()
    parts = stamp_parts(data)
    result = {"stamp_parts": parts, "stamped": bool(parts)}
    score = d / "score.json"
    if score.exists():
        checks = json.loads(score.read_text())["checks"]
        result.update(attribute(checks, bool(parts)))
        labels = {c["id"]: c["label"] for c in checks}
        result["labels"] = {k: labels[k] for k in result["unseparable"] + result["own"]}
    (d / "stamp.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
