#!/usr/bin/env python3
"""
Open a set of .docx files in Microsoft Word and export each to PDF, through the
audited driver vendored at build/vendor/word_pdf.py (see word_pdf.SOURCE).

The driver does the hard parts: it stages inside Word's container, names the
document it saves (never `active document`), answers Word's repair prompt
"No" so Word's repair is never measured, watches Microsoft Error Reporting,
holds a lock so two Word jobs never share Word, and writes one manifest record
per file. This module only stages the trial's files under unique names, runs
the driver once, and reads its manifest:

  OPENED   Word opened the file and exported it, with no repair prompt;
  REFUSED  Word raised its repair prompt, or opened no document (not Word valid);
  FAILED:  anything else, with the driver's own words.

Run it the way the bench's own handoff says (neurotic_docx_bench,
docs/HANDOFF_LIVE_BENCH_HARVEST_20261017.md): Word clean (no documents open)
and in front, nothing else driving Word, and the run in the foreground of a
Terminal tab - not as a hidden background job, where Word's repair prompt can
arrive only after the open has timed out.

usage (library): word_batch.run({"plate": Path(...), ...}, out_dir) -> {label: verdict}
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "build" / "vendor" / "word_pdf.py"
# The bench runs its driver beside this watchdog: a modal dialog blocks the
# driver's own timeouts, so when neither the output folder nor the log has
# grown for 60 s while Word sits idle, the watchdog kills Word and the driver
# recycles it and resumes (neurotic_docx_bench scripts/word_watchdog.sh).
WATCHDOG = ROOT / "build" / "vendor" / "word_watchdog.sh"
# Both mean Word did not open the file: the driver declined Word's repair
# prompt, or Word produced no document for it (the watchdog does not always
# get to record its decline before the driver gives up on the empty load).
REFUSALS = ("repair prompt declined", "open produced 0 new documents")


def verdict(record: dict) -> str:
    if record.get("status") == "ok":
        return "OPENED"
    error = str(record.get("error", ""))
    if any(r in error for r in REFUSALS):
        return "REFUSED"
    return f"FAILED: {error}" if error else f"FAILED: {record.get('status', 'no record')}"


def read_manifest(path: Path) -> dict[str, dict]:
    """The last PDF record for each staged file, keyed by its stem (the label)."""
    out: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") == "rename":
            continue
        out[Path(r["original_filename"]).stem] = r
    return out


def word_version() -> str:
    return subprocess.run(["defaults", "read", "/Applications/Microsoft Word.app/Contents/Info.plist",
                           "CFBundleShortVersionString"], capture_output=True, text=True).stdout.strip()


def run(targets: dict[str, Path], out_dir: Path, timeout: float = 180.0) -> dict[str, str]:
    """Export every target once; PDFs land in out_dir as <label>.pdf, the driver's log beside them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="trial-word-") as tmp:
        src = Path(tmp)
        for label, path in targets.items():
            shutil.copy(path, src / f"{label}.docx")
        # A fresh output folder per run: the driver skips files whose PDF exists
        # and remembers refusals there, and a verdict must come from this run.
        work = Path(tempfile.mkdtemp(prefix="trial-word-out-"))
        cmd = ["uv", "run", "-q", "--script", str(DRIVER), "--src", str(src), "--out", str(work),
               "--force", "--timeout", str(timeout), "--no-check-preset", "--label", "trial",
               "--log", str(out_dir / "word_driver.log")]
        log = out_dir / "word_driver.log"
        dog = subprocess.Popen([str(WATCHDOG), str(work), str(log)],
                               stdout=open(out_dir / "word_watchdog.log", "a"), stderr=subprocess.STDOUT)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        finally:
            dog.terminate()
            dog.wait(timeout=10)
        (out_dir / "word_driver.stdout").write_text(proc.stdout + proc.stderr)
        manifest = work / "manifest.jsonl"
        records = read_manifest(manifest) if manifest.exists() else {}
        shutil.copy(manifest, out_dir / "manifest.jsonl") if manifest.exists() else None
        verdicts = {}
        for label in targets:
            r = records.get(label, {"status": "no record", "error": f"driver exit {proc.returncode}"})
            verdicts[label] = verdict(r)
            pdf = work / f"{label}_byword.pdf"
            if verdicts[label] == "OPENED" and pdf.exists():
                shutil.move(pdf, out_dir / f"{label}.pdf")
        shutil.rmtree(work, ignore_errors=True)
    return verdicts
