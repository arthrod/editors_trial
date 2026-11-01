#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=11"]
# ///
"""
Report C §6.2: every output as LIBREOFFICE renders it, against LibreOffice's
rendering of the corpus. Used for the outputs Word refuses, where it is the only
rendering available, and kept for every output as a second engine.

Each package goes through `soffice --convert-to pdf`, each page is rasterised
with `pdftoppm` at build/pixels.py's resolution (out/render/lo_png), and the
pages are compared with render_compare_word.py's own diff() and ink(), with its
thresholds. Until v0.9.2 this table had no script; this one reproduces its figures.

usage: uv run --script build/lo_render_compare.py [tool ...]   # default: every output
writes out/render/lo/<tool>/doc.pdf, out/render/lo_png/<tool>-N.png,
       out/render/lo_render_compare.json
"""
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixels  # noqa: E402  (build/pixels.py: the release resolution)

BASE = "/Users/arthrod/temp/T/editors_trial"
RENDER = os.path.join(BASE, "out", "render")
RCW = runpy.run_path(os.path.join(BASE, "build", "render_compare_word.py"), run_name="lo")
diff, ink, pages = RCW["diff"], RCW["ink"], RCW["pages"]

# label in the JSON (and the PNG name), output package
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


def render(label, rel, lo_dir, png_dir):
    out = os.path.join(lo_dir, label)
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "doc.docx")
        shutil.copy(os.path.join(BASE, rel), src)
        prof = "-env:UserInstallation=file://" + os.path.join(tmp, "profile")
        subprocess.run(["soffice", prof, "--headless", "--norestore", "--convert-to", "pdf",
                        "--outdir", out, src], check=True, capture_output=True, timeout=300)
    for old in os.listdir(png_dir):
        if old.startswith(label + "-") and old[len(label) + 1:-4].isdigit():
            os.remove(os.path.join(png_dir, old))
    subprocess.run(["pdftoppm", "-r", str(pixels.DPI), "-png", os.path.join(out, "doc.pdf"),
                    os.path.join(png_dir, label)], check=True)
    # pdftoppm pads page numbers when there are 10+ pages; the corpus has 6
    return pages(png_dir, label)


def verdict(pct):
    return ("pixel-identical" if pct < 0.5 else "very close" if pct < 5
            else "close" if pct < 25 else "different")


def compare(ref, op):
    total = 0
    for i, rp in enumerate(ref):
        if i >= len(op):
            return None
        r = diff(rp, op[i])
        if r.get("size_mismatch"):
            return None
        total += r["diff_px"]
    return total


def main(argv):
    lo_dir, png_dir = os.path.join(RENDER, "lo"), os.path.join(RENDER, "lo_png")
    os.makedirs(png_dir, exist_ok=True)
    want = set(argv) or {l for l, _ in TARGETS}
    path = os.path.join(RENDER, "lo_render_compare.json")
    rows = json.load(open(path)) if os.path.exists(path) else {}
    ref = render("corpus", "fixture/complex.docx", lo_dir, png_dir)
    cin = sum(ink(p) for p in ref)
    for label, rel in TARGETS:
        if label == "corpus" or label not in want or not os.path.exists(os.path.join(BASE, rel)):
            continue
        op = render(label, rel, lo_dir, png_dir)
        total = compare(ref, op) if len(op) == len(ref) else None
        if total is None:  # a different page count has no page-for-page comparison
            rows[label] = {"pages": len(op), "diff": None, "pct": None, "verdict": "different"}
        else:
            pct = round(total / cin * 100, 2)
            rows[label] = {"pages": len(op), "diff": total, "pct": pct, "verdict": verdict(pct)}
        print("%-12s %s" % (label, rows[label]))
    with open(path, "w") as f:
        json.dump(rows, f, indent=1)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
