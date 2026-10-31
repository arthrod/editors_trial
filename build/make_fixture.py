#!/usr/bin/env python3
"""
Build "complex.docx": a deliberately adversarial DOCX exercising OOXML exception cases.

Every feature here is chosen because at least one of the surveyed editors is documented
to lose it (unknown attributes, namespace prefixes, proofErr, w16du:dateUtc, fields,
content controls, charts, SmartArt, OLE, tracked moves, rPrChange/pPrChange, vMerge,
gridSpan, alternate content, altChunk, bookmarks, footnotes/endnotes, comments,
headers/footers, multi-section layout, bidi/RTL, math, symbols, permissions, ...).

The file is written as raw OOXML with hand-checked element ordering (CT_PPr / CT_RPr
sequence order) so that a strict consumer accepts it as-is.
"""
import os
import struct
import zlib
import zipfile

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixture", "complex.docx")

# ----------------------------------------------------------------------------- helpers
def png(w=16, h=16, rgb=(0x1F, 0x77, 0xB4)):
    """Minimal valid PNG (solid colour) built by hand."""
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))

DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

# ----------------------------------------------------------------------------- namespaces
NS = {
    "wpc": "http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas",
    "cx": "http://schemas.microsoft.com/office/drawing/2014/chartex",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "o": "urn:schemas-microsoft-com:office:office",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "v": "urn:schemas-microsoft-com:vml",
    "wp14": "http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "w10": "urn:schemas-microsoft-com:office:word",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "w16du": "http://schemas.microsoft.com/office/word/2023/wordml/word16du",
    "w16cex": "http://schemas.microsoft.com/office/word/2018/wordml/cex",
    "w16cid": "http://schemas.microsoft.com/office/word/2016/wordml/cid",
    "wpg": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "wpi": "http://schemas.microsoft.com/office/word/2010/wordprocessingInk",
    "wne": "http://schemas.microsoft.com/office/word/2006/wordml",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "wpgw": "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup",
    "w15_": "http://schemas.microsoft.com/office/word/2012/wordml",
}
NSDECL = " ".join('xmlns:%s="%s"' % (k, v) for k, v in NS.items())
IGNORABLE = "w14 w15 w16du w16cex w16cid wp14"

W = NS["w"]


def attrs(**kw):
    """Build an attribute string; keys use 'prefix:name' form or bare 'w:name'."""
    out = []
    for k, v in kw.items():
        if ":" in k:
            out.append('%s="%s"' % (k, v))
        else:
            out.append('w:%s="%s"' % (k, v))
    return (" " + " ".join(out)) if out else ""


def rpr(**kw):
    """Build a <w:rPr> honouring CT_RPr element order.

    Value convention: True -> empty toggle <w:k/>; False -> omitted;
    a string starting with '<' -> inserted verbatim (child-element form);
    any other string -> attribute-style element <w:k w:val="V"/>.
    """
    order = ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
             "dstrike", "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid",
             "vanish", "webHidden", "color", "spacing", "w", "kern", "position", "sz",
             "szCs", "highlight", "u", "effect", "bdr", "shd", "fitText", "vertAlign",
             "rtl", "cs", "em", "lang", "eastAsianLayout", "specVanish", "oMath",
             "rPrChange"]
    body = ""
    for k in order:
        if k not in kw:
            continue
        v = kw[k]
        if v is False or v is None:
            continue
        if v is True:
            body += "<w:%s/>" % k
        elif isinstance(v, str) and v.startswith("<"):
            body += v
        else:
            body += '<w:%s w:val="%s"/>' % (k, v)
    return "<w:rPr>%s</w:rPr>" % body if body else ""


def ppr(**kw):
    """Build a <w:pPr> honouring CT_PPr element order (same value convention as rpr)."""
    order = ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
             "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
             "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
             "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
             "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
             "suppressOverlap", "jc", "textDirection", "textAlignment",
             "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
             "pPrChange"]
    body = ""
    for k in order:
        if k not in kw:
            continue
        v = kw[k]
        if v is False or v is None:
            continue
        if v is True:
            body += "<w:%s/>" % k
        elif isinstance(v, str) and v.startswith("<"):
            body += v
        else:
            body += '<w:%s w:val="%s"/>' % (k, v)
    return "<w:pPr>%s</w:pPr>" % body if body else ""


def run(text=None, rpr_xml="", preserve=False, extra=""):
    """A <w:r>. `preserve` forces xml:space='preserve'.

    IMPORTANT: Word always writes xml:space="preserve" when a run's text has
    leading or trailing whitespace, and OOXML lets a consumer trim boundary
    whitespace when the attribute is absent. So the fixture applies the attribute
    automatically in that case, otherwise a spec-correct editor would be
    penalised for trimming whitespace the document never marked as significant.
    """
    t = ""
    if text is not None:
        if preserve is False and text != text.strip():
            preserve = True
        sp = ' xml:space="preserve"' if preserve else ""
        t = "<w:t%s>%s</w:t>" % (sp, text)
    return "<w:r>%s%s%s</w:r>" % (rpr_xml, t, extra)


def para(*runs, ppr_xml="", attrs_xml=""):
    return "<w:p%s>%s%s</w:p>" % (attrs_xml, ppr_xml, "".join(runs))


def txbx(text):
    """The VML fallback of an mc:AlternateContent.

    The fallback sits directly inside <mc:Fallback>, which itself sits inside the
    run that carries the AlternateContent - so it must contain the <w:pict>
    DIRECTLY. Wrapping it in another <w:r> would nest a run inside a run, which
    Word rejects.
    """
    return (
        '<w:pict>'
        '<v:shape id="_x0000_s1026" type="#_x0000_t202" style="width:200pt;height:50pt">'
        '<v:textbox><w:txbxContent>%s</w:txbxContent></v:textbox>'
        '<w10:wrap type="square"/>'
        '</v:shape>'
        '</w:pict>' % para(run("AlternateContent fallback text"))
    )


# ----------------------------------------------------------------------------- document.xml
DATE = "2026-01-15T09:30:00Z"
DATE_UTC = "2026-01-15T09:30:00.000Z"
AUTHOR = "Fixture Author"
EDITOR = "Round Trip Editor"

body = []

# --- 1. Plain paragraphs, styles, xml:space, tabs/breaks/symbols/hyphens -----------
body.append(para(
    run("Chapter 1: Heading with ", rpr_xml=rpr(b=True, sz="32")),
    run("mixed formatting", rpr_xml=rpr(b=False, i=True, sz="32")),
    run(".", rpr_xml=rpr(sz="32")),
    ppr_xml=ppr(pStyle="Heading1", keepNext=True, outlineLvl="0", rPr=rpr(b=True, sz="32"))))

body.append(para(
    run("Leading and trailing spaces ", preserve=True),
    run("are significant.", preserve=True),
    ppr_xml=ppr(pStyle="Normal")))

body.append(para(
    "<w:r><w:tab/></w:r>" +
    run("Tab separated") +
    "<w:r><w:br w:type=\"page\"/></w:r>" +
    run("After a page break") +
    "<w:r><w:noBreakHyphen/></w:r>" +
    run("nobreak") +
    "<w:r><w:softHyphen/></w:r>" +
    run("softhyphen") +
    "<w:r><w:sym w:font=\"Wingdings\" w:char=\"F0FC\"/></w:r>" +
    run("sym") +
    "<w:r><w:cr/></w:r>" +
    run("after CR")))

