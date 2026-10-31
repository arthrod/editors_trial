#!/usr/bin/env python3
"""Report A2: Docxodus additions and the stale altChunk / count corrections."""
from __future__ import annotations

from pathlib import Path

TARGET = Path("reports/Report A2 - Pass-Through (2026).md")

EDITS: list[tuple[str, str]] = []


def edit(old: str, new: str) -> None:
    EDITS.append((old, new))


# ------------------------------------------------------------------ §2.3
edit(
"**`afchunk.html` is pass-through for six editors and dropped by six.** The six that keep it are SuperDoc, Folio, GenOffice, eigenpal, office-open and Docen. The six that drop it are WordCraft, Fidus, canvas-editor, docs.plus, Plate.js and LibreOffice.",
"**`afchunk.html` is pass-through for seven participants and dropped by six.** The seven that keep it are SuperDoc, Folio, GenOffice, eigenpal, office-open, Docen and **Docxodus**. The six that drop it are WordCraft, Fidus, canvas-editor, docs.plus, Plate.js and LibreOffice.")

# ------------------------------------------------------------------ §3
edit(
"The part map has four distinct causes, and they differ in exactly what the author's bytes are entitled to.",
"The part map has **five** distinct causes, and they differ in exactly what the author's bytes are entitled to.")

edit(
"""The SDK has a **schema for the whole of WordprocessingML**, so it can parse
every part it knows; for every part it does not know it keeps the entry as it
found it; and inside a part it does know, an element or attribute from a
namespace it has no schema for is retained as *unknown* markup and re-emitted.""",
"""The SDK has a **schema for the whole of WordprocessingML**, so it can parse
every part it knows; for every part it does not know it keeps the entry as it
found it; and inside a part it does know, an element or attribute from a
namespace it has no schema for is still carried. The last of those is worth
being precise about, because the mechanism is *not* the SDK's unknown-element
machinery: **Docxodus never manipulates the SDK's typed DOM at all.** It works
on LINQ-to-XML `XDocument` trees (`Docxodus/PtOpenXmlUtil.cs:141`), and
`OpenXmlUnknownElement` appears **nowhere** in the repository. An element the
SDK has never heard of is simply a node in a tree, and nodes in a tree are
carried. The companion report *Serialization by Namespace* §3.12 works this
through in full.""")

# ------------------------------------------------------------------ §4
edit(
"That is the ideal a round-trip tool should aim at, and only four editors in this study come close.",
"That is the ideal a round-trip tool should aim at, and only five participants in this study come close — Folio, SuperDoc, Docxodus, GenOffice and eigenpal.")

# ------------------------------------------------------------------ §5.2
edit(
"**Seven editors keep both halves and six keep neither.** The `altChunk` is a construct the modelling decision either understands or does not, and the decision is applied consistently to the body element and to the payload. The part-level map records the HTML part as pass-through for six editors, and in every one of those six the element that uses it is still there.",
"**Seven participants keep both halves and six keep neither.** The `altChunk` is a construct the modelling decision either understands or does not, and the decision is applied consistently to the body element and to the payload. The part-level map records the HTML part as pass-through for seven participants, and in every one of those seven the element that uses it is still there.")

edit(
"That is worth stating as a **positive** result, because it is the outcome a naive reading of the part map would not predict: a reader seeing \"`word/afchunk.html` is byte-identical in six outputs\" would reasonably assume the chunk was **orphaned** — kept as ballast, unreferenced.",
"That is worth stating as a **positive** result, because it is the outcome a naive reading of the part map would not predict: a reader seeing \"`word/afchunk.html` is byte-identical in seven outputs\" would reasonably assume the chunk was **orphaned** — kept as ballast, unreferenced.")

# ------------------------------------------------------------------ §6.4
edit(
"**This row is the clearest example of why the `P` count alone is misleading.** eigenpal looks like the worst pass-through performer of the six \"good\" editors, and it is the second best on every other measure in the study.",
"**This row is the clearest example of why the `P` count alone is misleading.** eigenpal looks like the worst pass-through performer **by the `P` count** — 5, against Folio's 34 and Docxodus's 25 — and it is the second best on every other measure in the study.")

