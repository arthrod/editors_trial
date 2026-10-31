#!/usr/bin/env python3
"""
Isolate the two confirmed refusals and iterate on their markup alone.

Each candidate is a two- or three-paragraph document built from the fixture's
own package, so a verdict is attributable to the markup under test.

usage: python3 build/isolate_candidates.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_probe import probe  # noqa: E402

AUTHOR = "Fixture Author"
DATE = "2026-01-15T09:30:00Z"

MOVE_FROM = (
    '<w:moveFromRangeStart w:id="201" w:name="move1" w:author="%s" w:date="%s"/>'
    '<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
    '<w:r><w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>'
    '<w:moveFromRangeEnd w:id="201"/>' % (AUTHOR, DATE, AUTHOR, DATE))

MOVE_TO = (
    '<w:moveToRangeStart w:id="203" w:name="move1" w:author="%s" w:date="%s"/>'
    '<w:moveTo w:id="204" w:author="%s" w:date="%s">'
    '<w:r><w:t xml:space="preserve">moved here</w:t></w:r></w:moveTo>'
    '<w:moveToRangeEnd w:id="203"/>' % (AUTHOR, DATE, AUTHOR, DATE))

MOVE_FROM_W = (
    '<w:moveFromRangeStart w:id="1" w:name="move123456789" w:author="%s" w:date="%s"/>'
    '<w:moveFrom w:id="2" w:author="%s" w:date="%s">'
    '<w:r><w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>'
    '<w:moveFromRangeEnd w:id="1"/>' % (AUTHOR, DATE, AUTHOR, DATE))

MOVE_TO_W = (
    '<w:moveToRangeStart w:id="4" w:name="move123456789" w:author="%s" w:date="%s"/>'
    '<w:moveTo w:id="5" w:author="%s" w:date="%s">'
    '<w:r><w:t xml:space="preserve">moved here</w:t></w:r></w:moveTo>'
    '<w:moveToRangeEnd w:id="4"/>' % (AUTHOR, DATE, AUTHOR, DATE))

MOVE_FROM_BARE = (
    '<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
    '<w:r><w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>'
    % (AUTHOR, DATE))

MOVE_TO_BARE = (
    '<w:moveTo w:id="204" w:author="%s" w:date="%s">'
    '<w:r><w:t xml:space="preserve">moved here</w:t></w:r></w:moveTo>'
    % (AUTHOR, DATE))

MOVE_FROM_MARK = (
    '<w:p><w:pPr><w:rPr><w:moveFrom w:id="301" w:author="%s" w:date="%s"/></w:rPr></w:pPr>'
    '<w:moveFromRangeStart w:id="201" w:name="move1" w:author="%s" w:date="%s"/>'
    '<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
    '<w:r><w:delText xml:space="preserve">moved away</w:delText></w:r></w:moveFrom>'
    '<w:moveFromRangeEnd w:id="201"/></w:p>' % (AUTHOR, DATE, AUTHOR, DATE, AUTHOR, DATE))

MOVE_TO_MARK = (
    '<w:p><w:pPr><w:rPr><w:moveTo w:id="304" w:author="%s" w:date="%s"/></w:rPr></w:pPr>'
    '<w:moveToRangeStart w:id="203" w:name="move1" w:author="%s" w:date="%s"/>'
    '<w:moveTo w:id="204" w:author="%s" w:date="%s">'
    '<w:r><w:t xml:space="preserve">moved here</w:t></w:r></w:moveTo>'
    '<w:moveToRangeEnd w:id="203"/></w:p>' % (AUTHOR, DATE, AUTHOR, DATE, AUTHOR, DATE))

MATH_BLOCK = ("<m:oMathPara><m:oMath>"
              '<m:r><w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'
              "<m:t>E = mc^2</m:t></m:r>"
              "</m:oMath></m:oMathPara>")


def p(inner):
    return "<w:p>" + inner + "</w:p>"


CANDS = [
    ("i0_plain", p("<w:r><w:t>plain</w:t></w:r>")),
    ("i1_math_block", MATH_BLOCK),
    ("i2_math_in_p", p(MATH_BLOCK)),
    ("i3_move_pair", p(MOVE_FROM) + p(MOVE_TO)),
    ("i4_move_word", p(MOVE_FROM_W) + p(MOVE_TO_W)),
    ("i5_move_bare", p(MOVE_FROM_BARE) + p(MOVE_TO_BARE)),
    ("i6_move_mark", MOVE_FROM_MARK + MOVE_TO_MARK),
    ("i7_movefrom_only", p(MOVE_FROM)),
    ("i8_moveto_only", p(MOVE_TO)),
]

if __name__ == "__main__":
    for name, body in CANDS:
        probe(name, body)
