#!/usr/bin/env python3
"""
Bake the table of contents into the .docx.

pandoc's --toc writes a Word TOC *field* with an empty cached result, and the
only way Word would fill it in is a field update - which it performs on open
only when the field carries w:dirty="true".  Word 16.115 refuses a document
whose w:fldChar carries w:dirty="true" (see build/scan_word_hostile.py), so
the flag has to be false and the table of contents therefore stays EMPTY.

The fix is to write the field the way Word itself writes it: the entries live
between w:fldChar "separate" and w:fldChar "end" as the field's cached result.
The table of contents is then visible the moment the document opens, the
hyperlinks work, and pressing F9 still regenerates it with page numbers.

usage: python3 build/bake_toc.py <file.docx> [...]
"""
import os
import re
import shutil
import sys
import zipfile

TOC_STYLES = """
<w:style w:type="paragraph" w:styleId="TOC1"><w:name w:val="toc 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:pPr><w:spacing w:before="60" w:after="0"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="TOC2"><w:name w:val="toc 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:pPr><w:spacing w:after="0"/><w:ind w:left="284"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="TOC3"><w:name w:val="toc 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:pPr><w:spacing w:after="0"/><w:ind w:left="567"/></w:pPr></w:style>
""".strip()


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def headings(xml, levels=(1, 2, 3)):
    """(level, text, bookmark) for every heading, in document order."""
    out = []
    for m in re.finditer(r"<w:p\b(?:[^>]*)>.*?</w:p>", xml, re.S):
        p = m.group(0)
        st = re.search(r'<w:pStyle w:val="Heading(\d)"\s*/>', p)
        if not st:
            continue
        lvl = int(st.group(1))
        if lvl not in levels:
            continue
        bm = re.search(r'<w:bookmarkStart[^>]*w:name="([^"]+)"', p)
        if not bm:
            continue
        text = "".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", p, re.S))
        text = (text.replace("&amp;", "&").replace("&lt;", "<")
                    .replace("&gt;", ">").replace("&quot;", '"')
                    .replace("&apos;", "'").replace("&#39;", "'"))
        out.append((lvl, text.strip(), bm.group(1)))
    return out


def build_toc(entries):
    """The TOC field, with the entries as its cached result."""
    paras = []
    for i, (lvl, text, bm) in enumerate(entries):
        head = ""
        if i == 0:
            head = ('<w:r><w:fldChar w:fldCharType="begin" w:dirty="false" /></w:r>'
                    '<w:r><w:instrText xml:space="preserve">TOC \\o "1-3" \\h \\z \\u'
                    '</w:instrText></w:r>'
                    '<w:r><w:fldChar w:fldCharType="separate" /></w:r>')
        paras.append(
            '<w:p><w:pPr><w:pStyle w:val="TOC%d" /></w:pPr>%s'
            '<w:hyperlink w:anchor="%s"><w:r><w:t xml:space="preserve">%s</w:t>'
            '</w:r></w:hyperlink></w:p>'
            % (lvl, head, bm, esc(text)))
    paras.append('<w:p><w:pPr><w:pStyle w:val="TOC1" /></w:pPr>'
                 '<w:r><w:fldChar w:fldCharType="end" /></w:r></w:p>')
    return "".join(paras)


def bake(path):
    z = zipfile.ZipFile(path)
    items = {n: z.read(n) for n in z.namelist()}
    z.close()
    xml = items["word/document.xml"].decode("utf-8")

    entries = headings(xml)
    if not entries:
        print("%-64s no headings, skipped" % os.path.basename(path))
        return

    # the empty TOC field pandoc wrote
    m = re.search(
        r'<w:p>\s*<w:r>\s*<w:fldChar w:fldCharType="begin"[^>]*/>\s*'
        r'<w:instrText[^>]*>.*?</w:instrText>\s*'
        r'<w:fldChar w:fldCharType="separate"\s*/>\s*'
        r'<w:fldChar w:fldCharType="end"\s*/>\s*</w:r>\s*</w:p>',
        xml, re.S)
    if not m:
        print("%-64s no TOC field found, skipped" % os.path.basename(path))
        return

    xml = xml[:m.start()] + build_toc(entries) + xml[m.end():]
    items["word/document.xml"] = xml.encode("utf-8")

    # the TOC paragraph styles have to exist
    styles = items["word/styles.xml"].decode("utf-8")
    add = ""
    for sid in ("TOC1", "TOC2", "TOC3"):
        if 'w:styleId="%s"' % sid not in styles:
            add += re.search(r'<w:style [^>]*w:styleId="%s".*?</w:style>' % sid,
                             TOC_STYLES, re.S).group(0)
    if add:
        styles = styles.replace("</w:styles>", add + "</w:styles>")
        items["word/styles.xml"] = styles.encode("utf-8")

    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for n, d in items.items():
            out.writestr(n, d)
    shutil.move(tmp, path)
    print("%-64s %d TOC entries baked" % (os.path.basename(path), len(entries)))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        bake(p)