# --- 2. Unknown attributes + unknown elements (the classic fidelity trap) ---------
body.append(para(
    '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Arial"/>'
    '<w14:textOutline w14:w="9525" w14:cap="flat" w14:cmpd="sng" w14:algn="ctr">'
    '<w14:solidFill><w14:srgbClr w14:val="000000"/></w14:solidFill>'
    '<w14:prstDash w14:val="solid"/><w14:round/></w14:textOutline>'
    '<w:b w:val="1" w14:paraId="1A2B3C4D" w14:textId="77777777"/>'
    '</w:rPr>'
    '<w:t xml:space="preserve">run with unknown w14 attributes and w14 elements</w:t></w:r>'))

body.append(para(
    '<w:r><w:t xml:space="preserve">custom namespace attribute: </w:t></w:r>' +
    '<w:r><w:t xml:space="preserve">cs</w:t></w:r>' +
    '<w:r><w:rPr><w:rFonts w:cs="Times New Roman" w:ascii="Calibri"/></w:rPr>'
    '<w:t xml:space="preserve"> complex-script text</w:t></w:r>'))

# --- 3. w:proofErr (spell/grammar markers) ---------------------------------------
body.append(para(
    "<w:proofErr w:type=\"spellStart\"/>" +
    run("mispeling") +
    "<w:proofErr w:type=\"spellEnd\"/>" +
    "<w:proofErr w:type=\"gramStart\"/>" +
    run("grammaticaly") +
    "<w:proofErr w:type=\"gramEnd\"/>"))

# --- 4. Tracked changes: ins / del / rPrChange / pPrChange ------------------------
body.append(para(
    '<w:ins w:id="101" w:author="%s" w:date="%s" w16du:dateUtc="%s">'
    '<w:r><w:t xml:space="preserve">inserted text </w:t></w:r></w:ins>'
    '<w:del w:id="102" w:author="%s" w:date="%s" w16du:dateUtc="%s">'
    '<w:r><w:delText xml:space="preserve">deleted text</w:delText></w:r></w:del>'
    % (AUTHOR, DATE, DATE_UTC, AUTHOR, DATE, DATE_UTC)))

body.append(para(
    '<w:r><w:rPr><w:b/>'
    '<w:rPrChange w:id="103" w:author="%s" w:date="%s">'
    '<w:rPr><w:b w:val="0"/><w:i/></w:rPr></w:rPrChange>'
    '</w:rPr><w:t>run whose formatting was changed</w:t></w:r>' % (AUTHOR, DATE)))

body.append(para(
    '<w:pPr>'
    '<w:pStyle w:val="Normal"/>'
    '<w:pPrChange w:id="104" w:author="%s" w:date="%s">'
    '<w:pPr><w:spacing w:after="240"/><w:jc w:val="center"/></w:pPr>'
    '</w:pPrChange>'
    '</w:pPr>' % (AUTHOR, DATE) +
    run("paragraph whose properties were changed")))

# --- 5. Tracked moves (moveFrom / moveTo + range markers) -------------------------
# Word 16.115 refuses the file outright if the moved-from run uses w:delText:
# w:delText belongs to w:del only, and a move source carries ordinary w:t
# (verified by isolation probe, see build/move_shape_candidates.py).
body.append(para(
    '<w:moveFromRangeStart w:id="201" w:name="move1" w:author="%s" w:date="%s"/>'
    '<w:moveFrom w:id="202" w:author="%s" w:date="%s">'
    '<w:r><w:t xml:space="preserve">moved away</w:t></w:r></w:moveFrom>'
    '<w:moveFromRangeEnd w:id="201"/>' % (AUTHOR, DATE, AUTHOR, DATE)))

body.append(para(
    '<w:moveToRangeStart w:id="203" w:name="move1" w:author="%s" w:date="%s"/>'
    '<w:moveTo w:id="204" w:author="%s" w:date="%s">'
    '<w:r><w:t xml:space="preserve">moved here</w:t></w:r></w:moveTo>'
    '<w:moveToRangeEnd w:id="203"/>' % (AUTHOR, DATE, AUTHOR, DATE)))

# --- 6. Paragraph-mark revision (w:pPr/w:rPr/w:ins) ------------------------------
body.append(para(
    '<w:pPr><w:rPr>'
    '<w:ins w:id="301" w:author="%s" w:date="%s" w16du:dateUtc="%s"/>'
    '</w:rPr></w:pPr>' % (AUTHOR, DATE, DATE_UTC) +
    run("paragraph mark was inserted")))

# --- 7. Complex field: TOC with fldChar / instrText ------------------------------
# w:dirty is exercised with a FALSE value on purpose: Microsoft Word 16.115
# refuses to open a document in which any w:fldChar carries w:dirty with a
# true value ("true" or "1"), while w:dirty="false" is accepted
# (verified by isolation probe, see build/dirty_candidates.py).
body.append(para(
    '<w:r><w:fldChar w:fldCharType="begin" w:dirty="false"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    '<w:r><w:t>Right-click and choose Update Field to build the table of contents.</w:t></w:r>'
    '<w:r><w:fldChar w:fldCharType="end"/></w:r>'))

# --- 8. Simple field + bookmark + REF field -------------------------------------
body.append(para(
    '<w:bookmarkStart w:id="301" w:name="TargetBookmark"/>' +
    run("bookmarked anchor") +
    '<w:bookmarkEnd w:id="301"/>'))

body.append(para(
    '<w:fldSimple w:instr=" REF TargetBookmark \\h ">'
    '<w:r><w:t>bookmarked anchor</w:t></w:r></w:fldSimple>'))

body.append(para(
    '<w:fldSimple w:instr=" PAGE \\* MERGEFORMAT ">'
    '<w:r><w:t>1</w:t></w:r></w:fldSimple>'))

# --- 9. Content controls (sdt): rich text, date picker, dropdown, data-bound ----
body.append(
    '<w:sdt><w:sdtPr>'
    '<w:alias w:val="Rich text control"/>'
    '<w:tag w:val="rt-tag"/>'
    '<w:id w:val="111222333"/>'
    '<w:lock w:val="sdtLocked"/>'
    '<w:placeholder><w:docPart w:val="DefaultPlaceholder_1"/></w:placeholder>'
    '<w:showingPlcHdr/>'
    '<w:richText/>'
    '</w:sdtPr><w:sdtContent>' +
    para(run("content control content")) +
    '</w:sdtContent></w:sdt>')

body.append(
    '<w:sdt><w:sdtPr>'
    '<w:alias w:val="Date picker"/>'
    '<w:tag w:val="date-tag"/>'
    '<w:id w:val="444555666"/>'
    '<w:date w:fullDate="2026-01-15T00:00:00Z">'
    '<w:dateFormat w:val="yyyy-MM-dd"/>'
    '<w:lid w:val="en-US"/>'
    '<w:storeMappedDataAs w:val="dateTime"/>'
    '<w:calendar w:val="gregorian"/>'
    '</w:date>'
    '</w:sdtPr><w:sdtContent>' +
    para(run("2026-01-15")) +
    '</w:sdtContent></w:sdt>')

body.append(
    '<w:sdt><w:sdtPr>'
    '<w:alias w:val="Data bound"/>'
    '<w:tag w:val="bound"/>'
    '<w:id w:val="777888999"/>'
    '<w:dataBinding w:prefixMappings="xmlns:ns0=\'http://example.com/fixture\'" '
    'w:xpath="/ns0:root[1]/ns0:field[1]" '
    'w:storeItemID="{5A1B2C3D-4E5F-6071-8293-A4B5C6D7E8F9}"/>'
    '<w:text/>'
    '</w:sdtPr><w:sdtContent>' +
    para(run("bound value")) +
    '</w:sdtContent></w:sdt>')

# --- 10. Nested content control ---------------------------------------------------
body.append(
    '<w:sdt><w:sdtPr><w:alias w:val="Outer"/><w:id w:val="111000111"/>'
    '<w:group/></w:sdtPr><w:sdtContent>' +
    '<w:sdt><w:sdtPr><w:alias w:val="Inner"/><w:id w:val="111000222"/>'
    '<w:text/></w:sdtPr><w:sdtContent>' +
    para(run("inner nested content")) +
    '</w:sdtContent></w:sdt>' +
    '</w:sdtContent></w:sdt>')

