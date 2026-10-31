#!/usr/bin/env python3
"""
Pin down what Word 16.115 objects to inside a w:moveFrom.

Data so far (/tmp/word_probe.log):
  moveTo   alone  -> OPENED
  moveFrom alone  -> REFUSED
  moveFrom+moveTo -> REFUSED   (with and without range markers,
                                 with and without paragraph-mark revisions)

usage: python3 build/move_shape_candidates.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_probe import probe  # noqa: E402

A = "Fixture Author"
D = "2026-01-15T09:30:00Z"


def p(inner):
    return "<w:p>" + inner + "</w:p>"


CANDS = [
    # 1 - the moveFrom content uses w:t instead of w:delText
    ("m1_movefrom_t", p('<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
                        "<w:r><w:t>moved away</w:t></w:r></w:moveFrom>" % (A, D))),
    # 2 - baseline: moveFrom with w:delText
    ("m2_movefrom_deltext", p('<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
                              "<w:r><w:delText xml:space=\"preserve\">moved away</w:delText></w:r>"
                              "</w:moveFrom>" % (A, D))),
    # 3 - control: a plain deletion, which the fixture's w:del already uses
    ("m3_del_control", p('<w:del w:id="102" w:author="%s" w:date="%s">'
                         "<w:r><w:delText xml:space=\"preserve\">moved away</w:delText></w:r>"
                         "</w:del>" % (A, D))),
    # 4 - moveFrom with an empty run
    ("m4_movefrom_emptyrun", p('<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
                               "<w:r></w:r></w:moveFrom>" % (A, D))),
    # 5 - control: an insertion
    ("m5_ins_control", p('<w:ins w:id="101" w:author="%s" w:date="%s">'
                         "<w:r><w:t>moved away</w:t></w:r></w:ins>" % (A, D))),
    # 6 - the range markers alone, with no moveFrom/moveTo element
    ("m6_markers_only",
     p('<w:moveFromRangeStart w:id="201" w:name="move1" w:author="%s" w:date="%s"/>'
       '<w:moveFromRangeEnd w:id="201"/>' % (A, D))),
    # 7 - moveFrom with the run marked deleted as well
    ("m7_movefrom_rpr_del",
     p('<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
       "<w:r><w:rPr><w:del/></w:rPr>"
       "<w:delText xml:space=\"preserve\">moved away</w:delText></w:r></w:moveFrom>" % (A, D))),
    # 8 - moveFrom whose text run has no xml:space
    ("m8_movefrom_nospace",
     p('<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
       "<w:r><w:delText>moved away</w:delText></w:r></w:moveFrom>" % (A, D))),
]

if __name__ == "__main__":
    for name, body in CANDS:
        probe(name, body)
