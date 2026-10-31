#!/usr/bin/env python3
"""
Re-fit the tables of a generated .docx to the page.

pandoc sizes every table to 7920 twips - the width of a PORTRAIT Letter page
with 1.5in margins - whatever the section says. The reference document here is
LANDSCAPE Letter with 0.5in margins, so the content area is 14400 twips and
every pandoc table covers 55% of the page, with the first column squeezed
until the part names wrap into three lines.

This pass lays each table out from its own content:

  * every column gets at least the width of its longest unbreakable token
    (so no word is split mid-word),
  * the slack is shared out equally,
  * the table is given the full content width and a fixed layout, so Word
    honours the widths instead of re-flowing them.

usage: python3 build/retune_tables.py <file.docx> [...]
"""
import os
import re
import shutil
import sys
import zipfile

# twips
CELL_MARGIN = 115          # 115 twips of padding on each side of a cell
PROP_CHARS_PER_PT = 0.50   # average advance width of a proportional face
MONO_CHARS_PER_PT = 0.55   # average advance width of Consolas


def page_width(xml):
    """The content width of the section, in twips."""
    m = re.search(r'<w:pgSz[^>]*w:w="(\d+)"', xml)
    pw = int(m.group(1)) if m else 12240
    m = re.search(r'<w:pgMar[^>]*w:left="(\d+)"[^>]*w:right="(\d+)"', xml)
    if m:
        left, right = int(m.group(1)), int(m.group(2))
    else:
        m2 = re.search(r'<w:pgMar[^>]*w:right="(\d+)"[^>]*w:left="(\d+)"', xml)
        left, right = (int(m2.group(2)), int(m2.group(1))) if m2 else (1440, 1440)
    return pw - left - right


def cell_text(tc):
    """(text, uses monospace) for one <w:tc> block."""
    parts = re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', tc, re.S)
    text = "".join(parts)
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"'))
    mono = 'w:val="VerbatimChar"' in tc or "Consolas" in tc
    return text, mono


def token_widths(text, mono):
    """Width of the longest unbreakable token in the cell."""
    if not text:
        return 0
    # 8pt for table text, 11pt for inline code
    per_pt = MONO_CHARS_PER_PT if mono else PROP_CHARS_PER_PT
    size = 11 if mono else 8
    unit = per_pt * size * 20          # twips per character
    longest = 0
    for tok in re.split(r"[\s/]+", text):
        longest = max(longest, len(tok))
    return longest * unit


def fit_table(tbl, total):
    """Return (grid_widths, per_row_widths) for one <w:tbl> block."""
    rows = re.findall(r"<w:tr\b.*?</w:tr>", tbl, re.S)
    if not rows:
        return None, None
    grid = re.search(r"<w:tblGrid>(.*?)</w:tblGrid>", tbl, re.S)
    ncols = len(re.findall(r"<w:gridCol\b", grid.group(1))) if grid else 0
    if not ncols:
        return None, None

    mins = [0] * ncols
    rowcells = []
    for r in rows:
        cells = re.findall(r"<w:tc>.*?</w:tc>", r, re.S)
        rowcells.append(cells)
        if len(cells) != ncols:
            return None, None
        for i, tc in enumerate(cells):
            text, mono = cell_text(tc)
            mins[i] = max(mins[i], token_widths(text, mono) + 2 * CELL_MARGIN)

    mins = [m or 2 * CELL_MARGIN for m in mins]
    s = sum(mins)
    if s >= total:
        widths = [max(int(m * total / s), 400) for m in mins]
        drift = total - sum(widths)
        widths[-1] += drift
    else:
        slack = total - s
        extra = slack // ncols
        widths = [m + extra for m in mins]
        widths[-1] += total - sum(widths)
    return widths, rowcells


def retune(path):
    src = zipfile.ZipFile(path)
    items = {n: src.read(n) for n in src.namelist()}
    src.close()
    xml = items["word/document.xml"].decode("utf-8")
    total = page_width(xml)

    count = 0

    def repl(m):
        nonlocal count
        tbl = m.group(0)
        widths, rowcells = fit_table(tbl, total)
        if not widths:
            return tbl
        count += 1
        # table width + fixed layout
        tbl = re.sub(r'<w:tblW[^>]*/>', '<w:tblW w:w="%d" w:type="dxa" />' % total, tbl, count=1)
        if "<w:tblLayout" not in tbl:
            tbl = re.sub(r"(<w:tblLook\b)", r'<w:tblLayout w:type="fixed" />\1', tbl, count=1)
        # grid
        cols = "".join('<w:gridCol w:w="%d" />' % w for w in widths)
        tbl = re.sub(r"<w:tblGrid>.*?</w:tblGrid>",
                     "<w:tblGrid>%s</w:tblGrid>" % cols, tbl, count=1, flags=re.S)
        # cell widths, row by row
        out, pos = [], 0
        for r in re.finditer(r"<w:tr\b.*?</w:tr>", tbl, re.S):
            row = r.group(0)
            cells = re.findall(r"<w:tc>.*?</w:tc>", row, re.S)
            if len(cells) != len(widths):
                out.append(row)
                continue
            new = row
            for i, tc in enumerate(cells):
                w = widths[i]
                if "<w:tcPr />" in tc:
                    new_tc = tc.replace(
                        "<w:tcPr />",
                        '<w:tcPr><w:tcW w:w="%d" w:type="dxa" /></w:tcPr>' % w, 1)
                else:
                    new_tc = re.sub(
                        r"<w:tcPr>(.*?)</w:tcPr>",
                        lambda mm: '<w:tcPr>%s<w:tcW w:w="%d" w:type="dxa" /></w:tcPr>'
                        % (mm.group(1), w),
                        tc, count=1, flags=re.S)
                new = new.replace(tc, new_tc, 1)
            out.append((row, new))
        # rebuild preserving order
        res, last = [], 0
        for old, new in out:
            i = tbl.find(old, last)
            if i < 0:
                continue
            res.append(tbl[last:i])
            res.append(new)
            last = i + len(old)
        res.append(tbl[last:])
        return "".join(res)

    xml = re.sub(r"<w:tbl>.*?</w:tbl>", repl, xml, flags=re.S)
    items["word/document.xml"] = xml.encode("utf-8")

    tmp = path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in items.items():
            z.writestr(n, d)
    shutil.move(tmp, path)
    print("%-70s %d tables, content width %d" % (os.path.basename(path), count, total))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        retune(p)
