#!/usr/bin/env python3
"""LibreOffice baseline pixel diffs for full-browser perf (200 dpi via build/pixels.py)."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "build"))
import pixels  # noqa: E402

DEFAULT_LO_BASELINE = REPO / "perf/out/lo_pixels_2026_11_07"
LO_CORPUS_STEM = "complex_corpus"
BROWSER_EDITORS = ("plate", "docxodus", "superdoc", "genoffice", "canvas")


def resolve_pixels_root(out_root: Path) -> Path:
    """Accept full-browser out root or an existing pixels/ directory."""
    if out_root.name == "pixels" or (out_root / "diff_vs_lo").is_dir():
        return out_root
    return out_root / "pixels"


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_compare_api():
    rcw = runpy.run_path(str(REPO / "build/render_compare_word.py"), run_name="perf_pixels_lo")
    return rcw["diff"], rcw["ink"]


def write_diff_png(ref_png: Path, op_png: Path, out_path: Path, thresh: int = 8) -> None:
    from PIL import Image, ImageChops

    ref = Image.open(ref_png).convert("RGB")
    op = Image.open(op_png).convert("RGB")
    if ref.size != op.size:
        canvas = Image.new("RGB", (ref.size[0] * 2 + 12, max(ref.size[1], op.size[1])), "white")
        canvas.paste(ref, (0, 0))
        canvas.paste(op, (ref.size[0] + 12, 0))
        canvas.save(out_path)
        return
    mask = ImageChops.difference(ref, op).convert("L").point(lambda v: 255 if v > thresh else 0)
    highlight = Image.new("RGB", ref.size, (255, 255, 255))
    overlay = Image.new("RGB", ref.size, (255, 0, 0))
    highlight.paste(overlay, mask=mask)
    canvas = Image.new("RGB", (ref.size[0] * 2 + 12, ref.size[1]), "white")
    canvas.paste(ref, (0, 0))
    canvas.paste(highlight, (ref.size[0] + 12, 0))
    canvas.save(out_path)


def baseline_corpus_page1(baseline_root: Path) -> Path | None:
    p = baseline_root / "png" / f"{LO_CORPUS_STEM}-1.png"
    return p if p.is_file() else None


def editor_page1_png(baseline_root: Path, editor_id: str) -> Path | None:
    if editor_id == "plate":
        p = baseline_root / "png" / "complex_plate-1.png"
        if p.is_file():
            return p
    return None


def rasterize_editor_page1(editor_id: str, work_png_dir: Path) -> tuple[Path | None, int]:
    """Rasterise out/<editor>/complex.docx via LibreOffice when baseline cache is missing."""
    from perf.run_lo_pixels_baseline import rasterize

    docx = REPO / "out" / editor_id / "complex.docx"
    if not docx.is_file():
        return None, 0
    label = f"full_browser_{editor_id}"
    pngs, _ = rasterize(docx, label, work_png_dir)
    if not pngs:
        return None, 0
    return Path(pngs[0]), len(pngs)


def compare_plate_page1(
    pixels_root: Path,
    baseline_root: Path,
    diff_fn,
    ink_fn,
) -> dict:
    lo_ref = baseline_corpus_page1(baseline_root)
    if lo_ref is None:
        raise FileNotFoundError(f"missing LO baseline page1 under {baseline_root}")

    editor_id = "plate"
    plate_pages = pixels_root / editor_id / "pages"
    plate_pages.mkdir(parents=True, exist_ok=True)
    diff_dir = pixels_root / "diff_vs_lo" / editor_id
    diff_dir.mkdir(parents=True, exist_ok=True)

    lo_page_count = len(list((baseline_root / "png").glob(f"{LO_CORPUS_STEM}-*.png")))
    op_png, op_page_count = editor_page1_png(baseline_root, editor_id), 0
    op_input = REPO / "out/plate/complex.docx"

    if op_png is not None:
        op_page_count = len(list((baseline_root / "png").glob("complex_plate-*.png")))
    else:
        work = pixels_root / "lo_baseline" / "png"
        op_png, op_page_count = rasterize_editor_page1(editor_id, work)
        if op_png is None:
            raise FileNotFoundError(f"no plate page-1 raster for {editor_id}")

    lo_copy = plate_pages / "lo-ref-page-1.png"
    op_copy = plate_pages / "page-1.png"
    shutil.copy2(lo_ref, lo_copy)
    shutil.copy2(op_png, op_copy)

    metrics = diff_fn(str(lo_ref), str(op_png))
    page1_only = lo_page_count != op_page_count or metrics.get("size_mismatch")
    diff_px = metrics.get("diff_px")
    if diff_px is None and metrics.get("size_mismatch"):
        diff_px = metrics["size_a"][0] * metrics["size_a"][1]

    diff_png = diff_dir / "page-1-diff.png"
    write_diff_png(lo_ref, op_png, diff_png)

    payload = {
        "editor_id": editor_id,
        "dpi": pixels.DPI,
        "page1_only": page1_only,
        "differing_pixels": diff_px,
        "diff_px": diff_px,
        "page_counts": {"lo_corpus": lo_page_count, editor_id: op_page_count},
        "page_compared": 1,
        "inputs": {
            "lo_ref": repo_rel(lo_ref),
            "editor_docx": repo_rel(op_input) if op_input.is_file() else None,
            "editor_page_png": repo_rel(op_png),
        },
        "lo_baseline_root": repo_rel(baseline_root),
        "image_size": list(metrics.get("size") or metrics.get("size_a") or []),
        "diff_bbox": metrics.get("bbox"),
        "corpus_ink_px": ink_fn(str(lo_ref)),
        "artifacts": {
            "editor_page": repo_rel(op_copy),
            "lo_ref_page": repo_rel(lo_copy),
            "diff_png": repo_rel(diff_png),
        },
    }
    if page1_only:
        payload["full_document_compare_impossible"] = (
            f"LO raster of fixture/complex.docx has {lo_page_count} pages; "
            f"{editor_id} output has {op_page_count}."
        )
    (diff_dir / "metrics.json").write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def write_skipped_metrics(pixels_root: Path, editor_id: str, reason: str) -> None:
    diff_dir = pixels_root / "diff_vs_lo" / editor_id
    diff_dir.mkdir(parents=True, exist_ok=True)
    (pixels_root / editor_id / "pages").mkdir(parents=True, exist_ok=True)
    (diff_dir / "metrics.json").write_text(
        json.dumps(
            {
                "editor_id": editor_id,
                "dpi": pixels.DPI,
                "outcome": "skipped",
                "reason": reason,
            },
            indent=2,
        )
        + "\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument(
        "--lo-baseline",
        type=Path,
        default=DEFAULT_LO_BASELINE,
        help="Directory with LO corpus PNGs (default: perf/out/lo_pixels_2026_11_07)",
    )
    args = parser.parse_args()

    pixels_root = resolve_pixels_root(args.out_root)
    pixels_root.mkdir(parents=True, exist_ok=True)
    baseline_root = args.lo_baseline.resolve()
    if not baseline_root.is_dir():
        print(f"LO baseline missing: {baseline_root}", file=sys.stderr)
        return 1

    diff_fn, ink_fn = load_compare_api()
    log_lines: list[str] = []

    try:
        plate_metrics = compare_plate_page1(pixels_root, baseline_root, diff_fn, ink_fn)
        log_lines.append(
            f"plate page-1 diff_px={plate_metrics.get('diff_px')} dpi={pixels.DPI}"
        )
    except OSError as exc:
        (pixels_root / "lo_render.log").write_text(str(exc) + "\n")
        print(exc, file=sys.stderr)
        return 1

    for editor in BROWSER_EDITORS:
        if editor == "plate":
            continue
        docx = REPO / "out" / editor / "complex.docx"
        if docx.is_file():
            write_skipped_metrics(
                pixels_root,
                editor,
                "page-1 LO diff not run in this pass; plate comparison is the gate artifact",
            )
        else:
            write_skipped_metrics(pixels_root, editor, f"missing {repo_rel(docx)}")

    (pixels_root / "lo_render.log").write_text("\n".join(log_lines) + "\n")

    browser_root = pixels_root.parent if pixels_root.name == "pixels" else pixels_root
    summary_path = browser_root / "pixels_summary.json"
    summary = {
        "suite": "pixels_lo",
        "dpi": pixels.DPI,
        "lo_baseline": repo_rel(baseline_root),
        "comparisons": [
            {
                "editor_id": "plate",
                "diff_px": plate_metrics.get("diff_px"),
                "page1_only": plate_metrics.get("page1_only"),
            }
        ],
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
