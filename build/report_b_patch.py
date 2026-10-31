#!/usr/bin/env python3
"""Report B: add Docxodus (the thirteenth participant) to the defect tables."""
from __future__ import annotations

from pathlib import Path

TARGET = Path("reports/Report B - Malformed Parts, Causes and Repair (2026).md")

EDITS: list[tuple[str, str]] = []


def edit(old: str, new: str) -> None:
    EDITS.append((old, new))


# ------------------------------------------------------------------ TL;DR
edit(
"- **Not one editor repairs anything.** Handed a corpus carrying all twelve defect classes, **every** editor either reproduced the damage or dropped the part that carried it. None diagnosed it, none fixed it — and, until **Plate.js** was added, not one said anything about it.",
"""- **Not one editor repairs anything.** Handed a corpus carrying all twelve defect classes, **every** editor either reproduced the damage or dropped the part that carried it. None diagnosed it, none fixed it — and, until **Plate.js** was added, not one said anything about it. **Docxodus, the thirteenth participant, does not change the finding: it preserves all ten package-visible defect classes, and Microsoft Word refuses its output.**
- **Docxodus is the only participant that ships a repair funnel, and it repairs a different set of defects.** Its `PackageOpenRepair` stage exists to unblock *"Package defects Word opens but the Open XML SDK rejects"* — a relationship to a part with **no content type** or **no ZIP entry**, a part reached by a known relationship but **typed only as generic XML**, and **two relationships sharing an Id**. **None of those is one of this report's twelve defect classes.** Having a repair stage and repairing a given malformation are different properties, and this is the cleanest available demonstration of the difference.""")

edit(
"- **Four of the twelve editor outputs cannot be opened by Microsoft Word**, and only two of those four fail for a reason a schema validator could have caught:",
"- **Four of the thirteen editor outputs cannot be opened by Microsoft Word**, and only two of those four fail for a reason a schema validator could have caught:")

edit(
"| WordCraft | 0 | clean | **opened** |\n| canvas-editor + plugin | 1 | clean | **opened** |",
"| WordCraft | 0 | clean | **opened** |\n| **Docxodus** | **0** | **clean** | **opened** |\n| canvas-editor + plugin | 1 | clean | **opened** |")

edit(
"- **Plate.js is the twelfth editor, and it breaks the pattern in the most useful way.** It cannot open the broken corpus either — but it fails **before writing anything**, so it is the only editor in the study that refuses a malformed file without leaving a damaged one behind. Its clean-corpus output, by contrast, is schema-clean, package-clean and **opens in Word**.",
"- **Plate.js is the twelfth editor, and it breaks the pattern in the most useful way.** It cannot open the broken corpus either — but it fails **before writing anything**, so it is the only editor in the study that refuses a malformed file without leaving a damaged one behind. Its clean-corpus output, by contrast, is schema-clean, package-clean and **opens in Word**. **Docxodus is the thirteenth, and it does not break the pattern: it is faithful, it preserves the damage, and Word refuses its broken-corpus output — exactly as the defect table predicts.**")

# ------------------------------------------------------------------ §4
edit(
"`fixture/complex_broken.docx` was pushed through all twelve editors. Each output was then scanned for the ten defect classes that are visible in a package (the OLE and nesting classes are covered by the earlier table), and separately opened in Word.",
"`fixture/complex_broken.docx` was pushed through all thirteen participants. Each output was then scanned for the ten defect classes that are visible in a package (the OLE and nesting classes are covered by the earlier table), and separately opened in Word.")

edit(
"| GenOffice | YES | YES | YES | YES | YES | YES | YES | YES | YES | YES | **REFUSED** |\n| eigenpal | YES | YES | YES | YES | YES | YES | YES | YES | YES | YES | **REFUSED** |",
"| GenOffice | YES | YES | YES | YES | YES | YES | YES | YES | YES | YES | **REFUSED** |\n| eigenpal | YES | YES | YES | YES | YES | YES | YES | YES | YES | YES | **REFUSED** |\n| **Docxodus** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **REFUSED** |")

