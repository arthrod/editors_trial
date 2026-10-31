#!/usr/bin/env python3
"""Second Report A patch: the §6 legend, the ?-suffix note, and the new §4.5."""
from __future__ import annotations

from pathlib import Path

TARGET = Path("reports/Report A - Serialization by Namespace (2026).md")

EDITS: list[tuple[str, str]] = []


def edit(old: str, new: str) -> None:
    EDITS.append((old, new))


edit(
"The two disagree in four places (§4.4), and in every one of them the **code reading understates the loss**. That is a result, not a problem with the method: a boundary that is defined for the *modeled* namespaces says nothing about what happens to markup that was destroyed upstream of the boundary.",
"The two disagree in four places among the twelve editors (§4.4), and in every one of them the **code reading understates the loss**. §4.5 shows the opposite happening too — and with it the reason the disagreement matters: a boundary that is defined for the *modeled* namespaces says nothing about what happens to markup that was destroyed upstream of the boundary, and just as little about markup that survived by a route the reading never saw.")

edit(
"Four disagreements, and **all four run the same way: the code understates the loss.**",
"Four disagreements among the twelve editors, and **all four run the same way: the code understates the loss.** §4.5 shows the opposite happens as well.")

edit(
"**Microsoft's own file format, round-tripped through the closest open implementation to Word, loses the 2023 UTC-date attribute.** That is a fair measure of how young that namespace is.\n\n---\n\n## 5. The consequences, namespace by namespace",
"""**Microsoft's own file format, round-tripped through the closest open implementation to Word, loses the 2023 UTC-date attribute.** That is a fair measure of how young that namespace is.

### 4.5 The code reading is wrong in both directions

The four disagreements above all run one way: the source reading predicts a **larger** loss than the file shows. The opposite also happens, and the matrix in §6 — rebuilt in this edition from the measurement rather than from the source reading — makes it visible for the first time.

**Twenty-seven cells** in the earlier matrix said *dropped* where the measurement finds the namespace kept, and **seventeen** said *kept or flattened* where the measurement finds it gone. The sharpest of the first group is **Plate.js and the OMML**: Mammoth's importer reports *"An unrecognised element was ignored: m:oMath"*, Plate.js surfaces that as a `converter-message` diagnostic, and the earlier edition of this report therefore listed Plate.js among the editors that drop `m` outright — but the measurement finds **all four `m:` names** in Plate's output package. The pattern repeats across ten namespaces:

| Namespace | Editors whose earlier reading said "dropped" | What the measurement finds |
|---|---|---|
| `pic` | Fidus, canvas-editor, docs.plus | all six `pic:` names — and the image bytes too, though the media file is renamed (`image-659975.png`, `zsakc18onfp21xzadj5t0.png`, `image-ZwEGiAbAoIUtGFAOXxOfH.png`) |
| `wp` | Fidus, canvas-editor, docs.plus | 3/5, 5/5 and 4/5 respectively |
| `w15` | Fidus, canvas-editor, office-open, Docen | all four keep `w15:restartNumberingAfterBreak` — in `word/numbering.xml`, not in the document body, which is why a body-only reading misses it |
| `w16cid` | WordCraft | the attribute is present, in `word/commentsIds.xml` |
| `w14` | WordCraft, office-open, Docen | all twelve names for WordCraft; 10/12 for office-open and Docen |
| `ns0` | office-open, Docen, WordCraft | both foreign names |
| `rels` | Fidus, canvas-editor, docs.plus | both names |
| `a` | Fidus, docs.plus | 11/60 and 42/60 — partial, but not nothing |
| `w:ins` and the other revision wrappers | office-open, Docen | all three revision markers survive |
| `dgm`, `c`, `v`, `o` | SuperDoc | every name present in the package — SuperDoc's diagnostic belongs to the *renderer*, not to the writer |

**And seventeen cells run the other way**: the earlier reading said *kept* where the measurement finds the namespace gone. Nine of them are Plate.js — `pic`, `wp`, `v`, `o`, `r`, `w15`, `w16cid`, `w14` and the revision wrappers — which is why Plate is the only editor in the study that loses the image outright. WordCraft loses `w10`. Fidus loses `m` (contrary to the earlier reading that it converts OMML to MathML) and `w:sdt`; canvas-editor loses `v` (contrary to the earlier reading of a partial VML model) and `w:sdt`.

**The mechanism behind both directions is the same one.** A construct that reaches the model as an *opaque payload* and is re-emitted verbatim is invisible to a source-level reading of the typed model — in either direction: the reading cannot see that it survived, and it cannot see that it did not. So the honest conclusion is not "the code reading understates the loss" but the sharper, two-sided one: **a code reading is a map of the code, and a construct's survival in a package can be established only by measurement.**

That is why §6's letters are now derived from the measurement and the parentheticals carry the mechanism. It also retires a small piece of the report's furniture: Plate.js's passive `w14` namespace and SuperDoc's closed engine are no longer represented in §6 as survivals the source reading predicts, but as **mechanisms that could not be verified** — marked with a `?` suffix — while the survival itself is stated by §4.2 and checked automatically before the table is written.

---

## 5. The consequences, namespace by namespace""")

edit(
"**Legend.** `K` kept verbatim · `R` rewritten or re-modelled · `S` summarised or flattened · `D` dropped · `G` diagnosed (a named warning or diagnostic is emitted) · `?` no verifiable code path in this checkout · `—` not applicable.",
"""**Legend.** `K` every distinct name kept and carried unchanged · `R` every distinct name kept but re-serialised or re-modelled — a partial loss is shown as `R (n/N)` · `S` flattened or summarised · `D` dropped, no distinct name survives · `G` a named warning or diagnostic is emitted · `?` a *suffix* marking a cell whose **survival is measured but whose mechanism is not verifiable from source** · `—` not applicable.

**The letters are derived from the measurement**, not from the source reading. Every cell below is checked against `out/ns_map.json` — the §4.2 measurement — by `build/report_a_matrix.py` before the table is written, so this table cannot contradict §4.2. The parenthetical in each cell is the **mechanism**, established from source in §3.

**The Docxodus column is derived, not guessed.** It follows from the part classification in §3.12: the ten parts the projector re-writes and the twenty-five it copies byte-for-byte. `K (part)` means the namespace's payload lives in a copied part; `R (parts K)` means the namespace spans both a rewritten part and a copied one; `R (media K)` means the media is copied but the reference to it is re-serialised.""")

edit(
"**How to read the `?` cells.** A `?` is an absence of public evidence, **not** evidence of absence. Every SuperDoc `?` is a namespace whose behaviour lives inside the closed `@superdoc/docx-engine` bundle. §4.2 replaces most of them with measurements, and the measurements are kinder to SuperDoc than the `?`s suggest.",
"""**How to read the `?` suffix.** A `?` is an absence of public evidence about the **mechanism**, not about the survival: the namespace's names were measured, and what happened to them is known, but *how* it happened is not readable in this checkout. Nearly all of them are SuperDoc, whose engine is the closed `@superdoc/docx-engine` distribution, and office-open's and Docen's `cs`, `ds` and `w:altChunk` cells, where the source reading found no code path at all. **No cell in this matrix is unknown** — only some of their mechanisms are. The `w16cex` row is the one exception: the corpus declares that namespace and never uses it (§2.1), so there is no measurement to derive a letter from and the row carries the code reading alone.""")


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
