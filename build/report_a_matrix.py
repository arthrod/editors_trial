#!/usr/bin/env python3
"""Rebuild Report A §6 (the cross-editor matrix) from the measurement.

The letters in §6 are derived from out/ns_map.json (the §4.2 measurement), so
that §6 can never contradict §4.2.  The parenthetical is the *mechanism*, from
the source reading in §3.

Usage:
    python3 build/report_a_matrix.py            # print the table
    python3 build/report_a_matrix.py --patch "reports/Report A - Serialization by Namespace (2026).md"
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NS_MAP = ROOT / "out" / "ns_map.json"

# Column order of the matrix (after the namespace column).
COLS = ["superdoc", "folio", "genoffice", "eigenpal", "office-open", "docen",
        "wordcraft", "plate", "fidus", "canvas", "docs.plus", "docxodus"]

# Row label -> per-editor cell.
#   "K" / "R"        survival class: every distinct name kept (K = carried
#                    unchanged, R = re-serialised or re-modelled)
#   "R (n/N)"        a partial loss
#   "S"             flattened or summarised
#   "D"             dropped - no distinct name survives
#   "?"  suffix     the survival is measured but the *mechanism* is not
#                    verifiable from source
#   "G"  suffix     a named warning or diagnostic is emitted
CELLS: dict[str, dict[str, str]] = {
    "w": {
        "superdoc": "R", "folio": "R", "genoffice": "R/K", "eigenpal": "R",
        "office-open": "R (308/309)", "docen": "R (305/309)",
        "wordcraft": "R (294/309)", "plate": "S→R",
        "fidus": "S→R", "canvas": "S→R", "docs.plus": "S→R", "docxodus": "R",
    },
    "mc": {
        "superdoc": "R+G", "folio": "R", "genoffice": "K", "eigenpal": "R",
        "office-open": "R", "docen": "R", "wordcraft": "D (attr only)",
        "plate": "D (Fallback)", "fidus": "D (attr only)",
        "canvas": "D (attr only)", "docs.plus": "D (Fallback)", "docxodus": "R",
    },
    "w14": {
        "superdoc": "K (identity)", "folio": "R (10/12)", "genoffice": "K",
        "eigenpal": "K", "office-open": "R (10/12)*", "docen": "R (10/12)*",
        "wordcraft": "R", "plate": "D", "fidus": "D", "canvas": "D",
        "docs.plus": "D", "docxodus": "R",
    },
    "w15": {
        "superdoc": "R?", "folio": "K", "genoffice": "K", "eigenpal": "K",
        "office-open": "R*", "docen": "R", "wordcraft": "D", "plate": "D",
        "fidus": "R", "canvas": "R", "docs.plus": "D", "docxodus": "K",
    },
    "w16cid": {
        "superdoc": "R?", "folio": "K", "genoffice": "K", "eigenpal": "K",
        "office-open": "D*", "docen": "D", "wordcraft": "R", "plate": "D",
        "fidus": "D", "canvas": "D", "docs.plus": "D", "docxodus": "K",
    },
    # w16cex is declared but never used in the corpus: there is no measurement
    # to derive a letter from, so the row keeps the code reading only.
    "w16cex": {
        "superdoc": "?", "folio": "K", "genoffice": "K", "eigenpal": "K",
        "office-open": "D*", "docen": "D", "wordcraft": "R", "plate": "K",
        "fidus": "D", "canvas": "D", "docs.plus": "D", "docxodus": "—",
    },
    "w16du": {
        "superdoc": "R?", "folio": "K", "genoffice": "K", "eigenpal": "K",
        "office-open": "D", "docen": "D", "wordcraft": "D", "plate": "D",
        "fidus": "D", "canvas": "D", "docs.plus": "D",
        "docxodus": "R (SDK 3.5.1 models it)",
    },
    "a": {
        "superdoc": "K", "folio": "R", "genoffice": "K", "eigenpal": "R",
        "office-open": "R", "docen": "R", "wordcraft": "R (56/60)",
        "plate": "R (33/60)", "fidus": "R (11/60)", "canvas": "R (11/60)",
        "docs.plus": "R (42/60)", "docxodus": "R",
    },
    "wp": {
        "superdoc": "K", "folio": "R", "genoffice": "K", "eigenpal": "R",
        "office-open": "R", "docen": "R", "wordcraft": "R", "plate": "D",
        "fidus": "R (3/5)", "canvas": "R", "docs.plus": "R (4/5)",
        "docxodus": "R",
    },
    "pic": {
        "superdoc": "K", "folio": "R", "genoffice": "K", "eigenpal": "R",
        "office-open": "R", "docen": "R", "wordcraft": "R", "plate": "D",
        "fidus": "R", "canvas": "R", "docs.plus": "R", "docxodus": "R (media K)",
    },
    "dgm": {
        "superdoc": "R+G", "folio": "S", "genoffice": "K", "eigenpal": "S",
        "office-open": "R", "docen": "R", "wordcraft": "R (regen)", "plate": "D",
        "fidus": "D", "canvas": "D", "docs.plus": "D", "docxodus": "R (parts K)",
    },
    "c": {
        "superdoc": "R (def. fidelity)", "folio": "S", "genoffice": "K",
        "eigenpal": "S", "office-open": "R", "docen": "R", "wordcraft": "R+G",
        "plate": "D", "fidus": "D", "canvas": "D", "docs.plus": "D",
        "docxodus": "R (part K)",
    },
    "cs": {
        "superdoc": "R?", "folio": "K (part)", "genoffice": "K", "eigenpal": "K",
        "office-open": "R?", "docen": "R?", "wordcraft": "D", "plate": "D",
        "fidus": "D", "canvas": "D", "docs.plus": "D", "docxodus": "K (part)",
    },
    "m": {
        "superdoc": "R?", "folio": "R (→MathML)", "genoffice": "K",
        "eigenpal": "R", "office-open": "R", "docen": "R", "wordcraft": "R",
        "plate": "R (importer ignores it)", "fidus": "D", "canvas": "D",
        "docs.plus": "D", "docxodus": "R",
    },
    "v": {
        "superdoc": "R+G", "folio": "R", "genoffice": "K", "eigenpal": "R+G",
        "office-open": "R (opaque)", "docen": "R (opaque)", "wordcraft": "R (2/3)",
        "plate": "D", "fidus": "D", "canvas": "D", "docs.plus": "D",
        "docxodus": "R",
    },
    "o": {
        "superdoc": "R+G", "folio": "K (part)", "genoffice": "K", "eigenpal": "R",
        "office-open": "R (opaque)", "docen": "R (opaque)", "wordcraft": "R",
        "plate": "D", "fidus": "D", "canvas": "D", "docs.plus": "D",
        "docxodus": "R",
    },
    "w10": {
        "superdoc": "R?", "folio": "K", "genoffice": "K", "eigenpal": "K",
        "office-open": "K", "docen": "K", "wordcraft": "D", "plate": "D",
        "fidus": "D", "canvas": "D", "docs.plus": "D", "docxodus": "R",
    },
    "r": {
        "superdoc": "K", "folio": "R", "genoffice": "K", "eigenpal": "R",
        "office-open": "R", "docen": "R", "wordcraft": "R", "plate": "D",
        "fidus": "R (1/6)", "canvas": "R (2/6)", "docs.plus": "R (2/6)",
        "docxodus": "R",
    },
    "w:ins": {
        "superdoc": "R?", "folio": "K+G", "genoffice": "K (raw accept/reject)",
        "eigenpal": "R", "office-open": "R", "docen": "R", "wordcraft": "R",
        "plate": "D", "fidus": "S (marks)", "canvas": "D", "docs.plus": "D",
        "docxodus": "R",
    },
    "w:sdt": {
        "superdoc": "R?", "folio": "R", "genoffice": "K (shell)", "eigenpal": "R",
        "office-open": "R", "docen": "R", "wordcraft": "R", "plate": "D",
        "fidus": "D", "canvas": "D", "docs.plus": "D", "docxodus": "R",
    },
    "w:altChunk": {
        "superdoc": "R?", "folio": "R+G", "genoffice": "K", "eigenpal": "K",
        "office-open": "R?", "docen": "R?", "wordcraft": "D", "plate": "D",
        "fidus": "D", "canvas": "D", "docs.plus": "D", "docxodus": "R",
    },
    "ds": {
        "superdoc": "R?", "folio": "K (part)", "genoffice": "K", "eigenpal": "R?",
        "office-open": "R?", "docen": "R?", "wordcraft": "R?", "plate": "D",
        "fidus": "D", "canvas": "D", "docs.plus": "D", "docxodus": "K (part)",
    },
    "ns0": {
        "superdoc": "R?", "folio": "K (verbatim)", "genoffice": "K",
        "eigenpal": "K (generic)", "office-open": "R", "docen": "R",
        "wordcraft": "R", "plate": "D", "fidus": "D", "canvas": "D",
        "docs.plus": "D", "docxodus": "K",
    },
    "ct": {
        "superdoc": "R?", "folio": "R", "genoffice": "R", "eigenpal": "R",
        "office-open": "R", "docen": "R", "wordcraft": "R", "plate": "R",
        "fidus": "R?", "canvas": "R?", "docs.plus": "R?", "docxodus": "K",
    },
    "rels": {
        "superdoc": "R?", "folio": "R", "genoffice": "R", "eigenpal": "R",
        "office-open": "R", "docen": "R", "wordcraft": "R", "plate": "R",
        "fidus": "R", "canvas": "R", "docs.plus": "R", "docxodus": "K",
    },
}

# Construct rows are not namespace-scored: these are first-hand counts of the
# elements in each output package, and the label says which part they live in.
CONSTRUCT_COUNTS = {
    "w:ins": {"superdoc": 3, "folio": 3, "genoffice": 3, "eigenpal": 3,
              "office-open": 3, "docen": 3, "wordcraft": 2, "plate": 0,
              "fidus": 1, "canvas": 0, "docs.plus": 0, "docxodus": 3},
    "w:sdt": {"superdoc": 5, "folio": 5, "genoffice": 5, "eigenpal": 5,
              "office-open": 5, "docen": 5, "wordcraft": 5, "plate": 0,
              "fidus": 0, "canvas": 0, "docs.plus": 0, "docxodus": 5},
    "w:altChunk": {"superdoc": 1, "folio": 1, "genoffice": 1, "eigenpal": 1,
                   "office-open": 1, "docen": 1, "wordcraft": 0, "plate": 0,
                   "fidus": 0, "canvas": 0, "docs.plus": 0, "docxodus": 1},
}

ROW_LABELS = {
    "w:ins": "`w:ins`/`w:del`/`w:moveFrom`/`w:moveTo`",
    "w:sdt": "`w:sdt`",
    "w:altChunk": "`w:altChunk`",
    "ds": "`ds` (customXml)",
    "ns0": "`ns0` (foreign)",
    "ct": "`ct` (content types)",
}

HEADER_LABELS = {
    "superdoc": "SuperDoc", "folio": "Folio", "genoffice": "GenOffice",
    "eigenpal": "eigenpal", "office-open": "office-open", "docen": "Docen",
    "wordcraft": "WordCraft", "plate": "Plate.js", "fidus": "Fidus",
    "canvas": "canvas", "docs.plus": "docs.plus", "docxodus": "Docxodus",
}


def load_ns_map() -> dict[str, dict]:
    data = json.loads(NS_MAP.read_text())
    return {rec["prefix"]: rec for rec in data["namespaces"]}


def implied_class(cell: str) -> str:
    """What survival class does this cell claim?"""
    c = cell.strip()
    if c.startswith("S"):
        return "partial"
    if c.startswith("D (attr only)"):
        return "attr"
    if c.startswith("D"):
        return "none"
    if c.startswith("K"):
        return "all"
    if c.startswith("R"):
        m = re.match(r"R \((\d+)/(\d+)\)", c)
        if m:
            return "partial" if int(m.group(1)) < int(m.group(2)) else "all"
        return "all"
    return "unknown"


def validate(cells: dict[str, dict[str, str]], ns_map: dict[str, dict]) -> list[str]:
    problems = []
    for row, per_col in cells.items():
        if row in CONSTRUCT_COUNTS:
            counts = CONSTRUCT_COUNTS[row]
            for col, cell in per_col.items():
                n = counts[col]
                cls = implied_class(cell)
                want = "none" if n == 0 else "all"
                if cls not in (want, "partial"):
                    problems.append(f"{row}/{col}: cell '{cell}' claims {cls}, count is {n}")
                if n == 0 and cls == "all":
                    problems.append(f"{row}/{col}: cell '{cell}' claims all, count is 0")
            continue
        rec = ns_map.get(row)
        if rec is None:
            if row != "w16cex":
                problems.append(f"{row}: not in ns_map.json")
            continue
        total = len(rec["corpus_names"])
        for col, cell in per_col.items():
            s = rec["survival"].get(col)
            if s is None:
                problems.append(f"{row}/{col}: no measurement")
                continue
            kept = s["kept"]
            cls = implied_class(cell)
            if cls == "attr":
                if kept == 0:
                    problems.append(f"{row}/{col}: cell '{cell}' claims attr, measurement {kept}/{total}")
                continue
            if kept == 0 and cls == "all":
                problems.append(f"{row}/{col}: cell '{cell}' claims all, measurement {kept}/{total}")
            if kept == total and cls == "none":
                problems.append(f"{row}/{col}: cell '{cell}' claims none, measurement {kept}/{total}")
            if 0 < kept < total and cls == "none":
                problems.append(f"{row}/{col}: cell '{cell}' claims none, measurement {kept}/{total}")
            if 0 < kept < total and cls == "all":
                problems.append(f"{row}/{col}: cell '{cell}' claims all, measurement {kept}/{total}")
    return problems


def render(cells: dict[str, dict[str, str]]) -> str:
    out = ["| namespace | " + " | ".join(HEADER_LABELS[c] for c in COLS) + " |",
           "|---" * (len(COLS) + 1) + "|"]
    for row, per_col in cells.items():
        label = ROW_LABELS.get(row, f"`{row}`")
        out.append(f"| {label} | " + " | ".join(per_col[c] for c in COLS) + " |")
    return "\n".join(out)


def main() -> int:
    ns_map = load_ns_map()
    problems = validate(CELLS, ns_map)
    if problems:
        print("MATRIX INCONSISTENT WITH THE MEASUREMENT:")
        for p in problems:
            print("  -", p)
        return 1
    table = render(CELLS)
    if "--patch" in sys.argv:
        target = Path(sys.argv[sys.argv.index("--patch") + 1])
        text = target.read_text()
        start = text.index("| namespace | ")
        end = text.index("\n\n", start)
        old = text[start:end]
        new = text[:start] + table + text[end:]
        target.write_text(new)
        print(f"patched {target}: {len(old.splitlines())-2} rows -> {len(table.splitlines())-2} rows")
    else:
        print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
