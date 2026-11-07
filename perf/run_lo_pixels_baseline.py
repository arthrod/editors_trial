#!/usr/bin/env python3
"""Rasterise DOCX fixtures with LibreOffice at build/pixels.DPI for CI baselines."""

from __future__ import annotations

import hashlib
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import pixels  # noqa: E402

RCW = runpy.run_path(str(ROOT / "build" / "render_compare_word.py"), run_name="lo_baseline")
diff = RCW["diff"]
ink = RCW["ink"]
pages = RCW["pages"]


def soffice_version() -> str:
    out = subprocess.run(["soffice", "--version"], capture_output=True, text=True, check=True)
    return out.stdout.strip() or out.stderr.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rasterize(docx: Path, label: str, png_dir: Path) -> tuple[list[str], Path]:
    png_dir.mkdir(parents=True, exist_ok=True)
    for old in png_dir.glob(f"{label}-*.png"):
        old.unlink()
    pdf_dir = png_dir / "pdf" / label
    pdf_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "doc.docx"
        shutil.copy(docx, src)
        prof = f"-env:UserInstallation=file://{tmp}/profile"
        subprocess.run(
            [
                "soffice",
                prof,
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf_dir),
                str(src),
            ],
            check=True,
            capture_output=True,
            timeout=300,
        )
    pdf = pdf_dir / "doc.pdf"
    if not pdf.is_file():
        raise FileNotFoundError(f"no PDF from {docx}")
    subprocess.run(
        ["pdftoppm", "-r", str(pixels.DPI), "-png", str(pdf), str(png_dir / label)],
        check=True,
    )
    pngs = [str(p) for p in pages(str(png_dir), label)]
    return pngs, pdf


def compare_page_lists(ref: list[str], op: list[str]) -> dict | None:
    if len(ref) != len(op):
        return {"page_mismatch": True, "ref_pages": len(ref), "op_pages": len(op)}
    total = 0
    for rp, op_path in zip(ref, op):
        r = diff(rp, op_path)
        if r.get("size_mismatch"):
            return {"size_mismatch": True}
        total += r["diff_px"]
    cin = sum(ink(p) for p in ref)
    pct = round(total / cin * 100, 2) if cin else None
    return {"diff_px": total, "corpus_ink_px": cin, "pct_of_corpus_ink": pct, "pages": len(ref)}


def main() -> int:
    out_root = ROOT / "perf" / "out" / "lo_pixels_2026_11_07"
    png_dir = out_root / "png"
    png_dir.mkdir(parents=True, exist_ok=True)

    fixtures = [
        ("micro", ROOT / "perf/out/unblocked_2026_11_07/micro-paragraphs.docx"),
        ("complex_corpus", ROOT / "fixture/complex.docx"),
    ]
    entries = []
    rasters: dict[str, list[str]] = {}

    ver = soffice_version()
    for label, path in fixtures:
        if not path.is_file():
            print(f"skip missing {path}", file=sys.stderr)
            continue
        pngs, pdf = rasterize(path, label, png_dir)
        entries.append(
            {
                "label": label,
                "input": str(path.relative_to(ROOT)),
                "input_sha256": sha256_file(path),
                "dpi": pixels.DPI,
                "page_count": len(pngs),
                "pdf": str(pdf.relative_to(ROOT)),
                "png_paths": [str(Path(p).relative_to(ROOT)) for p in pngs],
                "png_sha256": {Path(p).name: sha256_file(Path(p)) for p in pngs},
            }
        )
        rasters[label] = pngs
        print(f"{label}: {len(pngs)} pages @ {pixels.DPI} dpi")

    compare: dict = {}
    editor_docx = ROOT / "out/plate/complex.docx"
    if editor_docx.is_file() and "complex_corpus" in rasters:
        editor_label = "complex_plate"
        op_pngs, _ = rasterize(editor_docx, editor_label, png_dir)
        compare = {
            "ref_label": "complex_corpus",
            "op_label": editor_label,
            "op_input": str(editor_docx.relative_to(ROOT)),
            "metrics": compare_page_lists(rasters["complex_corpus"], op_pngs),
        }
        m = compare.get("metrics") or {}
        print(
            f"compare corpus vs plate: "
            f"diff_px={m.get('diff_px')} pct={m.get('pct_of_corpus_ink')}"
        )

    summary = {
        "soffice_version": ver,
        "dpi": pixels.DPI,
        "rasterized": entries,
        "compare": compare or None,
    }
    summary_path = out_root / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
