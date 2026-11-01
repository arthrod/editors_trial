#!/usr/bin/env python3
"""
Emit the part x editor matrix as two readable tables.

Thirteen columns do not fit a landscape page - the renderer wraps the header
words onto four lines each. Splitting the editors in half keeps every cell to
one glyph.

usage: python3 build/part_matrix_md.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import part_map  # noqa: E402

BASE = "/Users/arthrod/temp/T/editors_trial"
IN = os.path.join(BASE, "fixture", "complex.docx")
GLYPH = {"PASSTHROUGH": "P", "REWRITTEN": "w", "CHANGED": "C",
         "DROPPED": "D", "ADDED": "A"}

# the payload parts get their own table: they are the ones readers care about
PAYLOAD = [
    "word/charts/chart1.xml", "word/charts/style1.xml", "word/charts/colors1.xml",
    "word/diagrams/data1.xml", "word/diagrams/layout1.xml",
    "word/diagrams/quickStyle1.xml", "word/diagrams/colors1.xml",
    "word/embeddings/embedded1.docx",
    "word/embeddings/Microsoft_Excel_Worksheet.xlsx",
    "word/media/image1.png", "word/afchunk.html",
]


def collect():
    inp = part_map.read(IN)
    maps = {}
    for name, d in part_map.EDITORS:
        p = os.path.join(BASE, "out", d, "complex.docx")
        if not os.path.exists(p):
            continue
        maps[name] = part_map.classify(inp, part_map.read(p))
    return inp, maps


def short(name):
    """Compact the part name so the column does not wrap."""
    n = name
    if n.startswith("word/"):
        n = n[5:]
    for a, b in (("Microsoft_Excel_Worksheet.xlsx", "Excel_Worksheet.xlsx"),
                 ("customXml/_rels/item1.xml.rels", "customXml/item1.rels"),
                 ("embeddings/", "embed/"),
                 ("diagrams/", "dgm/"),
                 ("charts/", "chart/"),
                 ("media/", "media/")):
        n = n.replace(a, b)
    return n


# the column header is a display name; the maps stay keyed by the original
# editor name so a lookup can never desynchronise from the header row
DISPLAY = {
    "Fidus Writer": "Fidus",
    "canvas-editor + plugin": "canvas + plugin",
    "LibreOffice (baseline)": "LibreOffice",
}


def display(name):
    return DISPLAY.get(name, name)


def table(inp, maps, order, parts, title):
    out = ["**%s**\n" % title,
           "| Package part | " + " | ".join(display(n) for n in order) + " |",
           "|---|" + "---|" * len(order)]
    for p in parts:
        row = [GLYPH.get(maps[n].get(p), "·") for n in order]
        out.append("| `%s` | %s |" % (short(p), " | ".join(row)))
    return "\n".join(out)


def markdown():
    """The four tables Report A2 prints (build/facts.py: parts.matrix)."""
    inp, maps = collect()
    order = [n for n, _ in part_map.EDITORS if n in maps]
    half = (len(order) + 1) // 2
    a, b = order[:half], order[half:]
    common = sorted(set(inp) - set(PAYLOAD))
    return "\n\n".join([
        table(inp, maps, a, common, "WordprocessingML and package parts"),
        table(inp, maps, b, common, "WordprocessingML and package parts (continued)"),
        table(inp, maps, a, PAYLOAD, "Binary payload and opaque parts"),
        table(inp, maps, b, PAYLOAD, "Binary payload and opaque parts (continued)"),
    ])


if __name__ == "__main__":
    print(markdown())