edit(
"- **LibreOffice** is the only one that repaired the `w:trPr` ordering on its own (`w:cantSplit`/`w:tblHeader`) while dropping everything else — because its writer emits rows in schema order.",
"""- **LibreOffice** is the only one that repaired the `w:trPr` ordering on its own (`w:cantSplit`/`w:tblHeader`) while dropping everything else — because its writer emits rows in schema order.
- **Docxodus preserves all ten, and the mechanism is worth naming.** It is a pass-through writer for the twenty-five parts the Open XML SDK does not model and a re-serialiser for the ten it does — and `word/document.xml` and `word/settings.xml` are both in the second group. **Re-serialisation is faithful to the *tree*, not to the *schema*: the SDK prints the elements it read in the order it read them**, so an out-of-order `w:tcPr` comes back out of order. Its broken-corpus output therefore carries **ten real XSD violations** (7 × `w:tcW`, 1 × `w:spacing`, 1 × `w:pgNumType`, 1 × `w:documentProtection`) and is **package-clean** — the same shape of failure as the other four faithful editors, reached by a completely different route.""")

# ------------------------------------------------------------------ §4.1
edit(
"| GenOffice | YES | YES | YES | REFUSED | all three fatal classes survive |\n| eigenpal | YES | YES | YES | REFUSED | all three fatal classes survive |",
"| GenOffice | YES | YES | YES | REFUSED | all three fatal classes survive |\n| eigenpal | YES | YES | YES | REFUSED | all three fatal classes survive |\n| **Docxodus** | **YES** | **YES** | **YES** | **REFUSED** | **all three fatal classes survive** |")

edit(
"Two of these rows are individually decisive:",
"Three of these rows are individually decisive:")

# ------------------------------------------------------------------ §4.2
edit(
"| WordCraft | OPENED | REFUSED | **yes** |\n| Folio | REFUSED | REFUSED | no — already broken |",
"| WordCraft | OPENED | REFUSED | **yes** |\n| **Docxodus** | **OPENED** | **REFUSED** | **yes** |\n| Folio | REFUSED | REFUSED | no — already broken |")

edit(
"**Four editors that were faithful to the clean file die on the malformed one, and the three that survive are the three that throw the content away.** Fidelity and robustness are anti-correlated here, and the reason is structural rather than accidental: an editor that preserves the document preserves the damage inside it, because the damage *is* the document as far as a pass-through writer is concerned. The editors that survive the malformed input are the ones that were already losing most of the document — they lose nothing more.",
"**Five editors that were faithful to the clean file die on the malformed one, and the three that survive are the three that throw the content away.** Fidelity and robustness are anti-correlated here, and the reason is structural rather than accidental: an editor that preserves the document preserves the damage inside it, because the damage *is* the document as far as a pass-through writer is concerned. The editors that survive the malformed input are the ones that were already losing most of the document — they lose nothing more.")

# ------------------------------------------------------------------ §4.3
edit(
"The comparison with the other eleven editors is the point. They either **corrupt** the malformed input (preserve the damage) or **discard** it (drop the part), and both outcomes are silent. Plate **declines**. Of the three possible behaviours on malformed input — repair, degrade, refuse — **only one of the twelve editors implements the third**, and it is the one with the most stars.",
"The comparison with the other twelve participants is the point. They either **corrupt** the malformed input (preserve the damage) or **discard** it (drop the part), and both outcomes are silent. Plate **declines**. Of the three possible behaviours on malformed input — repair, degrade, refuse — **only one of the thirteen implements the third**, and it is the one with the most stars.")

