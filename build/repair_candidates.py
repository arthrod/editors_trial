#!/usr/bin/env python3
"""
Repair candidates for the fixture's two confirmed Word refusals.

Confirmed by bisection (see /tmp/culprit_log.txt):
  * block  9 - the w:moveFrom region, alone, is refused
  * block 31 - the block-level m:oMathPara, alone, is refused

This script writes whole-document variants with different repairs applied and
probes each one against Microsoft Word.

usage: python3 build/repair_candidates.py
"""
import os
import re
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wxml import split_body  # noqa: E402
from word_probe import probe  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")

with zipfile.ZipFile(SRC) as _z:
    PARTS = {n: _z.read(n) for n in _z.namelist()}
DOC = PARTS["word/document.xml"].decode("utf-8")
HEAD, BLOCKS, TAIL = split_body(DOC)

AUTHOR = "Fixture Author"
DATE = "2026-01-15T09:30:00Z"

# ------------------------------------------------------------------ repairs
MATH_P = ("<m:oMathPara><m:oMath>"
          '<m:r><w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'
          "<m:t>E = mc^2</m:t></m:r>"
          "</m:oMath></m:oMathPara>")

# a) wrap the display equation in a paragraph, the way Word writes it
MATH_FIXED = "<w:p>" + MATH_P + "</w:p>"

# b) inline equation inside a normal paragraph
MATH_INLINE = ("<w:p><w:r><w:t>inline:</w:t></w:r>"
               "<m:oMath><m:r><w:rPr><w:rFonts w:ascii=\"Cambria Math\" "
               "w:hAnsi=\"Cambria Math\"/></w:rPr>"
               "<m:t>E = mc^2</m:t></m:r></m:oMath></w:p>")

MOVE_FROM = BLOCKS[9]
MOVE_TO = BLOCKS[10]

# c) Word-shaped move: paragraph-mark revision + Word-style name and ids
MOVE_FROM_W = (
    '<w:p><w:pPr><w:rPr><w:moveFrom w:id="101" w:author="%s" w:date="%s"/>'
    "</w:rPr></w:pPr>" % (AUTHOR, DATE) +
    '<w:moveFromRangeStart w:id="1" w:name="move123456789" w:author="%s" w:date="%s"/>'
    '<w:moveFrom w:id="2" w:author="%s" w:date="%s">'
    '<w:r><w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>'
    '<w:moveFromRangeEnd w:id="1"/></w:p>' % (AUTHOR, DATE, AUTHOR, DATE))

MOVE_TO_W = (
    '<w:p><w:pPr><w:rPr><w:moveTo w:id="103" w:author="%s" w:date="%s"/>'
    "</w:rPr></w:pPr>" % (AUTHOR, DATE) +
    '<w:moveToRangeStart w:id="4" w:name="move123456789" w:author="%s" w:date="%s"/>'
    '<w:moveTo w:id="5" w:author="%s" w:date="%s">'
    '<w:r><w:t xml:space="preserve">moved here</w:t></w:r></w:moveTo>'
    '<w:moveToRangeEnd w:id="4"/></w:p>' % (AUTHOR, DATE, AUTHOR, DATE))

# d) revision wrappers only, no range markers
MOVE_BARE = (
    '<w:p><w:moveFrom w:id="202" w:author="%s" w:date="%s">'
    '<w:r><w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>'
    "</w:p>" % (AUTHOR, DATE))
MOVE_BARE_TO = (
    '<w:p><w:moveTo w:id="204" w:author="%s" w:date="%s">'
    '<w:r><w:t xml:space="preserve">moved here</w:t></w:r></w:moveTo>'
    "</w:p>" % (AUTHOR, DATE))


def build(name, math_fix=None, move=None, move_to=None):
    blocks = list(BLOCKS)
    if math_fix:
        blocks[31] = math_fix
    if move is not None:
        blocks[9] = move
    if move_to is not None:
        blocks[10] = move_to
    body = "".join(blocks)
    return name, body


CANDS = [
    build("r0_baseline"),
    build("r1_math_p", math_fix=MATH_FIXED),
    build("r2_math_inline", math_fix=MATH_INLINE),
    build("r3_math_p_move_word", math_fix=MATH_FIXED,
          move=MOVE_FROM_W, move_to=MOVE_TO_W),
    build("r4_math_p_move_bare", math_fix=MATH_FIXED,
          move=MOVE_BARE, move_to=MOVE_BARE_TO),
]

if __name__ == "__main__":
    for name, body in CANDS:
        probe(name, body)
