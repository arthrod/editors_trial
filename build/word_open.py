#!/usr/bin/env python3
"""
Ask Microsoft Word 16.115 to open a file and report the verdict.

usage: python3 build/word_open.py <file.docx> [<file.docx> ...]

Prints "<file> => OPENED | REFUSED" for each file. Word leaves a modal
dialog behind when it refuses a document, so the process is hard-restarted
before every file: a refusal must never poison the next test.
"""
import os
import shutil
import subprocess
import sys
import time


def osa(script, timeout=25):
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "__TIMEOUT__"


_DIRTY = True          # first run: Word's state is unknown
_LAST_REFUSED = False  # a refusal leaves a modal dialog behind


def ensure_clean():
    """Clear Word's document set, restarting it only when necessary.

    A refusal leaves a modal dialog that blocks every later open, so after one
    the app has to be restarted - and a hard kill makes Word restore its
    AutoRecovery set, which then steals the open. A restart therefore waits
    for the restore to land and clears it; a clean test only needs the
    documents closed.

    Closing is not enough on its own: Word keeps processing the close for a
    moment afterwards, and an Apple Event that arrives while the app is still
    busy is QUEUED rather than executed. The file then never opens and the
    poll reports REFUSED for a file Word would have accepted. So after
    closing, wait for the document count to reach zero and let the app settle
    before the open is sent.
    """
    global _DIRTY
    if _DIRTY or _LAST_REFUSED:
        n = restart_word()
        _DIRTY = False
        return n
    osa('tell application "Microsoft Word" to close every document saving no')
    n = "?"
    for _ in range(10):
        time.sleep(1.0)
        n = osa('tell application "Microsoft Word" to count documents')
        if n == "0":
            break
    time.sleep(2.0)
    return n


def restart_word():
    """Bring Word to a clean, document-free state.

    A hard kill makes Word restore its AutoRecovery set on the next launch -
    including any documents the user had open. That restore lands AFTER a
    short sleep and then steals the Apple Event, so the target file is never
    opened and the poll sees somebody else's document. Give the restore time
    to finish, then clear everything, then confirm the document count is 0
    before the target is opened.
    """
    subprocess.run(["killall", "-9", "Microsoft Word"], capture_output=True)
    time.sleep(3)
    subprocess.run(["open", "-a", "Microsoft Word"], capture_output=True)
    time.sleep(20)
    for _ in range(3):
        osa('tell application "Microsoft Word" to close every document saving no')
        time.sleep(2)
    for _ in range(6):
        n = osa('tell application "Microsoft Word" to count documents')
        if n == "0":
            break
        osa('tell application "Microsoft Word" to close every document saving no')
        time.sleep(2)
    return osa('tell application "Microsoft Word" to count documents')


def _open_once(staged, base):
    """One open-and-poll cycle. Returns OPENED, REFUSED or a diagnostic string."""
    n = ensure_clean()
    if n != "0":
        return "ORACLE-NOT-CLEAN:%s" % n
    subprocess.run(["open", "-a", "Microsoft Word", staged], capture_output=True)
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
            verdict = "OPENED" if base in out else "OPENED-OTHER:" + out
            break
    return verdict


def open_file(path):
    global _LAST_REFUSED
    # Every editor's output is called complex.docx, so a name match alone
    # cannot tell them apart - and a stale document left over from an earlier
    # test would satisfy it. Stage each file under a unique name.
    stem = os.path.splitext(os.path.basename(path))[0]
    parent = os.path.basename(os.path.dirname(path)) or "x"
    os.makedirs("/tmp/wt", exist_ok=True)
    staged = os.path.join("/tmp/wt", "%s_%s.docx" % (parent, stem))
    shutil.copy(path, staged)
    base = os.path.basename(staged)

    verdict = _open_once(staged, base)

    # A refusal can be real or an artifact of a busy Word (the open is queued
    # instead of executed). Only a full restart tells the two apart, so a
    # refusal is always retried once against a freshly started Word. The
    # second verdict is the one that is reported.
    if verdict == "REFUSED":
        _LAST_REFUSED = True
        time.sleep(1)
        verdict2 = _open_once(staged, base)
        verdict = verdict + "/RETRY:" + verdict2
        if verdict2.startswith("OPENED"):
            verdict = "OPENED"
        _LAST_REFUSED = False

    _LAST_REFUSED = (verdict.startswith("REFUSED"))
    print("%-46s => %s" % (parent + "/" + stem, verdict), flush=True)
    return verdict


if __name__ == "__main__":
    for f in sys.argv[1:]:
        open_file(f)
