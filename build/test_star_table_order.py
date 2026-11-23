"""The selection table in the main report is in star order, as its paragraph says (CodeAnt on PR #292).

The star counts are facts re-measured each release while the rows are fixed in the template,
so a re-measure can put two rows out of order; this catches it in the rendered report."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md"


def star_column() -> list[int]:
    lines = REPORT.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("| Project | ★ |"))
    stars = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        stars.append(int(re.sub(r"[^\d]", "", line.split("|")[2])))
    return stars


def test_rows_descend_by_stars():
    stars = star_column()
    assert len(stars) > 10
    out = [(a, b) for a, b in zip(stars, stars[1:]) if a < b]
    assert not out, f"a row with fewer stars sits above one with more: {out}"
