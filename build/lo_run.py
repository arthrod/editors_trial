#!/usr/bin/env python3
"""Run LibreOffice against the bombs inside a container. Prints score lines."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/opt")
import bomb_score
import make_bombs


def main() -> int:
    canary = Path("/tmp/xxe-canary.txt")
    canary.write_text(bomb_score.CANARY + "\n", encoding="utf-8")
    mounted = Path("/bombs")
    if mounted.is_dir() and any(mounted.glob("B*.docx")):
        built = {path.stem: path for path in sorted(mounted.glob("B*.docx"))}
    else:
        built = make_bombs.build(Path("/tmp/bombs"), "file:///tmp/xxe-canary.txt")
    ids = sys.argv[1:] or list(built)
    for bid in ids:
        print(f"BEGIN {bid}", flush=True)
        out = Path("/tmp/out") / bid
        out.mkdir(parents=True, exist_ok=True)
        prof = Path("/tmp/profile") / bid
        prof.mkdir(parents=True, exist_ok=True)
        command = [
            "soffice",
            "--headless",
            "--norestore",
            "--nologo",
            "--nofirststartwizard",
            f"-env:UserInstallation=file://{prof}",
            "--convert-to",
            "docx",
            "--outdir",
            str(out),
            str(built[bid]),
        ]
        print("CMD " + " ".join(command), file=sys.stderr, flush=True)
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            code = proc.returncode
            timed = False
            out_text = proc.stdout or ""
            err_text = proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            code = 124
            timed = True
            out_text = exc.stdout or ""
            err_text = exc.stderr or ""
        produced = [p for p in out.glob("*.docx") if p.is_file()]
        data = produced[0].read_bytes() if produced else None
        text = data.decode("utf-8", "replace") if data else ""
        leak = bomb_score.leaked_text(text)
        slips = [p for p in Path("/tmp").rglob(make_bombs.SLIP_NAME) if out not in p.parents]
        leak = leak or bool(slips)
        fid = bomb_score.fidelity(bid, data)
        safe = bomb_score.safety(code, timed, leak)
        produced_desc = ", ".join(f"{p.name} size={p.stat().st_size}" for p in produced) or "none"
        slip_desc = ", ".join(str(p) for p in slips) or "none"
        print(f"EXIT {code} timed_out={timed}", file=sys.stderr, flush=True)
        print(f"PRODUCED {produced_desc}", file=sys.stderr, flush=True)
        print(f"LEAK {leak} slips={slip_desc}", file=sys.stderr, flush=True)
        print("SOFFICE_STDOUT_BEGIN", file=sys.stderr, flush=True)
        print(out_text, file=sys.stderr, flush=True)
        print("SOFFICE_STDOUT_END", file=sys.stderr, flush=True)
        print("SOFFICE_STDERR_BEGIN", file=sys.stderr, flush=True)
        print(err_text, file=sys.stderr, flush=True)
        print("SOFFICE_STDERR_END", file=sys.stderr, flush=True)
        print(bomb_score.line("comparison", "libreoffice", bid, fid, safe), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
