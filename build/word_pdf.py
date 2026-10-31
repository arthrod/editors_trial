#!/usr/bin/env python3
"""
Render a .docx with Microsoft Word itself, to PDF.

Word's AppleScript `save as ... file format format PDF` is the only way to get
Word's OWN rendering of a document, which is the ground truth the editor
renderings are compared against.

The trap: Word queues the Apple Event while it is still busy and never
executes it, so the call times out with -1712 and no PDF appears. The fix is
the same one the open-test harness uses: restart Word, wait for the
AutoRecovery restore to land, clear the documents, and only then send the
event. The document is then opened, verified by NAME, and exported.

usage: python3 build/word_pdf.py <file.docx> <out.pdf> [...]
"""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_open import osa, restart_word  # noqa: E402


def export(path, out_pdf):
    """Open `path` in Word and export it to `out_pdf`. Returns True on success."""
    stem = os.path.splitext(os.path.basename(path))[0]
    parent = os.path.basename(os.path.dirname(path)) or "x"
    staged = os.path.join("/tmp/wt", "%s_%s.docx" % (parent, stem))
    os.makedirs("/tmp/wt", exist_ok=True)
    shutil.copy(path, staged)
    base = os.path.basename(staged)

    # a clean, responsive Word
    restart_word()
    time.sleep(2)
    for _ in range(10):
        if osa('tell application "Microsoft Word" to count documents') == "0":
            break
        time.sleep(1)

    subprocess.run(["open", "-a", "Microsoft Word", staged], capture_output=True)

    # wait for the document to actually be open, matched BY NAME
    opened = False
    deadline = time.time() + 60
    while time.time() < deadline:
        time.sleep(1.5)
        names = osa('tell application "Microsoft Word" to get name of every document')
        if names and names != "__TIMEOUT__" and base in names:
            opened = True
            break
    if not opened:
        print("  REFUSED (did not open): %s" % os.path.basename(path))
        return False

    target = os.path.abspath(out_pdf)
    if os.path.exists(target):
        os.remove(target)
    script = (
        'with timeout of 600 seconds\n'
        'tell application "Microsoft Word"\n'
        '  save as active document file name "%s" file format format PDF\n'
        '  return "saved"\n'
        'end tell\n'
        'end timeout' % target)
    res = osa(script, timeout=600)
    time.sleep(1)
    ok = os.path.exists(target) and os.path.getsize(target) > 0
    print("  %s -> %s (%s bytes)" % (os.path.basename(path),
                                     os.path.basename(out_pdf),
                                     os.path.getsize(target) if ok else 0),
          flush=True)
    if not ok:
        print("    export returned: %r" % res)
    return ok


if __name__ == "__main__":
    args = sys.argv[1:]
    outdir = args[0]
    os.makedirs(outdir, exist_ok=True)
    ok = 0
    for p in args[1:]:
        stem = os.path.splitext(os.path.basename(p))[0]
        if export(p, os.path.join(outdir, stem + ".pdf")):
            ok += 1
    print("exported %d of %d" % (ok, len(args) - 1))
