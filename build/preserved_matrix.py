#!/usr/bin/env python3
"""Rebuild the preserved-vs-dropped matrix in the main report from the measurement.

The matrix in the main write-up is a grid of claims about twelve editors. A
grid that large drifts when it is edited by hand, so this script derives every
cell from the same per-tool score.json files the scorer writes, and prints the
row that replaces the hand-written one.

A cell is P when the construct's checks all pass, D when one of them fails,
and ? when no check covers the row. The parenthetical is the count the check
itself reported, when the check reports one.

Usage:
    python3 build/preserved_matrix.py            # print the table
    python3 build/preserved_matrix.py --patch "<report.md>"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

# display name, output dir
TOOLS = [
    ("SuperDoc", "superdoc"),
    ("Docxodus", "docxodus"),
    ("Folio", "folio"),
    ("GenOffice", "genoffice"),
    ("eigenpal", "eigenpal"),
    ("office-open", "officeopen"),
    ("Docen", "docen"),
    ("WordCraft", "wordcraft"),
    ("canvas", "canvas"),
    ("Fidus", "fidus"),
    ("docs.plus", "docsplus"),
    ("Plate.js", "plate"),
    ("Apryse", "apryse"),
]

# label -> list of check ids that cover it. A row with no check is left alone.
ROWS = [
    ("Unknown attributes (`w14:paraId`, `textId`)", ["unknown w14 attributes kept"]),
    ("`w16du:dateUtc`", ["w16du:dateUtc kept"]),
    ("`w16du` namespace declaration", ["w16du namespace declaration kept"]),
    ("`xml:space=\"preserve\"`", ["significant leading/trailing whitespace preserved"]),
    ("`w:proofErr`", ["w:proofErr kept"]),
    ("`mc:AlternateContent` Choice **and** Fallback", ["mc:AlternateContent kept (Choice+Fallback)"]),
    ("`w:ins` / `w:del` runs", ["w:ins runs kept", "w:del runs kept"]),
    ("`w:rPrChange` / `w:pPrChange`", ["w:rPrChange kept", "w:pPrChange kept"]),
    ("`w:moveFrom` / `w:moveTo`", ["w:moveFrom kept with w:t, not w:delText", "w:moveTo kept"]),
    ("Row-level revisions (`w:trPr/w:ins`, `w:trPr/w:del`)",
     ["inserted table row (trPr/ins) kept", "deleted table row (trPr/del) kept"]),
    ("Complex fields (`fldChar`/`instrText`)",
     ["complex field (w:fldChar) kept", "field instruction (w:instrText) kept"]),
    ("Simple fields (`w:fldSimple`)", ["simple fields kept (as simple or complex fields)"]),
    ("Bookmarks", ["bookmark kept"]),
    ("Content controls (`w:sdt`)", ["content controls kept (>=5)"]),
    ("`w:dataBinding`, date picker, nested sdt",
     ["w:dataBinding kept", "date-picker content control kept", "nested content control kept"]),
    ("Tables: `tblGrid`, `gridSpan`, `vMerge`",
     ["tblGrid kept", "table gridSpan kept", "table vMerge kept"]),
    ("Nested table", ["nested table kept"]),
    ("Section count (3) and landscape", ["all 3 sections kept", "landscape section kept"]),
    ("Page borders / multi-column / `docGrid`",
     ["page borders kept", "multi-column section kept", "docGrid kept"]),
    ("RTL (`w:bidi` / `w:rtl`)", ["RTL paragraph (w:bidi) kept", "RTL run (w:rtl) kept"]),
    ("`w:sym`, `w:tab`, `w:br`, hyphens",
     ["w:sym symbol kept", "w:tab kept", "w:br kept", "noBreakHyphen/softHyphen kept"]),
    ("`w:vanish`, `w:noProof`, `vertAlign`",
     ["hidden text (w:vanish) kept", "w:noProof kept", "w:vertAlign kept"]),
    ("9-level `numbering.xml`", ["9-level numbering definition kept"]),
    ("Chart part", ["chart part kept"]),
    ("SmartArt parts (4)", ["SmartArt/diagram parts kept"]),
    ("OLE object + embedded workbook", ["OLE object part kept", "embedded workbook kept"]),
    ("Image", ["embedded image (word/media)"]),
    ("Headers/footers (2 + 2)",
     ["part kept: header (default)", "part kept: header (first page)",
      "part kept: footer (default)", "part kept: footer (first page)"]),
    ("Tracked change inside a header", ["tracked change inside header kept"]),
    ("Footnotes / endnotes / comments",
     ["part kept: footnotes.xml", "part kept: endnotes.xml", "part kept: comments.xml",
      "footnote body text kept", "endnote body text kept", "comment body text kept"]),
    ("`documentProtection`, `evenAndOddHeaders`",
     ["settings.xml documentProtection kept", "evenAndOddHeaders kept"]),
    ("`w:altChunk` (element + part + text)",
     ["part kept: altChunk part", "altChunk relationship resolves, or content imported"]),
    ("Glossary / building blocks", ["part kept: glossary/building blocks"]),
    ("customXml data store", ["part kept: customXml data store"]),
    ("`docProps/core.xml` metadata", ["core properties kept"]),
    ("Chart / SmartArt relationships resolve to a part",
     ["chart relationship resolves to a part", "SmartArt relationships resolve to parts"]),
    ("Output re-opens as a well-formed package",
     ["ZIP package opens, CRC valid", "word/document.xml present and well-formed"]),
]


def load(tool_dir: str) -> dict:
    """Return {check label: (pass, detail)} for one tool's score.json."""
    path = OUT / tool_dir / "score.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {c["label"]: (bool(c["pass"]), c.get("detail", "")) for c in data["checks"]}


