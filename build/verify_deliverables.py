#!/usr/bin/env python3
"""
Final verification: open every deliverable in Microsoft Word and report what
Word itself sees - document name, word count, paragraph count, table count.

The verdict comes from build/word_open.py, which stages each file under a
unique name, matches the open document BY NAME (never by index - "document 1"
is whatever happened to be open first) and retries every refusal against a
freshly restarted Word.

usage: python3 build/verify_deliverables.py
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import word_open  # noqa: E402
from word_open import osa  # noqa: E402

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


def stats_for(name):
    """Word's own view of the document called `name`.

    The name is checked first - `active document` is only used to reach the
    object, never to decide WHICH document is being measured. Word's
    `count of words` does not work on a reference taken from a repeat loop,
    so the object is taken from `active document` and its name is verified.
    """
    script = (
        'tell application "Microsoft Word"\n'
        '  set d to active document\n'
        '  if (name of d) is not "%s" then return "WRONG-DOCUMENT:" & (name of d)\n'
        '  return (count of words of d) & " words, " & '
        '(count of paragraphs of d) & " paragraphs, " & '
        '(count of tables of d) & " tables"\n'
        'end tell' % name.replace('"', '\\"'))
    s = osa(script)
    return s if s and s != "__TIMEOUT__" else "?"


if __name__ == "__main__":
    ok = True
    for path, label in DELIVERABLES:
        if not os.path.exists(path):
            print("MISSING %s" % path, flush=True)
            ok = False
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        parent = os.path.basename(os.path.dirname(path)) or "x"
        staged = "/tmp/wt/%s_%s.docx" % (parent, stem)
        verdict = word_open.open_file(path)
        if verdict.startswith("OPENED"):
            st = stats_for(os.path.basename(staged))
            print("%-9s %-52s => OPENED  (%s)" % (label, stem[:52], st), flush=True)
        else:
            print("%-9s %-52s => %s" % (label, stem[:52], verdict), flush=True)
            ok = False
    print("ALL DELIVERABLES OPEN IN MICROSOFT WORD" if ok
          else "SOME DELIVERABLE FAILED")
