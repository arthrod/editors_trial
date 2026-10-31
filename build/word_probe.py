#!/usr/bin/env python3
"""
Test arbitrary word/document.xml bodies against Microsoft Word 16.115.

usage: python3 build/word_probe.py <name> <body-file> [<body-file> ...]

Each body file contains the raw inner XML of <w:body>. The rest of the
package is taken from fixture/complex.docx unchanged. A variant is OPENED if
Word opens it, REFUSED if Word declines it.

Word leaves a modal dialog behind when it refuses a file, so the process is
hard-restarted before every probe; a refusal must never poison the next test.
"""
import os
import re
import subprocess
import sys
import time
import zipfile

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")
WT = "/tmp/wt"
LOG = "/tmp/word_probe.log"

os.makedirs(WT, exist_ok=True)
with zipfile.ZipFile(SRC) as _z:
    PARTS = {n: _z.read(n) for n in _z.namelist()}
DOC = PARTS["word/document.xml"].decode("utf-8")
# keep the whole <w:document ...> wrapper: it carries every namespace
# declaration, and dropping it makes the part unparsable for Word.
HEAD = DOC[:DOC.index("<w:body>") + len("<w:body>")]
TAIL = DOC[DOC.index("</w:body>"):]


def osa(script, timeout=25):
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "__TIMEOUT__"


def restart_word():
    subprocess.run(["killall", "-9", "Microsoft Word"], capture_output=True)
    time.sleep(2)
    subprocess.run(["open", "-a", "Microsoft Word"], capture_output=True)
    time.sleep(6)


def probe(name, body, keep_package=True, src=SRC):
    """Ask Word to open a document built from `src`'s package with `body`."""
    path = os.path.join(WT, name + ".docx")
    newdoc = HEAD + body + TAIL
    with zipfile.ZipFile(src) as _z:
        pkg = {n: _z.read(n) for n in _z.namelist()}
    head = pkg["word/document.xml"].decode("utf-8")
    head = head[:head.index("<w:body>") + len("<w:body>")]
    tail = head  # placeholder, replaced below
    tail = pkg["word/document.xml"].decode("utf-8")
    tail = tail[tail.index("</w:body>"):]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as o:
        for n, data in pkg.items():
            o.writestr(n, (head + body + tail).encode("utf-8")
                       if n == "word/document.xml" else data)
    restart_word()
    osa('tell application "Microsoft Word" to close every document saving no')
    time.sleep(0.5)
    subprocess.run(["open", "-a", "Microsoft Word", path], capture_output=True)
    none, verdict = 0, "TIMEOUT"
    deadline = time.time() + 45
    while time.time() < deadline:
        time.sleep(1.5)
        out = osa('tell application "Microsoft Word" to get name of every document')
        if out == "__TIMEOUT__":
            break
        if out.startswith("missing") or out == "":
            none += 1
            if none >= 8:
                verdict = "REFUSED"
                break
        else:
            verdict = "OPENED" if name in out else "OPENED-OTHER:" + out
            break
    with open(LOG, "a") as f:
        f.write("%-26s => %s\n" % (name, verdict))
    print("%-26s => %s" % (name, verdict), flush=True)
    return verdict


if __name__ == "__main__":
    for i in range(1, len(sys.argv), 2):
        nm = sys.argv[i]
        bf = sys.argv[i + 1]
        with open(bf) as f:
            probe(nm, f.read())