# --- 11. Numbering (multi-level list) ---------------------------------------------
body.append(para(
    run("List item level 1"),
    ppr_xml=ppr(pStyle="ListParagraph",
                 numPr='<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')))
body.append(para(
    run("List item level 2"),
    ppr_xml=ppr(pStyle="ListParagraph",
                 numPr='<w:numPr><w:ilvl w:val="1"/><w:numId w:val="1"/></w:numPr>')))

# --- 12. Tables: gridSpan, vMerge, tblHeader, nested table, borders, shading ------
def tc(width, content, **kw):
    """Build a <w:tc>. CT_TcPr order: tcW, gridSpan, vMerge, shd, textDirection, vAlign."""
    tcpr = ""
    if "tcW" in kw:
        tcpr += '<w:tcW w:w="%s" w:type="dxa"/>' % kw["tcW"]
    if "gridSpan" in kw:
        tcpr += '<w:gridSpan w:val="%s"/>' % kw["gridSpan"]
    if "vMerge" in kw:
        tcpr += '<w:vMerge%s/>' % (' w:val="restart"' if kw["vMerge"] == "restart" else "")
    if "shd" in kw:
        tcpr += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % kw["shd"]
    if "textDirection" in kw:
        tcpr += '<w:textDirection w:val="%s"/>' % kw["textDirection"]
    if "vAlign" in kw:
        tcpr += '<w:vAlign w:val="%s"/>' % kw["vAlign"]
    tcpr = "<w:tcPr>%s</w:tcPr>" % tcpr if tcpr else ""
    return "<w:tc>%s%s</w:tc>" % (tcpr, content)

tbl_rows = []
tbl_rows.append(
    "<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>" +
    tc("2400", para(run("Header A", rpr_xml=rpr(b=True))), tcW="2400") +
    tc("2400", para(run("Header B", rpr_xml=rpr(b=True))), tcW="2400") +
    tc("2400", para(run("Header C", rpr_xml=rpr(b=True))), tcW="2400") +
    "</w:tr>")
tbl_rows.append(
    "<w:tr>" +
    tc("4800", para(run("Spans two columns")), gridSpan="2", tcW="4800", shd="D9E2F3") +
    tc("2400", para(run("Normal cell")), tcW="2400") +
    "</w:tr>")
tbl_rows.append(
    "<w:tr>" +
    tc("2400", para(run("vert merged, first")), vMerge="restart", tcW="2400") +
    tc("2400", para(run("vert merged, second")), vMerge="continue", tcW="2400") +
    tc("2400", para(run("vertical text")), textDirection="btLr", tcW="2400") +
    "</w:tr>")
tbl_rows.append(
    "<w:tr>" +
    tc("2400", para(run("vert merged, continuation")), vMerge="continue", tcW="2400") +
    tc("2400", para(run("right aligned")), tcW="2400") +
    tc("2400", para(run("bottom aligned")), vAlign="bottom", tcW="2400") +
    "</w:tr>")
# nested table inside a cell
nested = (
    "<w:tbl><w:tblPr><w:tblW w:w=\"0\" w:type=\"auto\"/>"
    "<w:tblBorders>"
    "<w:top w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
    "<w:left w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
    "<w:bottom w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
    "<w:right w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
    "<w:insideH w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
    "<w:insideV w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"auto\"/>"
    "</w:tblBorders></w:tblPr>"
    "<w:tblGrid><w:gridCol w:w=\"1500\"/><w:gridCol w:w=\"1500\"/></w:tblGrid>"
    "<w:tr>" + tc("1500", para(run("nested 1")), tcW="1500") +
    tc("1500", para(run("nested 2")), tcW="1500") + "</w:tr></w:tbl>" +
    para(run("after nested table"))
)
tbl_rows.append(
    "<w:tr>" +
    tc("7200", nested, gridSpan="3", tcW="7200") +
    "</w:tr>")
# row with tracked row insertion / deletion
tbl_rows.append(
    "<w:tr><w:trPr><w:ins w:id=\"401\" w:author=\"%s\" w:date=\"%s\"/></w:trPr>" % (AUTHOR, DATE) +
    tc("7200", para(run("This row was inserted (trIns)")), gridSpan="3", tcW="7200") +
    "</w:tr>")
tbl_rows.append(
    "<w:tr><w:trPr><w:del w:id=\"402\" w:author=\"%s\" w:date=\"%s\"/></w:trPr>" % (AUTHOR, DATE) +
    tc("7200", para('<w:del w:id="403" w:author="%s" w:date="%s">'
                    '<w:r><w:delText>This row was deleted (trDel)</w:delText></w:r></w:del>'
                    % (AUTHOR, DATE)), gridSpan="3", tcW="7200") +
    "</w:tr>")

table = (
    "<w:tbl><w:tblPr>"
    '<w:tblStyle w:val="TableGrid"/>'
    '<w:tblW w:w="7200" w:type="dxa"/>'
    '<w:jc w:val="left"/>'
    '<w:tblInd w:w="0" w:type="dxa"/>'
    "<w:tblBorders>"
    '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    "</w:tblBorders>"
    '<w:tblLayout w:type="fixed"/>'
    '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" '
    'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/>'
    "</w:tblPr>"
    '<w:tblGrid><w:gridCol w:w="2400"/><w:gridCol w:w="2400"/><w:gridCol w:w="2400"/></w:tblGrid>'
    + "".join(tbl_rows) + "</w:tbl>")
body.append(table)
body.append(para(run("Paragraph after the table.")))

# --- 13. Footnote and endnote references -----------------------------------------
body.append(para(
    run("A sentence with a footnote"),
    '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
    '<w:footnoteReference w:id="2"/></w:r>',
    run(" and an endnote"),
    '<w:r><w:rPr><w:rStyle w:val="EndnoteReference"/></w:rPr>'
    '<w:endnoteReference w:id="2"/></w:r>'))

# --- 14. Comment reference --------------------------------------------------------
body.append(para(
    run("A sentence with a comment"),
    '<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>'
    '<w:commentReference w:id="0"/></w:r>'))

# --- 15. Image (DrawingML inline) -------------------------------------------------
drawing = (
    "<w:r><w:drawing>"
    '<wp:inline distT="0" distB="0" distL="0" distR="0">'
    '<wp:extent cx="1143000" cy="1143000"/>'
    '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
    '<wp:docPr id="1" name="Picture 1" descr="fixture image"/>'
    '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
    "<a:graphic><a:graphicData "
    'uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    "<pic:pic>"
    '<pic:nvPicPr><pic:cNvPr id="1" name="image1.png"/><pic:cNvPicPr/></pic:nvPicPr>'
    '<pic:blipFill><a:blip r:embed="rIdImage"/>'
    "<a:stretch><a:fillRect/></a:stretch></pic:blipFill>"
    '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1143000" cy="1143000"/></a:xfrm>'
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
    "</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>")
body.append(para(drawing))

# --- 16. Chart (DrawingML graphicFrame -> chart part) ------------------------------
chart = (
    "<w:r><w:drawing>"
    '<wp:inline distT="0" distB="0" distL="0" distR="0">'
    '<wp:extent cx="5486400" cy="3200400"/>'
    '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
    '<wp:docPr id="2" name="Chart 1"/>'
    "<wp:cNvGraphicFramePr/>"
    '<a:graphic><a:graphicData '
    'uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
    '<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'r:id="rIdChart"/>'
    "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>")
body.append(para(chart))

