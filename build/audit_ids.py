#!/usr/bin/env python3
"""Audit id/marker usage in the fixture's word/document.xml."""
import re
import zipfile

z = zipfile.ZipFile("/Users/arthrod/temp/T/editors_trial/fixture/complex.docx")
d = z.read("word/document.xml").decode()

def show(title, pat):
    print("=== %s ===" % title)
    for m in re.finditer(pat, d):
        print("  ", m.group(0))
    print()

show("w14 paraId/textId", r'w14:(?:paraId|textId)="[^"]*"')
show("move range markers", r'<w:move\w*Range\w*\b[^>]*>|<w:move(?:From|To)\b[^>]*>')
show("bookmarks", r'<w:bookmark(?:Start|End)\b[^>]*>')
show("sdt ids", r'<w:id w:val="[^"]*"/>')
show("fields", r'<w:fldChar[^>]*>|<w:instrText[^>]*>[^<]*</w:instrText>|<w:fldSimple[^>]*>')
show("revision wrappers", r'<w:(?:ins|del)\b[^>]*>')
show("comment/perm markers", r'<w:(?:commentRangeStart|commentRangeEnd|commentReference|permStart|permEnd)\b[^>]*>')
show("footnote/endnote refs", r'<w:(?:footnoteReference|endnoteReference)\b[^>]*>')
show("docPr ids", r'<wp:docPr[^>]*>')
show("oMath", r'<m:oMathPara[^>]*>|<m:oMath[^>]*>')
show("altChunk", r'<w:altChunk[^>]*>')
show("object/OLE", r'<w:object[^>]*>|<o:OLEObject[^>]*>')
show("alternate content", r'<mc:AlternateContent[^>]*>|<mc:Choice[^>]*>|<mc:Fallback[^>]*>')