# ------------------------------------------------------------------ §6.7 (new)
edit(
"""### 6.7 Fidus Writer, canvas-editor, docs.plus, Plate.js — zero""",
"""### 6.7 Docxodus — 25 parts byte-identical, and nothing changed at all

**Pass-through.** 25 of 35 parts are byte-identical and the other ten are re-serialised to the same tree. **Nothing is changed, nothing is dropped, nothing is added** — the only row in the table with a zero in every one of those three columns.

**The ten it re-serialises** are `word/document.xml`, `word/comments.xml`, `word/footnotes.xml`, `word/endnotes.xml`, both headers, both footers, `word/settings.xml` and `word/styles.xml` — the parts the SDK owns. The twenty-five it copies are everything else, including the **entire binary payload**: the chart *and its two style companions*, all four SmartArt parts, both embeddings, the image and the `altChunk` HTML.

**This is the strongest row in the table, and it is strongest in the column that matters.** Folio copies more bytes — 34 against 25 — but Folio *changes* `word/document.xml`. Docxodus changes nothing at all: it has the highest pass-through count of any participant that also has a zero in the "changed" column. It gets there without a policy, because the SDK owns the parts it models and passes the rest through entry-for-entry.

**What it does not do.** It orphans nothing, it dangles nothing (§5.4), and its content-types declarations are coherent (§5.5). Its relationship ids are the corpus's own and every one resolves.

**And the interesting caveat is that it is not an editor.** A user cannot restyle a chart through Docxodus's package writer, because the chart is a copied ZIP entry and a copied ZIP entry cannot be edited. The pass-through is *exact*, and it is exact because nobody looked at those bytes — which is §1.1's definition, arrived at by a completely different route.

### 6.8 Fidus Writer, canvas-editor, docs.plus, Plate.js — zero""")

# ------------------------------------------------------------------ §7
edit(
"- **\"The part is still there\" is not \"the part is still used.\"** Six editors keep `word/afchunk.html` byte-for-byte and none of them keeps the `w:altChunk` element that referenced it. The package grew and the document did not.",
"""- **\"The part is still there\" is not \"the part is still used\" — but on this corpus it did not happen.** The obvious orphan is the `altChunk`: a payload part in the package and an element in the body that points at it, in two separate places. **Seven participants keep both halves and six keep neither; not one keeps one.** The failure mode is real in general and it did happen with the chart (§5.4) — but it did not happen with the `altChunk`, and a reader who assumed the part map implied the orphan would have been wrong.""")

edit(
"- **Choose on the axis you care about.** If you need the document to survive a round trip with its payloads intact, Folio and SuperDoc.",
"- **The best row and the best score are not the same row.** Docxodus has the only all-zero row in the part map — 0 changed, 0 dropped, 0 added — and the *entire* binary payload byte-identical. Folio copies more bytes still (34 against 25), but it rewrites the body. If your requirement is \"save it back and change nothing\", Docxodus is the only participant in this study that satisfies it outright.\n- **Choose on the axis you care about.** If you need the document to survive a round trip with its payloads intact, Folio and SuperDoc.")

# ------------------------------------------------------------------ Gaps
edit(
"6. **This report measures packages, not pages.** Whether a surviving part is *drawn* is a separate question, answered in *Rendering Versus Word*.",
"""6. **This report measures packages, not pages.** Whether a surviving part is *drawn* is a separate question, answered in *Rendering Versus Word*. For Docxodus the two answers are unusually far apart: its package keeps every namespace, and its renderer substitutes a `[SMARTART]` placeholder and a `[MATH]` chip for two of them.
7. **Docxodus's row is measured through the `DocxSession` API, not through its export CLI.** The round trip is `docxodus/core` → `openDocxSession` → `save()` (`harness/ui/docxodus/roundtrip.mjs`). The `@docxodus/export` CLI produces HTML and PDF and does not write DOCX, so it has no package to measure. The two paths share the same package writer, but the measurement exercises the session API — which is the product's own supported round-trip surface.
8. **Docxodus's pass-through is exact because the SDK never opens those parts.** "Byte-identical" here means *never touched*, and that is a statement about the SDK's part ownership, not about a decision to preserve. The consequence for an evaluator is the same one §4.1 draws for Folio: the parts Docxodus copies are the parts no user can change.""")


def main() -> int:
    text = TARGET.read_text()
    for i, (old, new) in enumerate(EDITS, 1):
        n = text.count(old)
        if n != 1:
            print(f"EDIT {i} matched {n} times (expected 1):\n---\n{old[:220]}\n---")
            return 1
        text = text.replace(old, new)
    TARGET.write_text(text)
    print(f"applied {len(EDITS)} edits to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
