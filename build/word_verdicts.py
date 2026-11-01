#!/usr/bin/env python3
"""
Open every editor's output in Microsoft Word and record the verdicts in
out/word_verdicts.json (build/word_open.py does the opening and the retry).

usage: python3 build/word_verdicts.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import word_open  # noqa: E402

TOOLS = ["plate", "docxodus", "superdoc", "folio", "folio-editor", "genoffice", "eigenpal",
         "eigenpal-editor", "officeopen", "docen", "wordcraft", "fidus", "canvas", "docsplus", "lo_baseline"]

version = subprocess.run(["defaults", "read", "/Applications/Microsoft Word.app/Contents/Info.plist",
                          "CFBundleShortVersionString"], capture_output=True, text=True).stdout.strip()
verdicts = {}
for t in TOOLS:
    path = ROOT / "out" / t / "complex.docx"
    if path.exists():
        verdict = word_open.open_file(str(path))
        verdicts[t] = verdict
        print(f"{t:16s} {verdict}")
(ROOT / "out" / "word_verdicts.json").write_text(json.dumps({"word": version, "verdicts": verdicts}, indent=1) + "\n")
