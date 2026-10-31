#!/usr/bin/env python3
"""
Render every editor output with MICROSOFT WORD, to PDF.

Word's own rendering is the ground truth: it is the application the document
was written for. LibreOffice is the proxy, because it can open the four files
Word refuses and because it is scriptable and parallel; this script produces
the reference series that the proxy series is checked against.

The traps, and what this script does about them:

  * every editor's output is called complex.docx, so each file is STAGED
    under a unique name and each PDF is written under a unique name;
  * a refused document leaves a modal dialog behind that blocks every later
    open, so the app is restarted only after a refusal - not before every
    file;
  * Word queues an Apple Event while it is still busy, so the document count
    is polled to zero and the app is given a moment to settle before the
    open is sent;
  * the `save as ... format PDF` call takes far longer than the 25 s default
    of the osascript wrapper, so it gets its own long timeout.

usage: python3 build/word_render_all.py <outdir>
"""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_open import osa, restart_word  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"

TARGETS = [
    ("corpus", os.path.join(BASE, "fixture", "complex.docx")),
    ("superdoc", os.path.join(BASE, "out", "superdoc", "complex.docx")),
    ("folio", os.path.join(BASE, "out", "folio", "complex.docx")),
    ("genoffice", os.path.join(BASE, "out", "genoffice", "complex.docx")),
    ("eigenpal", os.path.join(BASE, "out", "eigenpal", "complex.docx")),
    ("office-open", os.path.join(BASE, "out", "officeopen", "complex.docx")),
    ("docen", os.path.join(BASE, "out", "docen", "complex.docx")),
    ("wordcraft", os.path.join(BASE, "out", "wordcraft", "complex.docx")),
    ("fidus", os.path.join(BASE, "out", "fidus", "complex.docx")),
    ("canvas", os.path.join(BASE, "out", "canvas", "complex.docx")),
    ("docs.plus", os.path.join(BASE, "out", "docsplus", "complex.docx")),
    ("plate", os.path.join(BASE, "out", "plate", "complex.docx")),
    ("docxodus", os.path.join(BASE, "out", "docxodus", "complex.docx")),
    ("libreoffice", os.path.join(BASE, "out", "lo_baseline", "complex.docx")),
]


def close_all():
    osa('tell application "Microsoft Word" to close every document saving no')
    for _ in range(12):
        time.sleep(1.0)
        if osa('tell application "Microsoft Word" to count documents') == "0":
            break
    time.sleep(2.0)


def export(label, path, outdir):
    staged = "/tmp/wt/render_%s_complex.docx" % label.replace(".", "_")
    os.makedirs("/tmp/wt", exist_ok=True)
    shutil.copy(path, staged)
    base = os.path.basename(staged)

    close_all()
    subprocess.run(["open", "-a", "Microsoft Word", staged], capture_output=True)

    opened = False
    deadline = time.time() + 60
    while time.time() < deadline:
        time.sleep(1.5)
        names = osa('tell application "Microsoft Word" to get name of every document')
        if names and names != "__TIMEOUT__" and base in names:
            opened = True
            break
    if not opened:
        print("  %-12s REFUSED by Word (no output)" % label, flush=True)
        return False

    target = os.path.join(outdir, "%s.pdf" % label)
    if os.path.exists(target):
        os.remove(target)
    script = (
        'with timeout of 900 seconds\n'
        'tell application "Microsoft Word"\n'
        '  save as active document file name "%s" file format format PDF\n'
        '  return "saved"\n'
        'end tell\n'
        'end timeout' % os.path.abspath(target))
    osa(script, timeout=900)
    time.sleep(1)
    ok = os.path.exists(target) and os.path.getsize(target) > 0
    print("  %-12s %s (%s bytes)" % (label, "OK" if ok else "EXPORT FAILED",
                                     os.path.getsize(target) if ok else 0),
          flush=True)
    return ok


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    ok = 0
    for label, path in TARGETS:
        if not os.path.exists(path):
            print("  %-12s MISSING" % label, flush=True)
            continue
        if export(label, path, outdir):
            ok += 1
        else:
            # a refusal leaves a modal behind; clear it for the next file
            restart_word()
            time.sleep(3)
    print("rendered %d of %d with Word" % (ok, len(TARGETS)), flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "out", "render", "word"))
