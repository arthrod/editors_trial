#!/usr/bin/env python3
"""
Open every editor's output in Microsoft Word and record the verdicts. The
opening is done by the audited driver (build/word_batch.py ->
build/vendor/word_pdf.py): OPENED means Word opened and exported the file with
no repair prompt; REFUSED means Word offered to repair it.

Two sets of outputs:
  outputs  out/<tool>/complex.docx         -> out/word_verdicts.json        (main report, D2)
  broken   out_broken/<tool>/complex.docx  -> out/word_verdicts_broken.json (Report B)

usage: python3 build/word_verdicts.py [--set outputs|broken] [work-dir]
       python3 build/word_verdicts.py [--set ...] --reread <work-dir>   # verdicts from a finished run's manifest
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import word_batch  # noqa: E402

TOOLS = ["plate", "docxodus", "superdoc", "folio", "folio-editor", "genoffice", "eigenpal",
         "eigenpal-editor", "officeopen", "docen", "wordcraft", "fidus", "canvas", "docsplus", "apryse", "lo_baseline"]

SETS = {
    "outputs": {"src": ROOT / "out", "json": ROOT / "out" / "word_verdicts.json",
                "work": ROOT / "out" / "word_verdicts"},
    "broken": {"src": ROOT / "out_broken", "json": ROOT / "out" / "word_verdicts_broken.json",
               "work": ROOT / "out" / "word_verdicts_broken"},
}


def targets(name: str) -> dict[str, Path]:
    src = SETS[name]["src"]
    return {t: src / t / "complex.docx" for t in TOOLS if (src / t / "complex.docx").exists()}


def parse(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=sorted(SETS), default="outputs")
    ap.add_argument("--reread", type=Path, help="read the verdicts from this finished run; Word is not opened")
    ap.add_argument("work", nargs="?", type=Path)
    return ap.parse_args(argv)


def main(argv: list[str]) -> int:
    a = parse(argv)
    s = SETS[a.set]
    t = targets(a.set)
    work = a.reread or a.work or s["work"]
    if not a.reread:
        word_batch.run(t, work)
    records = word_batch.read_manifest(work / "manifest.jsonl")
    verdicts = {k: word_batch.verdict(records.get(k, {"status": "no record"})) for k in t}
    details = {k: records[k].get("error", "") for k in t if k in records and records[k].get("error")}
    for k, v in verdicts.items():
        print(f"{k:16s} {v}")
    s["json"].write_text(json.dumps({
        "word": word_batch.word_version(),
        "driver": (ROOT / "build/vendor/word_pdf.SOURCE").read_text().split("\n")[1],
        "verdicts": verdicts,
        "details": details,
    }, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