def expected_counts(results: dict) -> dict:
    """Return {check label: expected count} for the checks that report one.

    The input's count is the largest count any tool reported for that check,
    so a tool that kept fewer is described as "K of N" rather than a bare "D".
    """
    counts: dict[str, int] = {}
    for res in results.values():
        for label, (_ok, detail) in res.items():
            m = re.fullmatch(r"n=(\d+)", detail.strip())
            if m:
                n = int(m.group(1))
                counts[label] = max(counts.get(label, 0), n)
    return counts


def cell(res: dict, ids: list[str], counts: dict) -> str:
    """Return one matrix cell: P, D, or D with a parenthetical."""
    known = [i for i in ids if i in res]
    if not known:
        return "?"
    bad = [i for i in known if not res[i][0]]
    if not bad:
        return "P"
    label = bad[0]
    detail = res[label][1].strip()
    m = re.fullmatch(r"n=(\d+)", detail)
    if m and counts.get(label):
        return f"**D** ({m.group(1)} of {counts[label]})"
    if "Hyphen" in label:
        return "**D** (hyphens)"
    if "moveFrom" in label:
        return "**D** (moveFrom)"
    if "AlternateContent" in label:
        return "**D** (Choice only)"
    if "paraId=0" in detail:
        return "**D** (paraId)"
    return "**D**"


def build_table() -> str:
    """Return the markdown table of the matrix."""
    results = {name: load(d) for name, d in TOOLS}
    counts = expected_counts(results)
    head = "| Item | " + " | ".join(name for name, _ in TOOLS) + " |"
    rule = "|---" * (len(TOOLS) + 1) + "|"
    lines = [head, rule]
    for label, ids in ROWS:
        cells = [cell(results[name], ids, counts) for name, _ in TOOLS]
        lines.append("| " + label + " | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> int:
    """Print the derived table, or patch it into the report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", default=None, help="report markdown to patch in place")
    args = parser.parse_args()
    table = build_table()
    if not args.patch:
        print(table)
        return 0
    path = Path(args.patch)
    text = path.read_text(encoding="utf-8")
    start = text.index("| Item | ")
    end = text.index("\n\n", start)
    new = text[:start] + table + text[end:]
    path.write_text(new, encoding="utf-8")
    print("patched:", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
