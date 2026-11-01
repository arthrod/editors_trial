#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow>=11"]
# ///
"""Compare a fresh set of Report C captures with the published ones, pixel by pixel.

usage: uv run --script build/compare_ui.py <old dir> <new dir>

Prints, per PNG present in both, the share of pixels that differ (any channel
by more than 16) and the bounding box of the difference. A capture is
"same" when under 0.1% of its pixels differ.
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops


def compare(a: Path, b: Path):
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        return None, f"size {ia.size} -> {ib.size}"
    diff = ImageChops.difference(ia, ib).convert("L").point(lambda v: 255 if v > 16 else 0)
    n = sum(1 for v in diff.getdata() if v)
    return n / (ia.size[0] * ia.size[1]), diff.getbbox()


def main() -> int:
    old, new = Path(sys.argv[1]), Path(sys.argv[2])
    for b in sorted(new.rglob("*.png")):
        a = old / b.relative_to(new)
        if not a.exists():
            print(f"NEW   {b.relative_to(new)}")
            continue
        share, box = compare(a, b)
        tag = "DIFF " if share is None or share >= 0.001 else "same "
        print(f"{tag} {b.relative_to(new)}  {'' if share is None else f'{share:.4%}'}  {box}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