# ------------------------------------------------------------------ §4.4
edit(
"Not one editor does any of the three. The pass-through editors cannot, by construction: repairing a part requires modelling it, and modelling it is what pass-through refuses to do.",
"""Not one editor does any of the three. The pass-through editors cannot, by construction: repairing a part requires modelling it, and modelling it is what pass-through refuses to do.

**Docxodus is the one participant that has a repair stage, and it repairs a different set of defects.** Its `PackageOpenRepair` funnel exists because *"Package defects Word opens but the Open XML SDK rejects"* would otherwise make the SDK refuse the file at `WordprocessingDocument.Open` (`Docxodus/DocxSession.cs:166`). It fixes four things: a relationship to a part with **no content type** or **no ZIP entry**, a part reached by a known relationship but **typed only as generic XML**, and **two relationships sharing an Id**. **None of those is one of this report's twelve defect classes** — which is exactly why the measurement above shows Docxodus repairing nothing.

That is the point worth keeping, and it generalises: **a repair stage is scoped to the consumer it unblocks.** A funnel that stops the SDK's own parser from refusing a file will not notice that `w:tcPr`'s children are in the wrong order, because the SDK is perfectly happy to read a badly ordered `w:tcPr` — it has no sequence check to make.""")

# ------------------------------------------------------------------ §5
edit(
"Every malformation observed in this study — in the corpus and in the twelve editors' outputs — falls into one of seven shapes. Each shape has a characteristic fix.",
"Every malformation observed in this study — in the corpus and in the thirteen participants' outputs — falls into one of seven shapes. Each shape has a characteristic fix.")

edit(
"| 1 | **Sequence written from a map, not from the schema's order** | Fidus: `w:footnotePr` after `w:compat` | emit children in the schema's sequence order |",
"| 1 | **Sequence written from a map, not from the schema's order** | Fidus: `w:footnotePr` after `w:compat`; Docxodus: the SDK re-prints `w:tcPr`'s children in the order it read them | emit children in the schema's sequence order |")

# ------------------------------------------------------------------ §7
edit(
"5. **\"No editor diagnoses malformed input\" was true of the first eleven and false of the twelfth.** Plate.js was added on 2026-10-30 and it **refuses** the broken corpus with a named diagnostic (`decode-failed`) rather than producing a damaged file. The precise statement is now: **no editor repairs malformed input; one of the twelve detects it, and detects exactly one of the twelve defect classes.**",
"""5. **"No editor diagnoses malformed input" was true of the first eleven and false of the twelfth.** Plate.js was added on 2026-10-30 and it **refuses** the broken corpus with a named diagnostic (`decode-failed`) rather than producing a damaged file. The precise statement is now: **no editor repairs malformed input; one of the thirteen detects it, and detects exactly one of the twelve defect classes.**
6. **"No editor repairs anything" is true of these twelve defect classes and false as a general statement.** Docxodus ships a repair funnel (`PackageOpenRepair`) that fixes four classes of package defect on the way in. It repairs none of the twelve here, because it is aimed at defects that would make the **Open XML SDK's own parser** refuse the file, not at defects that make **Microsoft Word** refuse it. The distinction is worth keeping for anyone reading the TL;DR literally: a repair stage is scoped to the consumer it unblocks, and Docxodus's is scoped to the SDK, not to Word.""")

# ------------------------------------------------------------------ Reproducing
edit(
"""build/folio_deltext_test.py          # the decisive Folio repair experiment
build/officeopen_rels_test.py        # the decisive office-open / Docen repair experiment""",
"""build/folio_deltext_test.py          # the decisive Folio repair experiment
build/officeopen_rels_test.py        # the decisive office-open / Docen repair experiment

# Docxodus, over the clean and the broken corpus:
cd harness/ui/docxodus && node roundtrip.mjs ../../fixture/complex.docx        ../../out/docxodus/complex.docx
cd harness/ui/docxodus && node roundtrip.mjs ../../fixture/complex_broken.docx ../../out_broken/docxodus/complex.docx""")

edit(
"python3 build/word_open.py out_broken/<editor>/complex.docx ...   # broken corpus",
"python3 build/word_open.py out_broken/<editor>/complex.docx ...   # broken corpus")


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
