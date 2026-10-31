#!/usr/bin/env python3
"""
Test the hypothesis: Word rejects a tracked move whose source text and
destination text differ.

Evidence so far (Microsoft Word 16.115, /tmp/word_probe.log):
  i7  moveFrom alone ("moved away")            -> REFUSED
  i8  moveTo   alone ("moved here")            -> OPENED
  i3  moveFrom "moved away" + moveTo "moved here" -> REFUSED
  i4  same, Word-style names/ids               -> REFUSED
  i5  same, no range markers                   -> REFUSED
  i6  same, with paragraph-mark revisions      -> REFUSED

Every failing shape has one thing in common: the text moved away is not the
text moved here. These candidates keep the source and destination identical.

usage: python3 build/move_text_candidates.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_probe import probe  # noqa: E402

AUTHOR = "Fixture Author"
DATE = "2026-01-15T09:30:00Z"
TEXT = "moved away"


def pair(marker_from, marker_to, text_from=TEXT, text_to=None,
         name="move1", id_from="201", id_to="203",
         id_movefrom="202", id_moveto="204"):
    text_to = text_from if text_to is None else text_to
    return (
        '<w:p><w:moveFromRangeStart w:id="%s" w:name="%s" w:author="%s" w:date="%s"/>'
        '<w:moveFrom w:id="%s" w:author="%s" w:date="%s">'
        '<w:r><w:delText xml:space="preserve">%s</w:delText></w:r></w:moveFrom>'
        '<w:moveFromRangeEnd w:id="%s"/></w:p>'
        '<w:p><w:moveToRangeStart w:id="%s" w:name="%s" w:author="%s" w:date="%s"/>'
        '<w:moveTo w:id="%s" w:author="%s" w:date="%s">'
        '<w:r><w:t xml:space="preserve">%s</w:t></w:r></w:moveTo>'
        '<w:moveToRangeEnd w:id="%s"/></w:p>'
        % (id_from, name, AUTHOR, DATE, id_movefrom, AUTHOR, DATE, text_from, id_from,
           id_to, name, AUTHOR, DATE, id_moveto, AUTHOR, DATE, text_to, id_to))


CANDS = [
    ("k1_same_text", pair(None, None)),
    ("k2_same_text_diff", pair(None, None, text_to="moved here")),
    ("k3_movefrom_same_only", pair(None, None, text_to=TEXT)),
]

if __name__ == "__main__":
    for name, body in CANDS:
        probe(name, body)
