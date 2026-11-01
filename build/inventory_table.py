#!/usr/bin/env python3
"""
Emit the "in the DOCX but not rendered" table for the rendering report.

Two separate questions, kept separate:

  PACKAGE  is the construct still in the editor's exported DOCX?
  WORD     does Word draw it when it opens that package?

The WORD column for the corpus is NOT read from the automated probe.  The
probe is a TEXT probe, and two constructs in this corpus are drawn by Word as
vector outlines - the OMML equation and the w14:textOutline run - so the
probe reports them as absent when Word in fact draws them (proven by A/B
pixel diffs: out/ab/ab_compare.json, Report C section 6.3).  The corpus column
therefore uses verified values, and the editor columns are read from the
package, which is a reliable measurement.

usage: python3 build/inventory_table.py > out/render/inventory_table.md
       (facts.py publishes table() as {{inventory.table}} for Report C section 4.1)
"""
import json
import os

BASE = "/Users/arthrod/temp/T/editors_trial"

EDITORS = ["superdoc", "folio", "genoffice", "eigenpal", "office-open",
           "docen", "wordcraft", "fidus", "canvas", "docs.plus", "plate",
           "docxodus", "apryse", "libreoffice"]

# key -> (label, Word's verified behaviour on the corpus)
SHOW = [
    ("Chart (series names)", "the chart", "drawn"),
    ("SmartArt (step 1)", "the SmartArt", "**not drawn** (0 px, §5)"),
    ("Text box (mc:Choice)", "the `mc:Choice` text box", "drawn"),
    ("mc:Fallback text", "the `mc:Fallback` text", "not drawn (Choice wins)"),
    ("OMML math", "the equation", "drawn (vector outline)"),
    ("Comment", "the comment", "drawn"),
    ("Endnote", "the endnote body", "drawn"),
    ("Footnote", "the footnote body", "drawn"),
    ("Tracked deletion (w:delText)", "the deleted runs", "drawn"),
    ("Deleted table row (w:trPr/w:del)", "the deleted table row", "drawn"),
    ("Tracked insertion (w:ins)", "the inserted runs", "drawn"),
    ("Move source (w:moveFrom)", "the move-source runs", "drawn"),
    ("Hidden text (w:vanish)", "the hidden run", "not drawn (vanish)"),
    ("altChunk part", "the altChunk", "drawn (imported)"),
    ("Landscape section", "the landscape section", "drawn"),
    ("Table vertical merge", "the vertical merge", "drawn"),
    ("Nested table", "the nested table", "drawn"),
    ("RTL / Hebrew run", "the RTL run", "drawn"),
]


def table(path=os.path.join(BASE, "out/render/render_inventory.json")):
    with open(path) as fh:
        inv = json.load(fh)

    out = []
    out.append("| Construct | In the corpus | Word draws it | " +
               " | ".join(EDITORS) + " |")
    out.append("|---|---|---|" + "---|" * len(EDITORS))

    for key, label, word in SHOW:
        row = [label, "yes", word]
        for ed in EDITORS:
            e = inv.get(ed)
            if not e:
                row.append("—")
                continue
            pkg = e.get("pkg", {}).get(key, False)
            row.append("yes" if pkg else "**dropped**")
        out.append("| " + " | ".join(row) + " |")

    return "\n".join(out)


def main():
    print(table())


if __name__ == "__main__":
    main()
