#!/usr/bin/env python3
"""
Pin down the exact rule behind the third Word refusal.

n1_toc_as_is  (w:dirty="true" on the begin fldChar) -> REFUSED
n2_toc_no_dirty                                   -> OPENED
n4_page_complex  (PAGE field, also w:dirty)       -> REFUSED

So the attribute, not the field, is the problem. These probes separate
"w:dirty is present" from "w:dirty is present with the value true", locate
which fldChar may carry it, and confirm the whole fixture opens once it is
dropped.

usage: python3 build/dirty_candidates.py
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_probe import probe  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"
SRC = os.path.join(BASE, "fixture", "complex.docx")


def p(inner):
    return "<w:p>" + inner + "</w:p>"


def field(begin_attr="", sep_attr="", end_attr="", instr=" PAGE "):
    return p('<w:r><w:fldChar w:fldCharType="begin"%s/></w:r>'
             '<w:r><w:instrText xml:space="preserve">%s</w:instrText></w:r>'
             '<w:r><w:fldChar w:fldCharType="separate"%s/></w:r>'
             "<w:r><w:t>1</w:t></w:r>"
             '<w:r><w:fldChar w:fldCharType="end"%s/></w:r>'
             % (begin_attr, instr, sep_attr, end_attr))


CANDS = [
    ("p1_dirty_1", field(begin_attr=' w:dirty="1"')),
    ("p2_dirty_false", field(begin_attr=' w:dirty="false"')),
    ("p3_dirty_on_separate", field(sep_attr=' w:dirty="true"')),
    ("p4_fldlock_false", field(begin_attr=' w:fldLock="false"')),
    ("p5_dirty_true_on_end", field(end_attr=' w:dirty="true"')),
]

if __name__ == "__main__":
    for name, body in CANDS:
        probe(name, body)

    # and the whole fixture with the dirty attribute dropped
    with zipfile.ZipFile(SRC) as z:
        d = z.read("word/document.xml").decode("utf-8")
    fixed = d.replace(' w:dirty="true"', "")
    body = fixed[fixed.index("<w:body>") + len("<w:body>"):fixed.index("</w:body>")]
    probe("p6_fixture_no_dirty", body)
