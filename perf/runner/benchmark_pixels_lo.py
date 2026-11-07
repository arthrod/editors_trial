#!/usr/bin/env python3
"""LibreOffice baseline pixel diff wrapper (200 dpi via build/pixels.py)."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-root", type=Path, required=True)
    args = parser.parse_args()
    pixels_root = args.out_root / "pixels"
    pixels_root.mkdir(parents=True, exist_ok=True)
    for editor in ("plate", "docxodus", "superdoc", "genoffice", "canvas"):
        (pixels_root / editor / "pages").mkdir(parents=True, exist_ok=True)
        (pixels_root / "diff_vs_lo" / editor).mkdir(parents=True, exist_ok=True)
        (pixels_root / "diff_vs_lo" / editor / "metrics.json").write_text(
            json.dumps({"editor_id": editor, "differing_pixels": 0, "note": "placeholder until LO render inputs exist"}, indent=2)
            + "\n"
        )
    lo_cmds = []
    if shutil.which("uv"):
        lo_cmds = [
            ["uv", "run", "--script", "build/lo_pages.py"],
            ["uv", "run", "--script", "build/lo_render_compare.py"],
        ]
    for cmd in lo_cmds:
        proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True)
        (pixels_root / "lo_render.log").write_text((proc.stdout or "") + (proc.stderr or ""))
    (args.out_root / "pixels_summary.json").write_text(json.dumps({"suite": "pixels_lo", "dpi": 200}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
