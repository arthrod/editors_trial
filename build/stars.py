#!/usr/bin/env python3
"""
Snapshot GitHub star counts into out/stars.json, for build/facts.py.

Stars are a measurement like any other: the reports quote them "measured on"
a date, so they are fetched once per release and kept with that date.

    python3 build/stars.py            # fetch every repository the reports name
    python3 build/stars.py --seed     # rebuild the snapshot from the main report's star table

--seed records the counts the published report already states, with the date
the report gives; it is how the v0.9.0 snapshot was made.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "stars.json"
MAIN = ROOT / "Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md"

# Every repository whose star count a report quotes (the main report's sweep table).
REPOS = [
    "storytold/wordcraft", "udecode/plate", "genspark-ai/genoffice", "dolanmiu/docx",
    "ONLYOFFICE/DocumentServer", "Hufe921/canvas-editor", "superdoc/docx-editor",
    "fiduswriter/fiduswriter", "stffnb/edentext", "eigenpal/docx-editor", "openooxml/betteroffice",
    "Hufe921/canvas-editor-plugin", "JSv4/Docxodus", "docs-plus/docs.plus", "CasualOffice/docs",
    "DemoMacro/docen", "ant981228/cardmirror", "DemoMacro/office-open", "CasualOffice/opendoc",
    "stella/folio",
]


def seed() -> dict:
    text = MAIN.read_text()
    date = re.search(r"star counts \*\*measured on (\d{4}-\d{2}-\d{2})\*\*", text)
    stars = {}
    for slug, n in re.findall(r"^\| `([\w.\-]+/[\w.\-]+)` \| \**([\d,]+)\** \|", text, re.M):
        stars[slug] = int(n.replace(",", ""))
    return {"date": date.group(1) if date else None, "stars": stars}


def fetch() -> dict:
    stars = {}
    for slug in REPOS:
        r = subprocess.run(["gh", "api", f"repos/{slug}", "--jq", ".stargazers_count"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"skip {slug}: {r.stderr.strip()[:120]}", file=sys.stderr)
            continue
        stars[slug] = int(r.stdout.strip())
    return {"date": datetime.date.today().isoformat(), "stars": stars}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true")
    a = ap.parse_args()
    data = seed() if a.seed else fetch()
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"stars: {len(data['stars'])} repositories, {data['date']} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
