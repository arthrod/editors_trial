#!/usr/bin/env python3
"""
Final verification: open every deliverable in Microsoft Word and report
whether Word opens each one cleanly.

The verdict comes from the audited driver (build/word_batch.py ->
build/vendor/word_pdf.py): each file is staged under a unique name, the
document saved is the one named (never `active document`), and Word's repair
prompt is answered "No" - OPENED means Word opened and exported the file with
no prompt at all.

usage: python3 build/verify_deliverables.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import word_batch  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"
# The publication set: every report that ships as a DOCX twin, plus the
# fixture the whole trial is measured against. The archived combined Report A
# is not a deliverable - it was superseded by Report A and Report A2.
DELIVERABLES = [
    (os.path.join(BASE, "Open-Source DOCX Editors Re-verified Against "
                         "Code and Measured Round-Trip (2026).docx"), "report 1"),
    (os.path.join(BASE, "reports", "Report A - Serialization by "
                                   "Namespace (2026).docx"), "report A"),
    (os.path.join(BASE, "reports", "Report A2 - Pass-Through (2026).docx"),
     "report A2"),
    (os.path.join(BASE, "reports", "Report B - Malformed Parts, Causes and "
                                   "Repair (2026).docx"), "report B"),
    (os.path.join(BASE, "reports", "Report C - Rendering Versus Word "
                                   "(2026).docx"), "report C"),
    (os.path.join(BASE, "reports", "Report D - Safety, Resource Bombs and "
                                   "Hostile Input (2026).docx"), "report D"),
    (os.path.join(BASE, "reports", "Report D1 - Jubarte on the Hostile "
                                    "Packages (2026).docx"), "report D1"),
    (os.path.join(BASE, "reports", "Report D2 - What Word Protects Against "
                                    "(2026).docx"), "report D2"),
    (os.path.join(BASE, "fixture", "complex.docx"), "fixture"),
]


if __name__ == "__main__":
    from pathlib import Path
    targets, ok = {}, True
    for path, label in DELIVERABLES:
        if not os.path.exists(path):
            print("MISSING %s" % path, flush=True)
            ok = False
        else:
            targets[label.replace(" ", "-")] = Path(path)
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(BASE) / "out" / "word_deliverables"
    verdicts = word_batch.run(targets, work)
    for path, label in DELIVERABLES:
        key = label.replace(" ", "-")
        if key not in verdicts:
            continue
        v = verdicts[key]
        pdf = work / ("%s.pdf" % key)
        size = " (%d-byte PDF)" % pdf.stat().st_size if pdf.exists() else ""
        print("%-9s %-52s => %s%s" % (label, os.path.splitext(os.path.basename(path))[0][:52], v, size), flush=True)
        ok = ok and v == "OPENED"
    print("ALL DELIVERABLES OPEN IN MICROSOFT WORD" if ok
          else "SOME DELIVERABLE FAILED")
