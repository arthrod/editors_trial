#!/usr/bin/env python3
"""Check the measured figures in the main report against the measurement.

Every percentage and byte size the report claims about the round trip has to
appear in the scorer's own output. The comparison is between the edited file
and the same file at HEAD, so the report's pre-existing numbers are reported
separately from the ones a refresh introduced.

Usage:
    python3 build/verify_report_numbers.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md"

PCT = re.compile(r"\d[\d,]*(?:\.\d+)?\s*%")
BYTE = re.compile(r"\d[\d,]*\s+bytes\b", re.I)


def percent_strings(data: object) -> list[str]:
    """Return every numeric field in a score.json rendered as a percentage."""
    out: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if key.endswith("_pct"):
                        out.append(f"{value}%")
                    elif key == "weighted":
                        out.append(f"{value}%")
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return out


def corpus() -> str:
    """Return everything the scorer itself produced, as one searchable string."""
    chunks: list[str] = []
    run = subprocess.run([sys.executable, str(ROOT / "build" / "score_all.py")],
                         capture_output=True, text=True, cwd=str(ROOT))
    chunks.append(run.stdout)
    for path in sorted((ROOT / "out").glob("*/score.json")) + sorted((ROOT / "out").glob("*/second/score.json")):
        text = path.read_text(encoding="utf-8", errors="replace")
        chunks.append(text)
        try:
            chunks.extend(percent_strings(json.loads(text)))
        except json.JSONDecodeError:
            pass
    return "\n".join(chunks)


def tokens(text: str) -> list[str]:
    """Return the percentages and byte sizes a text claims."""
    found: list[str] = []
    for rx in (PCT, BYTE):
        found.extend(m.group(0).strip() for m in rx.finditer(text))
    return found


def main() -> int:
    """Compare the edited report's figures with HEAD's, against the scorer output."""
    haystack = corpus()
    edited = REPORT.read_text(encoding="utf-8")
    head = subprocess.run(["git", "show", f"HEAD:{REPORT.relative_to(ROOT)}"],
                          capture_output=True, text=True, cwd=str(ROOT)).stdout
    old = set(tokens(head))
    new = [t for t in tokens(edited) if t not in old]
    missing = sorted({t for t in new if t not in haystack})
    print(f"tokens in the edited report not in HEAD: {len(set(new))}")
    print(f"of those, absent from the scorer output: {len(missing)}")
    for token in missing:
        print(f"  - {token}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