# --- 17. SmartArt (diagram) --------------------------------------------------------
smartart = (
    "<w:r><w:drawing>"
    '<wp:inline distT="0" distB="0" distL="0" distR="0">'
    '<wp:extent cx="5486400" cy="3200400"/>'
    '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
    '<wp:docPr id="3" name="Diagram 1"/>'
    "<wp:cNvGraphicFramePr/>"
    '<a:graphic><a:graphicData '
    'uri="http://schemas.openxmlformats.org/drawingml/2006/diagram">'
    '<dgm:relIds xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'r:dm="rIdDgmData" r:lo="rIdDgmLayout" r:qs="rIdDgmQuickStyle" r:cs="rIdDgmColors"/>'
    "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>")
body.append(para(smartart))

# --- 18. OLE object (embedded Word document) -------------------------------------
# Word stores an embedded Word document as the raw .docx bytes behind an
# o:OLEObject with ProgID="Word.Document.12". A random blob in place of that
# makes Word refuse the package, so a genuine minimal .docx is embedded here.
ole = (
    "<w:r><w:object w:dxaOrig=\"2160\" w:dyaOrig=\"1440\">"
    '<v:shape id="_x0000_i1025" type="#_x0000_t75" style="width:108pt;height:72pt">'
    '<v:imagedata r:id="rIdOleImage" o:title=""/></v:shape>'
    '<o:OLEObject Type="Embed" ProgID="Word.Document.12" ShapeID="_x0000_i1025" '
    'DrawAspect="Icon" ObjectID="_1234567890" r:id="rIdOleObject"/>'
    "</w:object></w:r>")
body.append(para(ole))

# --- 19. AlternateContent (mc:Choice with w:drawing / mc:Fallback with w:pict) -----
alt = (
    "<w:r><mc:AlternateContent>"
    '<mc:Choice Requires="wps">'
    "<w:drawing>"
    '<wp:inline distT="0" distB="0" distL="0" distR="0">'
    '<wp:extent cx="2540000" cy="635000"/>'
    '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
    '<wp:docPr id="4" name="Shape 1"/>'
    "<wp:cNvGraphicFramePr/>"
    '<a:graphic><a:graphicData '
    'uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
    "<wps:wsp>"
    '<wps:cNvSpPr txBox="1"/>'
    "<wps:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"2540000\" cy=\"635000\"/></a:xfrm>"
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
    '<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
    "</wps:spPr>"
    '<wps:txbx><w:txbxContent><w:p><w:r><w:t>Text box content</w:t></w:r></w:p></w:txbxContent></wps:txbx>'
    '<wps:bodyPr rot="0" anchor="t"/>'
    "</wps:wsp></a:graphicData></a:graphic></wp:inline></w:drawing>"
    "</mc:Choice>"
    "<mc:Fallback>" + txbx("AlternateContent fallback text") + "</mc:Fallback>"
    "</mc:AlternateContent></w:r>")
body.append(para(alt))

# --- 20. Math (OMML) ---------------------------------------------------------------
# A display equation must live inside a w:p. As a direct child of w:body the
# transitional schema allows it, but Word 16.115 refuses the whole file
# (verified by isolation probe, see build/isolate_candidates.py).
math = (
    "<w:p><m:oMathPara><m:oMath>"
    '<m:r><w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'
    "<m:t>E = mc^2</m:t></m:r>"
    "</m:oMath></m:oMathPara></w:p>")
body.append(math)

# --- 21. RTL / bidi ------------------------------------------------------------------
body.append(para(
    run("שלום עולם - Hebrew text right to left"),
    ppr_xml=ppr(bidi=True, jc="right", rPr=rpr(rtl=True))))

body.append(para(
    '<w:r><w:rPr><w:rtl/></w:rPr><w:t>rtl run</w:t></w:r>' +
    '<w:r><w:rPr><w:szCs w:val="40"/></w:rPr><w:t>complex script size</w:t></w:r>'))

# --- 22. Hidden / special run properties ---------------------------------------------
body.append(para(
    run("hidden text", rpr_xml=rpr(vanish=True)) +
    run("no proof", rpr_xml=rpr(noProof=True)) +
    run("caps small", rpr_xml=rpr(caps=True, smallCaps=True, strike=True)) +
    run("vert", rpr_xml=rpr(vertAlign="superscript")) +
    run("kern", rpr_xml=rpr(kern="28", spacing="10", position="4", sz="24", szCs="24")) +
    run("lang", rpr_xml=rpr(lang="ja-JP", eastAsianLayout="<w:eastAsianLayout w:id=\"1\" w:vert=\"1\"/>"))))

# --- 23. Permission ranges (editable regions) ----------------------------------------
body.append(para(
    '<w:permStart w:id="501" w:edGrp="everyone"/>' +
    run("This region is editable by everyone") +
    '<w:permEnd w:id="501"/>'))

# --- 24. Section 1 end -> landscape section with its own header, columns -------------
sect1 = (
    "<w:sectPr>"
    '<w:headerReference w:type="default" r:id="rIdHeader1"/>'
    '<w:footerReference w:type="default" r:id="rIdFooter1"/>'
    '<w:headerReference w:type="first" r:id="rIdHeader2"/>'
    '<w:headerReference w:type="even" r:id="rIdHeader1"/>'
    "<w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
    '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
    'w:header="720" w:footer="720" w:gutter="0"/>'
    '<w:cols w:space="720" w:num="1"/>'
    '<w:docGrid w:linePitch="360"/>'
    "</w:sectPr>")
body.append(para(run("End of section 1."), ppr_xml=ppr(sectPr=sect1)))

body.append(para(run("Landscape section content."),
                 ppr_xml=ppr(sectPr="<w:sectPr>"
                             '<w:headerReference w:type="default" r:id="rIdHeader1"/>'
                             '<w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>'
                             '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
                             'w:header="720" w:footer="720" w:gutter="0"/>'
                             '<w:pgNumType w:fmt="lowerRoman" w:start="1"/>'
                             '<w:cols w:space="720" w:num="2"/>'
                             '<w:docGrid w:linePitch="360"/>'
                             "</w:sectPr>")))

# --- 25. altChunk (HTML import part) ---------------------------------------------------
body.append('<w:altChunk r:id="rIdAltChunk"/>')

# --- 26. Final section properties --------------------------------------------------------
final_sect = (
    "<w:sectPr>"
    '<w:headerReference w:type="default" r:id="rIdHeader1"/>'
    '<w:footerReference w:type="default" r:id="rIdFooter1"/>'
    '<w:footerReference w:type="first" r:id="rIdFooter2"/>'
    '<w:pgSz w:w="12240" w:h="15840"/>'
    '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
    'w:header="720" w:footer="720" w:gutter="0"/>'
    '<w:paperSrc w:first="10" w:other="10"/>'
    '<w:pgBorders w:offsetFrom="page">'
    '<w:top w:val="single" w:sz="4" w:space="24" w:color="auto"/>'
    '<w:left w:val="single" w:sz="4" w:space="24" w:color="auto"/>'
    '<w:bottom w:val="single" w:sz="4" w:space="24" w:color="auto"/>'
    '<w:right w:val="single" w:sz="4" w:space="24" w:color="auto"/>'
    "</w:pgBorders>"
    '<w:cols w:space="720" w:num="1"/>'
    '<w:docGrid w:linePitch="360"/>'
    "</w:sectPr>")
body.append(para(run("Last paragraph.")))
body.append(final_sect)

document_xml = (
    DECL +
    '<w:document %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    "<w:body>" + "".join(body) + "</w:body></w:document>"
)

