#!/usr/bin/env python3
"""
Open every editor's output in Microsoft Word and record the verdicts in
out/word_verdicts.json. The opening is done by the audited driver
(build/word_batch.py -> build/vendor/word_pdf.py): OPENED means Word opened
and exported the file with no repair prompt; REFUSED means Word offered to
repair it.

usage: python3 build/word_verdicts.py [work-dir]
       python3 build/word_verdicts.py --reread <work-dir>   # verdicts from a finished run's manifest
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import word_batch  # noqa: E402

TOOLS = ["plate", "docxodus", "superdoc", "folio", "folio-editor", "genoffice", "eigenpal",
         "eigenpal-editor", "officeopen", "docen", "wordcraft", "fidus", "canvas", "docsplus", "apryse", "lo_baseline"]

reread = len(sys.argv) > 2 and sys.argv[1] == "--reread"
work = Path(sys.argv[-1]) if len(sys.argv) > 1 else ROOT / "out" / "word_verdicts"
targets = {t: ROOT / "out" / t / "complex.docx" for t in TOOLS if (ROOT / "out" / t / "complex.docx").exists()}
if not reread:
    word_batch.run(targets, work)
records = word_batch.read_manifest(work / "manifest.jsonl")
verdicts = {t: word_batch.verdict(records.get(t, {"status": "no record"})) for t in targets}
details = {t: records[t].get("error", "") for t in targets if t in records and records[t].get("error")}
for t, v in verdicts.items():
    print(f"{t:16s} {v}")
(ROOT / "out" / "word_verdicts.json").write_text(json.dumps({
    "word": word_batch.word_version(),
    "driver": (ROOT / "build/vendor/word_pdf.SOURCE").read_text().split("\n")[1],
    "verdicts": verdicts,
    "details": details,
}, indent=1) + "\n")
