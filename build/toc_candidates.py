#!/usr/bin/env python3
"""
Isolate what Word 16.115 objects to in the corpus's TOC complex field.

The bisect (build/find_word_culprit.py) isolated the whole TOC paragraph as
the third cause: with it removed, the fixture opens; with it in, it does not.

usage: python3 build/toc_candidates.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from word_probe import probe  # noqa: E402


def p(inner):
    return "<w:p>" + inner + "</w:p>"


TOC_INSTR = ' TOC \\o "1-3" \\h \\z \\u '
RESULT = '<w:r><w:t>Right-click and choose Update Field to build the table of contents.</w:t></w:r>'


def complex_field(instr, dirty=True, separate=True, result=True, noproof=False):
    rpr = "<w:rPr><w:noProof/></w:rPr>" if noproof else ""
    out = '<w:r>%s<w:fldChar w:fldCharType="begin"%s/></w:r>' % (
        rpr, ' w:dirty="true"' if dirty else "")
    out += '<w:r>%s<w:instrText xml:space="preserve">%s</w:instrText></w:r>' % (rpr, instr)
    if separate:
        out += '<w:r>%s<w:fldChar w:fldCharType="separate"/></w:r>' % rpr
    if result:
        out += RESULT
    out += '<w:r>%s<w:fldChar w:fldCharType="end"/></w:r>' % rpr
    return out


CANDS = [
    ("n1_toc_as_is", p(complex_field(TOC_INSTR))),
    ("n2_toc_no_dirty", p(complex_field(TOC_INSTR, dirty=False))),
    ("n3_toc_no_separate", p(complex_field(TOC_INSTR, separate=False, result=False))),
    ("n4_page_complex", p(complex_field(" PAGE "))),
    ("n5_toc_short_switches", p(complex_field(' TOC \\o "1-3" '))),
    ("n6_toc_noproof", p(complex_field(TOC_INSTR, noproof=True))),
    ("n7_toc_fldsimple", p('<w:fldSimple w:instr=" TOC \\o &quot;1-3&quot; ">'
                           + RESULT + "</w:fldSimple>")),
    ("n8_toc_instr_no_xmlspace",
     p('<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
       "<w:r><w:instrText>" + TOC_INSTR + "</w:instrText></w:r>"
       '<w:r><w:fldChar w:fldCharType="separate"/></w:r>' + RESULT +
       '<w:r><w:fldChar w:fldCharType="end"/></w:r>')),
]

if __name__ == "__main__":
    for name, body in CANDS:
        probe(name, body)