# ----------------------------------------------------------------------------- styles.xml
styles_xml = DECL + (
    '<w:styles %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    "<w:docDefaults>"
    "<w:rPrDefault><w:rPr>"
    '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="MS Mincho" w:cs="Arial"/>'
    '<w:sz w:val="22"/><w:szCs w:val="22"/>'
    '<w:lang w:val="en-US" w:eastAsia="ja-JP" w:bidi="ar-SA"/>'
    "</w:rPr></w:rPrDefault>"
    "<w:pPrDefault><w:pPr>"
    '<w:spacing w:after="160" w:line="259" w:lineRule="auto"/>'
    "</w:pPr></w:pPrDefault>"
    "</w:docDefaults>"
    '<w:latentStyles w:defLockedState="0" w:defUIPriority="99" w:defSemiHidden="1" '
    'w:defUnhideWhenUsed="1" w:defQFormat="0" w:count="371">'
    '<w:lsdException w:name="Normal" w:uiPriority="0" w:qFormat="1"/>'
    '<w:lsdException w:name="heading 1" w:uiPriority="9" w:qFormat="1"/>'
    '<w:lsdException w:name="caption" w:uiPriority="35" w:qFormat="1"/>'
    "</w:latentStyles>"
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
    '<w:name w:val="Normal"/><w:qFormat/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1">'
    '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
    '<w:link w:val="Heading1Char"/><w:uiPriority w:val="9"/><w:qFormat/>'
    '<w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="240" w:after="0"/>'
    '<w:outlineLvl w:val="0"/></w:pPr>'
    '<w:rPr><w:rFonts w:asciiTheme="majorHAnsi" w:hAnsiTheme="majorHAnsi"/>'
    '<w:color w:val="2F5496"/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>'
    '<w:style w:type="character" w:customStyle="1" w:styleId="Heading1Char">'
    '<w:name w:val="Heading 1 Char"/><w:link w:val="Heading1"/>'
    '<w:rPr><w:rFonts w:asciiTheme="majorHAnsi" w:hAnsiTheme="majorHAnsi"/>'
    '<w:color w:val="2F5496"/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="ListParagraph">'
    '<w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:uiPriority w:val="34"/><w:qFormat/>'
    '<w:pPr><w:ind w:left="720"/><w:contextualSpacing/></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="FootnoteText">'
    '<w:name w:val="footnote text"/><w:basedOn w:val="Normal"/>'
    '<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>'
    '<w:style w:type="character" w:styleId="FootnoteReference">'
    '<w:name w:val="footnote reference"/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="EndnoteText">'
    '<w:name w:val="endnote text"/><w:basedOn w:val="Normal"/>'
    '<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>'
    '<w:style w:type="character" w:styleId="EndnoteReference">'
    '<w:name w:val="endnote reference"/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>'
    '<w:style w:type="character" w:styleId="CommentReference">'
    '<w:name w:val="annotation reference"/><w:rPr><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="CommentText">'
    '<w:name w:val="annotation text"/><w:basedOn w:val="Normal"/>'
    '<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>'
    '<w:style w:type="table" w:default="1" w:styleId="TableNormal">'
    '<w:name w:val="Normal Table"/><w:uiPriority w:val="99"/><w:semiHidden/><w:unhideWhenUsed/>'
    '<w:tblPr><w:tblInd w:w="0" w:type="dxa"/>'
    '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
    '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
    '<w:style w:type="table" w:styleId="TableGrid">'
    '<w:name w:val="Table Grid"/><w:basedOn w:val="TableNormal"/><w:uiPriority w:val="39"/>'
    "<w:tblPr><w:tblBorders>"
    '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    "</w:tblBorders></w:tblPr></w:style>"
    "</w:styles>")

# ----------------------------------------------------------------------------- numbering.xml
lvl = ""
for i in range(9):
    fmt = ["decimal", "lowerLetter", "lowerRoman"][i % 3]
    txt = "%" + str(i + 1) + "."
    lvl += ('<w:lvl w:ilvl="%d"><w:start w:val="1"/><w:numFmt w:val="%s"/>'
            '<w:lvlText w:val="%s"/><w:lvlJc w:val="left"/>'
            '<w:pPr><w:ind w:left="%d" w:hanging="360"/></w:pPr>'
            '<w:rPr><w:rFonts w:hint="default"/></w:rPr></w:lvl>'
            % (i, fmt, txt, 720 + i * 720))
numbering_xml = DECL + (
    '<w:numbering %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:abstractNum w:abstractNumId="0" w15:restartNumberingAfterBreak="0">'
    '<w:nsid w:val="1A2B3C4D"/><w:multiLevelType w:val="hybridMultilevel"/>'
    '<w:tmpl w:val="0409001D"/>' + lvl + "</w:abstractNum>"
    '<w:num w:numId="1" w16cid:durableId="12345678">'
    '<w:abstractNumId w:val="0"/></w:num>'
    "</w:numbering>")

# ----------------------------------------------------------------------------- settings.xml
settings_xml = DECL + (
    '<w:settings %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:zoom w:percent="100"/>'
    "<w:proofState w:spelling=\"clean\" w:grammar=\"clean\"/>"
    "<w:documentProtection w:edit=\"readOnly\" w:enforcement=\"1\" "
    'w:cryptProviderType="rsaAES" w:cryptAlgorithmClass="hash" '
    'w:cryptAlgorithmType="typeAny" w:cryptAlgorithmSid="14" '
    'w:cryptSpinCount="100000" w:hash="AAAA" w:salt="BBBB"/>'
    '<w:defaultTabStop w:val="720"/>'
    "<w:evenAndOddHeaders/>"
    '<w:footnotePr><w:footnote w:id="-1"/><w:footnote w:id="0"/></w:footnotePr>'
    '<w:endnotePr><w:endnote w:id="-1"/><w:endnote w:id="0"/></w:endnotePr>'
    '<w:compat><w:compatSetting w:name="compatibilityMode" '
    'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'
    '<w:rsids><w:rsidRoot w:val="00A12345"/><w:rsid w:val="00A12345"/></w:rsids>'
    '<w:themeFontLang w:val="en-US" w:eastAsia="ja-JP"/>'
    '<w:clrSchemeMapping w:bg1="light1" w:t1="dark1" w:bg2="light2" w:t2="dark2" '
    'w:accent1="accent1" w:accent2="accent2" w:accent3="accent3" w:accent4="accent4" '
    'w:accent5="accent5" w:accent6="accent6" w:hyperlink="hyperlink" '
    'w:followedHyperlink="followedHyperlink"/>'
    "</w:settings>")

# ----------------------------------------------------------------------------- headers/footers
header1_xml = DECL + (
    '<w:hdr %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="center"/></w:pPr>'
    '<w:r><w:rPr><w:b/></w:rPr><w:t>Default header</w:t></w:r></w:p>'
    '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
    '<w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p>'
    "</w:hdr>")

header2_xml = DECL + (
    '<w:hdr %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="right"/></w:pPr>'
    '<w:r><w:t>First page header</w:t></w:r></w:p>'
    '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
    '<w:r><w:t>Header with tracked change</w:t></w:r>'
    '<w:ins w:id="901" w:author="%s" w:date="%s" w16du:dateUtc="%s">'
    '<w:r><w:t xml:space="preserve"> (added)</w:t></w:r></w:ins>'
    "</w:p></w:hdr>" % (AUTHOR, DATE, DATE_UTC))

footer1_xml = DECL + (
    '<w:ftr %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="center"/></w:pPr>'
    '<w:r><w:t xml:space="preserve">Footer text </w:t></w:r>'
    '<w:r><w:t>page </w:t></w:r>'
    '<w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple></w:p>'
    "</w:ftr>")

footer2_xml = DECL + (
    '<w:ftr %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>'
    '<w:r><w:t>First page footer</w:t></w:r></w:p></w:ftr>')

