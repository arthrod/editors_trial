#!/usr/bin/env python3
"""
Find the document.xml body block(s) that make Microsoft Word refuse the fixture.

Strategy: binary search over the 41 top-level body blocks of word/document.xml.
Keep a subset of blocks (+ the mandatory trailing w:sectPr) and ask Word whether
it opens the file. A subset that Word refuses contains at least one culprit;
narrowing to a single block identifies it. Wedge-safe: Word is force-restarted
whenever its Apple Event connection stops answering (a refusal dialog).

usage: python3 build/find_word_culprit.py [max_rounds]
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
LOG = "/tmp/culprit_log.txt"

os.makedirs(WT, exist_ok=True)


# ---------------------------------------------------------------- body split
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wxml import split_body  # noqa: E402


def _unused_split(doc):
    pass


with zipfile.ZipFile(SRC) as _z:
    PARTS = {n: _z.read(n) for n in _z.namelist()}
DOC = PARTS["word/document.xml"].decode("utf-8")
HEAD, BLOCKS, TAIL = split_body(DOC)
FINAL_SECTPR = next(b for b in reversed(BLOCKS) if b.startswith("<w:sectPr"))
BODY_IDX = [i for i, b in enumerate(BLOCKS) if b is not FINAL_SECTPR]
NB = len(BODY_IDX)


def write_variant(name, keep):
    """keep = iterable of block indices (into BLOCKS)."""
    body = "".join(BLOCKS[i] for i in keep)
    newdoc = HEAD + body + FINAL_SECTPR + TAIL
    path = os.path.join(WT, name + ".docx")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as o:
        for n, data in PARTS.items():
            o.writestr(n, newdoc.encode("utf-8") if n == "word/document.xml" else data)
    return path


# ---------------------------------------------------------------- word driver
def osa(script, timeout=25):
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "__TIMEOUT__"


def word_alive():
    out = osa('tell application "Microsoft Word" to count documents', timeout=20)
    return out not in ("__TIMEOUT__", "")


def restart_word():
    subprocess.run(["killall", "-9", "Microsoft Word"], capture_output=True)
    time.sleep(2)
    subprocess.run(["open", "-a", "Microsoft Word"], capture_output=True)
    time.sleep(7)


def word_opens(path, basename):
    """True if Word opens the file. Assumes Word is alive and modal-free."""
    osa('tell application "Microsoft Word" to close every document saving no')
    time.sleep(0.5)
    subprocess.run(["open", "-a", "Microsoft Word", path], capture_output=True)
    none = 0
    deadline = time.time() + 50
    while time.time() < deadline:
        time.sleep(1.5)
        out = osa('tell application "Microsoft Word" to get name of every document')
        if out == "__TIMEOUT__":
            return None            # wedged -> caller restarts Word
        if out.startswith("missing") or out == "":
            none += 1
            if none >= 9:
                return False        # refused
        else:
            if basename in out:
                return True
            none = 0
    return False


def test(name, keep):
    """Word verdict for the variant holding only `keep` blocks.

    A refusal leaves a modal dialog in Word that blocks every later open, so
    Word is always restarted before a test. That is the only reliable way to
    keep the oracle honest.
    """
    global NEEDS_RESTART
    path = write_variant(name, keep)
    base = os.path.basename(path)
    if NEEDS_RESTART or not word_alive():
        restart_word()
    NEEDS_RESTART = False
    v = word_opens(path, base)
    if v is None:
        restart_word()
        v = word_opens(path, base)
    if v is False:
        NEEDS_RESTART = True
    line = "%-22s keep=%-3s => %s" % (
        name, len(list(keep)), "OPENED" if v else "REFUSED")
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)
    return v


# ---------------------------------------------------------------- algorithm
NEEDS_RESTART = False


def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


log("=== search start: %d body blocks ===" % NB)
cur = list(BODY_IDX)
found = []
rounds = 0
max_rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 12

# sanity: the control file must open, otherwise the oracle is broken
ctrl = os.path.join(WT, "control.docx")
if not os.path.exists(ctrl):
    subprocess.run(["cp", os.path.join(os.path.expanduser("~"),
                                       "Documents", "wordtest", "control.docx"), ctrl])
restart_word()
ok = word_opens(ctrl, "control.docx")
log("oracle sanity (control.docx): %s" % ("OPENED" if ok else "REFUSED"))
if not ok:
    restart_word()
    ok = word_opens(ctrl, "control.docx")
    log("oracle sanity after restart: %s" % ("OPENED" if ok else "REFUSED"))
    if not ok:
        log("ORACLE BROKEN - aborting")
        sys.exit(2)


# 1. sanity: the full body must be refused
rounds += 1
full_refused = test("all_blocks", cur)
log("full body refused = %s" % ("REFUSED" if full_refused is False else "OPENED"))


def bisect(keep):
    """Narrow `keep` to a subset Word still refuses, by halving."""
    global rounds
    cur = list(keep)
    while rounds < max_rounds and len(cur) > 1:
        mid = len(cur) // 2
        left, right = cur[:mid], cur[mid:]
        rounds += 1
        if test("bis_left", left) is False:
            cur = left
            continue
        rounds += 1
        if test("bis_right", right) is False:
            cur = right
            continue
        log("neither half refused -> interaction inside %d blocks" % len(cur))
        return cur
    return cur


# 2. find every culprit: narrow to a candidate set, then isolate
work = list(BODY_IDX)
while rounds < max_rounds and len(work) > 1:
    cand = bisect(work)
    if not cand:
        break
    log("candidate set: %s" % cand)
    hit = None
    for i in cand:
        rounds += 1
        if test("solo_%02d" % i, [i]) is False:
            hit = i
            break
    if hit is None:
        # the block is only fatal in context: use the remove-one test
        for i in cand:
            rounds += 1
            keep = [j for j in cand if j != i]
            if test("blk_%02d" % i, keep) is True:
                hit = i
                break
    if hit is None:
        log("could not isolate a single culprit inside %s" % cand)
        break
    log("CULPRIT BLOCK = %d" % hit)
    found.append(hit)
    work = [j for j in BODY_IDX if j not in found]   # drop every culprit found so far
    rounds += 1
    still = test("minus_%02d" % hit, work)
    log("after removing block %d, remainder still refused = %s"
        % (hit, "REFUSED" if still is False else "OPENED"))
    if still is not False:
        log("single culprit identified")
        break

log("CULPRIT BLOCKS (index into BLOCKS): %s" % found)
for i in found:
    log("  block %d: %s" % (i, BLOCKS[i][:500]))
log("=== search done ===")
