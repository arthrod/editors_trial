#!/usr/bin/env python3
"""Report D1's table of jubarte on the 33 Word-experiment fixtures (#69).

The table is generated from the measured TSV that the experiment's harness
(`run_jubarte_bin.sh`) writes: one line per fixture and command, with the
columns id, command, exit, peak MB, seconds, message. No figure is typed by
hand.

Usage:
    python3 -I build/wordexp_table.py logs/word-exp/results_jubarte_d1_0140.tsv
    python3 -I build/wordexp_table.py TSV --patch "templates/reports/Report D1 - Jubarte on the Hostile Packages (2026).md"
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

COMMANDS = ["read", "read_nopm", "validate", "compare"]
HEADINGS = ["read", "read, no page markers", "validate", "compare"]
BEGIN = "<!-- wordexp-table:begin (build/wordexp_table.py --patch) -->"
END = "<!-- wordexp-table:end -->"
CODE = re.compile(r"\b([A-Z][A-Z_]{4,})\b")


@dataclass
class Run:
    exit: str
    peak_mb: int
    secs: int
    message: str


def parse(text: str) -> dict[str, dict[str, Run]]:
    rows: dict[str, dict[str, Run]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        f = line.split("\t")
        if len(f) < 5:
            raise ValueError(f"short line: {line!r}")
        fid, cmd = f[0], f[1]
        if cmd not in COMMANDS:
            raise ValueError(f"unknown command {cmd!r} for {fid}")
        rows.setdefault(fid, {})[cmd] = Run(f[2].strip(), int(f[3]), int(f[4]), f[5] if len(f) > 5 else "")
    for fid, cmds in rows.items():
        missing = [c for c in COMMANDS if c not in cmds]
        if missing:
            raise ValueError(f"{fid}: no row for {', '.join(missing)}")
    return rows


def cell(r: Run) -> str:
    mb = f"{r.peak_mb:,} MB"
    if "KILLED" in r.exit:
        what = "300 s" if ">300s" in r.exit else "6 GB"
        return f"**killed at {what}**, {mb}"
    if r.exit == "0":
        return f"exit 0, {mb}"
    if r.exit == "101":
        return f"**panic (exit 101)**, {mb}"
    m = CODE.search(r.message.split(":", 1)[-1]) if "error" in r.message or "refused" in r.message else None
    return f"exit {r.exit}, {m.group(1)}, {mb}" if m else f"exit {r.exit}, {mb}"


def short(fid: str) -> str:
    """B6 stays B6; E3_flood60 becomes E3; X4c_customxml_control becomes X4c.
    The depth fixtures keep their name (D_sdt200): "D" alone names six files."""
    return fid if fid.startswith("D_") else fid.split("_", 1)[0]


def table(rows: dict[str, dict[str, Run]]) -> str:
    out = ["| Fixture | " + " | ".join(HEADINGS) + " |", "|---|" + "---|" * len(HEADINGS)]
    for fid, cmds in rows.items():
        out.append(f"| {short(fid)} | " + " | ".join(cell(cmds[c]) for c in COMMANDS) + " |")
    return "\n".join(out)


def patch(doc: str, body: str) -> str:
    if BEGIN not in doc or END not in doc:
        raise ValueError("markers not found")
    head, rest = doc.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{BEGIN}\n{body}\n{END}{tail}"


def patch_file(path: Path, tsv: str) -> None:
    path.write_text(patch(path.read_text(), table(parse(tsv))))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    tsv = Path(argv[0]).read_text()
    if len(argv) == 3 and argv[1] == "--patch":
        patch_file(Path(argv[2]), tsv)
        print(f"patched {argv[2]}")
    else:
        print(table(parse(tsv)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