# ----------------------------------------------------------------------------- notes
footnotes_xml = DECL + (
    '<w:footnotes %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" '
    'w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>'
    '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing w:after="0" '
    'w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
    '<w:footnote w:id="2"><w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>'
    '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>'
    '<w:r><w:t xml:space="preserve"> This is the footnote body with a </w:t></w:r>'
    '<w:r><w:t>bold word</w:t></w:r></w:p></w:footnote>'
    "</w:footnotes>")

endnotes_xml = DECL + (
    '<w:endnotes %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:endnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:endnote>'
    '<w:endnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:endnote>'
    '<w:endnote w:id="2"><w:p><w:pPr><w:pStyle w:val="EndnoteText"/></w:pPr>'
    '<w:r><w:rPr><w:rStyle w:val="EndnoteReference"/></w:rPr><w:endnoteRef/></w:r>'
    '<w:r><w:t xml:space="preserve"> This is the endnote body.</w:t></w:r></w:p></w:endnote>'
    "</w:endnotes>")

comments_xml = DECL + (
    '<w:comments %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:comment w:id="0" w:author="%s" w:date="%s" w:initials="FA">'
    '<w:p><w:pPr><w:pStyle w:val="CommentText"/></w:pPr>'
    '<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:annotationRef/></w:r>'
    '<w:r><w:t>This is a comment body.</w:t></w:r></w:p></w:comment>'
    "</w:comments>" % (AUTHOR, DATE))

# ----------------------------------------------------------------------------- chart / smartart / ole parts
chart1_xml = DECL + (
    '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<c:date1904 val="0"/><c:lang val="en-US"/><c:roundedCorners val="0"/>'
    "<c:chart>"
    '<c:plotArea><c:layout/>'
    '<c:barChart><c:barDir val="col"/><c:grouping val="clustered"/><c:varyColors val="0"/>'
    '<c:ser><c:idx val="0"/><c:order val="0"/>'
    "<c:tx><c:strRef><c:f>Sheet1!$B$1</c:f>"
    '<c:strCache><c:ptCount val="1"/><c:pt idx="0"><c:v>Series 1</c:v></c:pt></c:strCache>'
    "</c:strRef></c:tx>"
    '<c:cat><c:strRef><c:f>Sheet1!$A$2:$A$4</c:f><c:strCache><c:ptCount val="3"/>'
    '<c:pt idx="0"><c:v>Cat A</c:v></c:pt><c:pt idx="1"><c:v>Cat B</c:v></c:pt>'
    '<c:pt idx="2"><c:v>Cat C</c:v></c:pt></c:strCache></c:strRef></c:cat>'
    '<c:val><c:numRef><c:f>Sheet1!$B$2:$B$4</c:f><c:numCache><c:formatCode>General</c:formatCode>'
    '<c:ptCount val="3"/><c:pt idx="0"><c:v>4.3</c:v></c:pt><c:pt idx="1"><c:v>2.5</c:v></c:pt>'
    '<c:pt idx="2"><c:v>3.5</c:v></c:pt></c:numCache></c:numRef></c:val>'
    "</c:ser>"
    '<c:gapWidth val="150"/><c:axId val="111111111"/><c:axId val="222222222"/></c:barChart>'
    '<c:catAx><c:axId val="111111111"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
    '<c:delete val="0"/><c:axPos val="b"/><c:crossAx val="222222222"/></c:catAx>'
    '<c:valAx><c:axId val="222222222"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
    '<c:delete val="0"/><c:axPos val="l"/><c:crossAx val="111111111"/></c:valAx>'
    "</c:plotArea>"
    '<c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend>'
    '<c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/>'
    "</c:chart>"
    "</c:chartSpace>")

chart1_rels = DECL + (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package" '
    'Target="../embeddings/Microsoft_Excel_Worksheet.xlsx"/>'
    "</Relationships>")

dgm_data = DECL + (
    '<dgm:dataModel xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
    '<dgm:ptLst>'
    '<dgm:pt modelId="{11111111-0000-0000-0000-000000000001}" type="doc">'
    '<dgm:prSet loTypeId="urn:microsoft.com/office/officeart/2005/8/layout/hierarchy1" '
    'loCatId="hierarchy" qsTypeId="urn:microsoft.com/office/officeart/2005/8/quickstyle/simple1" '
    'qsCatId="simple" csTypeId="urn:microsoft.com/office/officeart/2005/8/colors/accent1_2" '
    'csCatId="accent1"/>'
    '<dgm:spPr/><dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></dgm:t>'
    "</dgm:pt>"
    '<dgm:pt modelId="{11111111-0000-0000-0000-000000000002}">'
    '<dgm:prSet phldr="1"/><dgm:spPr/>'
    "<dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang=\"en-US\"/><a:t>Step one</a:t></a:r></a:p></dgm:t>"
    "</dgm:pt>"
    '<dgm:pt modelId="{11111111-0000-0000-0000-000000000003}">'
    '<dgm:prSet phldr="1"/><dgm:spPr/>'
    "<dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang=\"en-US\"/><a:t>Step two</a:t></a:r></a:p></dgm:t>"
    "</dgm:pt>"
    "</dgm:ptLst>"
    '<dgm:cxnLst>'
    '<dgm:cxn modelId="{22222222-0000-0000-0000-000000000001}" '
    'srcId="{11111111-0000-0000-0000-000000000001}" '
    'destId="{11111111-0000-0000-0000-000000000002}" srcOrd="0" destOrd="0"/>'
    '<dgm:cxn modelId="{22222222-0000-0000-0000-000000000002}" '
    'srcId="{11111111-0000-0000-0000-000000000001}" '
    'destId="{11111111-0000-0000-0000-000000000003}" srcOrd="1" destOrd="0"/>'
    "</dgm:cxnLst>"
    "<dgm:bg/><dgm:whole/>"
    "</dgm:dataModel>")

dgm_layout = DECL + (
    '<dgm:layoutDef xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'uniqueId="urn:microsoft.com/office/officeart/2005/8/layout/hierarchy1">'
    '<dgm:title val=""/><dgm:desc val=""/>'
    "<dgm:catLst><dgm:cat type=\"hierarchy\" pri=\"1000\"/></dgm:catLst>"
    "<dgm:sampData><dgm:dataModel><dgm:ptLst/><dgm:cxnLst/><dgm:bg/><dgm:whole/></dgm:dataModel></dgm:sampData>"
    "<dgm:styleData><dgm:dataModel><dgm:ptLst/><dgm:cxnLst/><dgm:bg/><dgm:whole/></dgm:dataModel></dgm:styleData>"
    "<dgm:clrData><dgm:dataModel><dgm:ptLst/><dgm:cxnLst/><dgm:bg/><dgm:whole/></dgm:dataModel></dgm:clrData>"
    '<dgm:layoutNode name="root">'
    '<dgm:alg type="hierRoot"/><dgm:shape type="none"/>'
    "</dgm:layoutNode>"
    "</dgm:layoutDef>")

dgm_colors = DECL + (
    '<dgm:colorsDef xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'uniqueId="urn:microsoft.com/office/officeart/2005/8/colors/accent1_2">'
    '<dgm:title val=""/><dgm:desc val=""/>'
    '<dgm:catLst><dgm:cat type="accent1" pri="11200"/></dgm:catLst>'
    "<dgm:styleLbl name=\"node0\"><dgm:fillClrLst meth=\"repeat\">"
    '<a:schemeClr val="accent1"/></dgm:fillClrLst>'
    '<dgm:linClrLst meth="repeat"><a:schemeClr val="lt1"/></dgm:linClrLst>'
    '<dgm:effectClrLst/><dgm:txLinClrLst/>'
    "<dgm:txFillClrLst/><dgm:txEffectClrLst/></dgm:styleLbl>"
    "</dgm:colorsDef>")

dgm_quickstyle = DECL + (
    '<dgm:styleDef xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'uniqueId="urn:microsoft.com/office/officeart/2005/8/quickstyle/simple1">'
    '<dgm:title val=""/><dgm:desc val=""/>'
    '<dgm:catLst><dgm:cat type="simple" pri="10100"/></dgm:catLst>'
    "<dgm:scene3d><a:camera prst=\"orthographicFront\"/>"
    '<a:lightRig rig="threePt" dir="t"/></dgm:scene3d>'
    "<dgm:styleLbl name=\"node0\"><dgm:scene3d><a:camera prst=\"orthographicFront\"/>"
    '<a:lightRig rig="threePt" dir="t"/></dgm:scene3d>'
    "<dgm:sp3d/><dgm:txPr/><dgm:style><a:lnRef idx=\"0\"><a:scrgbClr r=\"0\" g=\"0\" b=\"0\"/></a:lnRef>"
    '<a:fillRef idx="1"><a:scrgbClr r="0" g="0" b="0"/></a:fillRef>'
    '<a:effectRef idx="0"><a:scrgbClr r="0" g="0" b="0"/></a:effectRef>'
    '<a:fontRef idx="minor"><a:schemeClr val="lt1"/></a:fontRef></dgm:style></dgm:styleLbl>'
    "</dgm:styleDef>")

ole_object = b"PK\x03\x04" + b"\x00" * 60  # opaque blob stands in for the embedded package

altchunk_html = ("<html><body><p>Imported altChunk paragraph one.</p>"
                 "<p>Imported altChunk paragraph two.</p></body></html>")

# ----------------------------------------------------------------------------- embedded workbook
def make_workbook():
    """Minimal but valid .xlsx so the chart's externalData reference resolves."""
    parts = {
        "[Content_Types].xml": DECL +
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>",
        "_rels/.rels": DECL +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>",
        "xl/workbook.xml": DECL +
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": DECL +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>",
        "xl/worksheets/sheet1.xml": DECL +
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        '<row r="1"><c r="B1" t="inlineStr"><is><t>Series 1</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>Cat A</t></is></c><c r="B2"><v>4.3</v></c></row>'
        '<row r="3"><c r="A3" t="inlineStr"><is><t>Cat B</t></is></c><c r="B3"><v>2.5</v></c></row>'
        '<row r="4"><c r r="A4" t="inlineStr"><is><t>Cat C</t></is></c><c r="B4"><v>3.5</v></c></row>'
        "</sheetData></worksheet>",
    }
    bio = __import__("io").BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for n, c in parts.items():
            z.writestr(n, c)
    return bio.getvalue()


def make_embedded_docx():
    """A genuine minimal .docx to embed as an OLE object (ProgID Word.Document.12)."""
    inner_doc = (
        DECL +
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Embedded document</w:t></w:r></w:p>"
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
        "</w:sectPr></w:body></w:document>")
    inner_ct = DECL + (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>")
    inner_rels = DECL + (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>")
    bio = __import__("io").BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", inner_ct)
        z.writestr("_rels/.rels", inner_rels)
        z.writestr("word/document.xml", inner_doc)
    return bio.getvalue()


# ----------------------------------------------------------------------------- package plumbing
content_types = DECL + (
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Default Extension="png" ContentType="image/png"/>'
    '<Default Extension="bin" ContentType="application/vnd.openxmlformats-officedocument.oleObject"/>'
    '<Default Extension="docx" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document"/>'
    '<Default Extension="html" ContentType="text/html"/>'
    '<Default Extension="xlsx" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
    '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
    '<Override PartName="/word/webSettings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml"/>'
    '<Override PartName="/word/fontTable.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml"/>'
    '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>'
    '<Override PartName="/word/endnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"/>'
    '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>'
    '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
    '<Override PartName="/word/header2.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
    '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
    '<Override PartName="/word/footer2.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
    '<Override PartName="/word/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
    '<Override PartName="/word/charts/chart1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>'
    '<Override PartName="/word/charts/style1.xml" ContentType="application/vnd.ms-office.chartstyle+xml"/>'
    '<Override PartName="/word/charts/colors1.xml" ContentType="application/vnd.ms-office.chartcolorstyle+xml"/>'
    '<Override PartName="/word/diagrams/data1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml"/>'
    '<Override PartName="/word/diagrams/layout1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramLayout+xml"/>'
    '<Override PartName="/word/diagrams/quickStyle1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramStyle+xml"/>'
    '<Override PartName="/word/diagrams/colors1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.diagramColors+xml"/>'
    '<Override PartName="/word/glossary/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.glossary+xml"/>'
    '<Override PartName="/customXml/itemProps1.xml" ContentType="application/vnd.openxmlformats-officedocument.customXmlProperties+xml"/>'
    '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
    '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
    "</Types>")

root_rels = DECL + (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
    '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
    "</Relationships>")

doc_rels = DECL + (
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '<Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
    '<Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
    '<Relationship Id="rIdWebSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/webSettings" Target="webSettings.xml"/>'
    '<Relationship Id="rIdFontTable" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/fontTable" Target="fontTable.xml"/>'
    '<Relationship Id="rIdFootnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>'
    '<Relationship Id="rIdEndnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes" Target="endnotes.xml"/>'
    '<Relationship Id="rIdComments" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/>'
    '<Relationship Id="rIdHeader1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>'
    '<Relationship Id="rIdHeader2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header2.xml"/>'
    '<Relationship Id="rIdFooter1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
    '<Relationship Id="rIdFooter2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer2.xml"/>'
    '<Relationship Id="rIdTheme" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/>'
    '<Relationship Id="rIdImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>'
    '<Relationship Id="rIdChart" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="charts/chart1.xml"/>'
    '<Relationship Id="rIdDgmData" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData" Target="diagrams/data1.xml"/>'
    '<Relationship Id="rIdDgmLayout" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout" Target="diagrams/layout1.xml"/>'
    '<Relationship Id="rIdDgmQuickStyle" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramQuickStyle" Target="diagrams/quickStyle1.xml"/>'
    '<Relationship Id="rIdDgmColors" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramColors" Target="diagrams/colors1.xml"/>'
    '<Relationship Id="rIdOleObject" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject" Target="embeddings/embedded1.docx"/>'
    '<Relationship Id="rIdOleImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>'
    '<Relationship Id="rIdGlossary" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/glossaryDocument" Target="glossary/document.xml"/>'
    '<Relationship Id="rIdCustomXml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml" Target="../customXml/item1.xml"/>'
    '<Relationship Id="rIdAltChunk" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/aFChunk" Target="afchunk.html"/>'
    "</Relationships>")

web_settings_xml = DECL + (
    '<w:webSettings %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:optimizeForBrowser/><w:allowPNG/></w:webSettings>')

font_table_xml = DECL + (
    '<w:fonts %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    '<w:font w:name="Calibri"><w:panose1 w:val="020F0502020204030204"/>'
    '<w:charset w:val="00"/><w:family w:val="swiss"/><w:pitch w:val="variable"/>'
    '<w:sig w:usb0="E4002EFF" w:usb1="C000247B" w:usb2="00000009" w:usb3="00000000" '
    'w:csb0="000001FF" w:csb1="00000000"/></w:font>'
    '<w:font w:name="Times New Roman"><w:panose1 w:val="02020603050405020304"/>'
    '<w:charset w:val="00"/><w:family w:val="roman"/><w:pitch w:val="variable"/></w:font>'
    '<w:font w:name="Wingdings"><w:panose1 w:val="05000000000000000000"/>'
    '<w:charset w:val="02"/><w:family w:val="auto"/><w:pitch w:val="variable"/></w:font>'
    '<w:font w:name="Cambria Math"><w:panose1 w:val="02040503050406030204"/>'
    '<w:charset w:val="00"/><w:family w:val="roman"/><w:pitch w:val="variable"/></w:font>'
    "</w:fonts>")

theme_xml = DECL + (
    '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Fixture Theme">'
    "<a:themeElements>"
    '<a:clrScheme name="Office"><a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
    '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
    '<a:dk2><a:srgbClr val="44546A"/></a:dk2><a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>'
    '<a:accent1><a:srgbClr val="4472C4"/></a:accent1><a:accent2><a:srgbClr val="ED7D31"/></a:accent2>'
    '<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3><a:accent4><a:srgbClr val="FFC000"/></a:accent4>'
    '<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5><a:accent6><a:srgbClr val="70AD47"/></a:accent6>'
    '<a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink>'
    "</a:clrScheme>"
    '<a:fontScheme name="Office"><a:majorFont><a:latin typeface="Calibri Light"/><a:ea typeface=""/>'
    '<a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/>'
    '<a:cs typeface=""/></a:minorFont></a:fontScheme>'
    '<a:fmtScheme name="Office">'
    "<a:fillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
    "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
    "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:fillStyleLst>"
    "<a:lnStyleLst><a:ln w=\"6350\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>"
    "<a:ln w=\"12700\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln>"
    "<a:ln w=\"19050\"><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:ln></a:lnStyleLst>"
    "<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>"
    "<a:bgFillStyleLst><a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
    "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill>"
    "<a:solidFill><a:schemeClr val=\"phClr\"/></a:solidFill></a:bgFillStyleLst>"
    "</a:fmtScheme></a:themeElements></a:theme>")

glossary_xml = DECL + (
    '<w:glossaryDocument %s mc:Ignorable="%s">' % (NSDECL, IGNORABLE) +
    "<w:docParts><w:docPart>"
    '<w:docPartPr><w:name w:val="DefaultPlaceholder_1"/>'
    '<w:style w:val="Normal"/><w:category><w:name w:val="General"/><w:gallery w:val="placeholder"/>'
    "</w:category>"
    '<w:types><w:type w:val="bbPlcHdr"/></w:types>'
    '<w:behaviors><w:behavior w:val="content"/></w:behaviors>'
    '<w:guid w:val="{A1B2C3D4-1111-2222-3333-444455556666}"/></w:docPartPr>'
    "<w:docPartBody>"
    '<w:p><w:r><w:t>Click here to enter text.</w:t></w:r></w:p>'
    "</w:docPartBody></w:docPart></w:docParts></w:glossaryDocument>")

custom_item = DECL + (
    '<ns0:root xmlns:ns0="http://example.com/fixture">'
    "<ns0:field>bound value</ns0:field></ns0:root>")
custom_itemprops = DECL + (
    '<ds:datastoreItem xmlns:ds="http://schemas.openxmlformats.org/officeDocument/2006/customXml" '
    'ds:itemID="{5A1B2C3D-4E5F-6071-8293-A4B5C6D7E8F9}">'
    '<ds:schemaRefs><ds:schemaRef ds:uri="http://example.com/fixture"/></ds:schemaRefs>'
    "</ds:datastoreItem>")

core_xml = DECL + (
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
    'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
    "<dc:title>Fixture Complex Document</dc:title>"
    "<dc:subject>OOXML exception-case corpus</dc:subject>"
    "<dc:creator>Fixture Author</dc:creator>"
    "<cp:keywords>docx;fidelity;roundtrip</cp:keywords>"
    "<dc:description>Deliberately adversarial DOCX for editor round-trip testing.</dc:description>"
    '<cp:lastModifiedBy>Round Trip Editor</cp:lastModifiedBy>'
    '<cp:revision>1</cp:revision>'
    '<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-15T09:30:00Z</dcterms:created>'
    '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-01-15T09:30:00Z</dcterms:modified>'
    "<cp:category>fixture</cp:category>"
    "</cp:coreProperties>")

app_xml = DECL + (
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
    'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
    "<Application>Fixture Builder</Application><DocSecurity>0</DocSecurity>"
    "<ScaleCrop>false</ScaleCrop><Company>Fixture Co</Company><LinksUpToDate>false</LinksUpToDate>"
    "<SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged>"
    "<AppVersion>16.0000</AppVersion></Properties>")

chart_style = DECL + (
    '<cs:chartStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" id="0">'
    "<cs:axisTitle><cs:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr><a:defRPr/></a:pPr>"
    "<a:endParaRPr lang=\"en-US\"/></a:p></cs:txPr></cs:axisTitle></cs:chartStyle>")
chart_colors = DECL + (
    '<cs:colorStyle xmlns:cs="http://schemas.microsoft.com/office/drawing/2012/chartStyle" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" id="0">'
    "<cs:variation/>"
    "<cs:cat><cs:idx val=\"0\"/><cs:schemeClr val=\"accent1\"/></cs:cat>"
    "</cs:colorStyle>")

# ----------------------------------------------------------------------------- write the package
os.makedirs(os.path.dirname(OUT), exist_ok=True)
parts = [
    ("[Content_Types].xml", content_types),
    ("_rels/.rels", root_rels),
    ("docProps/core.xml", core_xml),
    ("docProps/app.xml", app_xml),
    ("word/document.xml", document_xml),
    ("word/_rels/document.xml.rels", doc_rels),
    ("word/styles.xml", styles_xml),
    ("word/numbering.xml", numbering_xml),
    ("word/settings.xml", settings_xml),
    ("word/webSettings.xml", web_settings_xml),
    ("word/fontTable.xml", font_table_xml),
    ("word/theme/theme1.xml", theme_xml),
    ("word/header1.xml", header1_xml),
    ("word/header2.xml", header2_xml),
    ("word/footer1.xml", footer1_xml),
    ("word/footer2.xml", footer2_xml),
    ("word/footnotes.xml", footnotes_xml),
    ("word/endnotes.xml", endnotes_xml),
    ("word/comments.xml", comments_xml),
    ("word/charts/chart1.xml", chart1_xml),
    ("word/charts/_rels/chart1.xml.rels", chart1_rels),
    ("word/charts/style1.xml", chart_style),
    ("word/charts/colors1.xml", chart_colors),
    ("word/diagrams/data1.xml", dgm_data),
    ("word/diagrams/layout1.xml", dgm_layout),
    ("word/diagrams/quickStyle1.xml", dgm_quickstyle),
    ("word/diagrams/colors1.xml", dgm_colors),
    ("word/glossary/document.xml", glossary_xml),
    ("customXml/item1.xml", custom_item),
    ("customXml/itemProps1.xml", custom_itemprops),
    ("customXml/_rels/item1.xml.rels", DECL +
     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
     '<Relationship Id="rId1" '
     'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXmlProps" '
     'Target="itemProps1.xml"/></Relationships>'),
    ("word/afchunk.html", altchunk_html),
]

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for name, data in parts:
        zi = zipfile.ZipInfo(name, date_time=(2026, 1, 15, 9, 30, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o600 << 16
        z.writestr(zi, data.encode("utf-8") if isinstance(data, str) else data)
    zi = zipfile.ZipInfo("word/media/image1.png", date_time=(2026, 1, 15, 9, 30, 0))
    zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, png())
    zi = zipfile.ZipInfo("word/embeddings/embedded1.docx", date_time=(2026, 1, 15, 9, 30, 0))
    zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, make_embedded_docx())
    zi = zipfile.ZipInfo("word/embeddings/Microsoft_Excel_Worksheet.xlsx",
                         date_time=(2026, 1, 15, 9, 30, 0))
    zi.compress_type = zipfile.ZIP_DEFLATED
    z.writestr(zi, make_workbook())

print("wrote", OUT, os.path.getsize(OUT), "bytes")
