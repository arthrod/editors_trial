#!/usr/bin/env python3
"""Refresh the main report's measured figures to the current scorer output.

Every replacement is asserted to match exactly once, so a silently drifted
number cannot slip through this script.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "Open-Source DOCX Editors Re-verified Against Code and Measured Round-Trip (2026).md"

EDITS: list[tuple[str, str]] = [
    # ---- headline -----------------------------------------------------------
    (
        "**Headline result:** only three projects survive the corpus intact — **SuperDoc (100%)**, **Folio (98.5%)** and **eigenpal (98.5%)**. **GenOffice** matches Folio.",
        "**Headline result:** only two participants survive the corpus with zero failed checks — **SuperDoc (100%)** and **Docxodus (100%)**. **GenOffice** and **eigenpal** score 98.5%, **Folio** 97.5%.",
    ),
    (
        "> **Plate.js** (`udecode/plate`, **16,680★** — the second-most-starred project in this trial) has been added: cloned at `08b1571f2`, driven through its own headless `importDocx` → `exportDocx` path with **45 base plugins** and Plate's own **static presentation kit**, and scored on the same 97 checks. It scores **20.5%** — last in the trial",
        "> **Plate.js** (`udecode/plate`, **16,684★** — the second-most-starred project in this trial) has been added: cloned at `08b1571f2`, driven through its own headless `importDocx` → `exportDocx` path with **45 base plugins** and Plate's own **static presentation kit**, and scored on the same 99 checks. It scores **20.6%** — last in the trial",
    ),
    (
        "**Star count turned out to have no relationship to fidelity** — the two most-starred projects in the trial (WordCraft, 16,740★, and Plate, 16,680★) score 83.0% and 20.5%, while the winner has 1,117.",
        "**Star count turned out to have no relationship to fidelity** — the two most-starred projects in the trial (WordCraft, 16,875★, and Plate, 16,684★) score 84.9% and 20.6%, while the winner has 1,117.",
    ),
    # ---- TL;DR --------------------------------------------------------------
    (
        "- **Best measured fidelity: SuperDoc V2.** 100% on the 97-point corpus, 31/31 critical features, 100% text retention, all 35 package parts preserved, and a genuine re-save (8 parts re-serialized, 27 untouched parts passed through byte-identically). It is the only project with **zero** failed checks and the only one whose second pass is also a perfect, byte-identical fixed point.",
        "- **Best measured fidelity: SuperDoc V2.** 100% on the 99-check corpus, 29/29 critical features, 100% text retention, all 35 package parts preserved, and a genuine re-save (8 parts re-serialized, 27 untouched parts passed through byte-identically). It has **zero** failed checks, and its second pass is a perfect, byte-identical fixed point.\n- **Docxodus matches it.** The Open XML SDK also scores 100% — 29/29 critical, 100% text, all 35 parts, zero failed checks, and a byte-identical second pass — with **0 changed, 0 dropped and 0 added** parts. It is the only participant in the study that draws its boundary around a set of *parts* rather than a set of *names*.",
    ),
    (
        "- **Four of the eight re-tested editors reach a byte-identical fixed point** — SuperDoc, Folio, eigenpal and GenOffice all reproduce their own output exactly when it is fed back through their code path. office-open and Docen do not: **their own output is malformed XML**, because the chart and SmartArt regeneration paths drop the local `a:` namespace binding their first pass emitted.",
        "- **Five of the thirteen participants reach a byte-identical fixed point** — SuperDoc, Docxodus, GenOffice, eigenpal and Folio all reproduce their own output exactly when it is fed back through their code path. office-open and Docen do not: **their own output is malformed XML**, because the chart and SmartArt regeneration paths drop the local `a:` namespace binding their first pass emitted.",
    ),
    (
        "- **Folio and eigenpal are effectively tied on features (98.5%), but Folio keeps 100% of the text and eigenpal keeps 97.6%** — because eigenpal flattens `mc:AlternateContent` to its `mc:Choice` branch and drops the fallback text. Folio's only loss is `w14:paraId`/`w14:textId`.",
        "- **eigenpal and GenOffice score 98.5% and Folio 97.5% — and Folio keeps 100% of the text against eigenpal's 97.6%**, because eigenpal flattens `mc:AlternateContent` to its `mc:Choice` branch and drops the fallback text. Folio's two losses are the `w14` run identifiers and the move source, which it serializes with `w:delText` where Word writes `w:t`.",
    ),
    (
        "- **office-open (95.5%) and Docen (92.0%) are full-regeneration pipelines.**",
        "- **office-open (93.5%) and Docen (91.5%) are full-regeneration pipelines.**",
    ),
    (
        "- **WordCraft (83.0%) is the most interesting failure.**",
        "- **WordCraft (84.9%) is the most interesting failure.**",
    ),
    (
        "- **Plate.js (20.5%) is the most instructive result, in both directions.**",
        "- **Plate.js (20.6%) is the most instructive result, in both directions.**",
    ),
    (
        "- **LibreOffice, as a calibration baseline, scores 86.0% / 77.4% critical.**",
        "- **LibreOffice, as a calibration baseline, scores 86.4% / 79.3% critical.**",
    ),
    (
        "- **The three weakest are not round-trip pipelines.** Fidus Writer (23.0%) has a DOCX importer that **drops all tables**; canvas-editor + plugin (24.0%) is a canvas editor with a DOCX export format and **crashes on `w:vMerge`**; docs.plus (21.0%) is an HTML bridge",
        "- **The three weakest are not round-trip pipelines.** Fidus Writer (23.6%) has a DOCX importer that **drops all tables**; canvas-editor + plugin (24.6%) is a canvas editor with a DOCX export format and **crashes on `w:vMerge`**; docs.plus (21.1%) is an HTML bridge",
    ),
    (
        "- **Popularity does not predict fidelity.** Star counts for the twelve projects are in §\"How the twelve were chosen\". The two most-starred (WordCraft 16,740★, Plate 16,680★) score 83.0% and 20.5%; the winner has 1,117★; the project that ties for second place has 31★.",
        "- **Popularity does not predict fidelity.** Star counts for the projects are in §\"How the twelve were chosen\", re-measured on 2026-11-01. The two most-starred (WordCraft 16,875★, Plate 16,684★) score 84.9% and 20.6%; the winner has 1,117★; the project that ties for second place has 32★.",
    ),
    # ---- rankings -----------------------------------------------------------
    (
        "1. **SuperDoc V2.** 100% on the corpus, 31/31 critical, 100% text, no part lost, genuine re-save with byte-identical passthrough of untouched parts.\n2. **Folio.** 98.5%, 100% text, no part lost. Loses only `w14:paraId`/`textId`.\n3. **GenOffice.** 98.5%, all 35 parts kept, one block regenerated.\n4. **eigenpal.** 98.5% on features but 97.6% text: `mc:AlternateContent` flattened to `mc:Choice`.\n5. **office-open.** 95.5%, 100% text, but regeneration drops `w16du`/`w14` metadata and it is not idempotent.\n6. **Docen.** 92.0%, inherits and extends office-open's losses.\n7. **WordCraft.** 83.0%.",
        "1. **SuperDoc V2.** 100% on the corpus, 29/29 critical, 100% text, no part lost, genuine re-save with byte-identical passthrough of untouched parts.\n2. **Docxodus.** 100%, 29/29 critical, 100% text, 35/35 parts with 0 changed and 0 dropped.\n3. **GenOffice.** 98.5%, all 35 parts kept, one block regenerated.\n4. **eigenpal.** 98.5% on features but 97.6% text: `mc:AlternateContent` flattened to `mc:Choice`.\n5. **Folio.** 97.5%, 100% text, no part lost. Loses `w14:paraId`/`textId` and the move source's `w:t`.\n6. **office-open.** 93.5%, 100% text, but regeneration drops `w16du`/`w14` metadata and it is not idempotent.\n7. **Docen.** 91.5%, inherits and extends office-open's losses.\n8. **WordCraft.** 84.9%.",
    ),
    (
        "**On popularity [MEASURED].** Star counts for all twelve are in §\"How the twelve were chosen\". **They do not predict fidelity.** The two most-starred projects in the trial, WordCraft (16,740★) and Plate (16,680★), score 83.0% and 20.5%. The winner has 1,117★, and the runner-up has **31★**",
        "**On popularity [MEASURED].** Star counts are in §\"How the twelve were chosen\", re-measured on 2026-11-01. **They do not predict fidelity.** The two most-starred projects in the trial, WordCraft (16,875★) and Plate (16,684★), score 84.9% and 20.6%. The winner has 1,117★, and the runner-up has **32★**",
    ),
    # ---- master comparison table -------------------------------------------
    (
        "| **100.0%** · 31/31 · text 100% |",
        "| **100.0%** · 29/29 · text 100% |",
    ),
    (
        "| **98.5%** · 30/31 · text 100% |",
        "| **97.5%** · 28/29 · text 100% |",
    ),
    (
        "| **98.5%** · 30/31 · text 98.8% |",
        "| **98.5%** · 28/29 · text 98.8% |",
    ),
    (
        "| **98.5%** · 30/31 · text 97.6% |",
        "| **98.5%** · 28/29 · text 97.6% |",
    ),
    (
        "| **95.5%** · 28/31 · text 100% |",
        "| **93.5%** · 25/29 · text 100% |",
    ),
    (
        "| **92.0%** · 26/31 · text 99.4% |",
        "| **91.5%** · 24/29 · text 99.4% |",
    ),
    (
        "| **83.0%** · 21/31 · text 97.6% |",
        "| **84.9%** · 21/29 · text 97.6% |",
    ),
    (
        "| **24.0%** · 7/31 · text 88.2% |",
        "| **24.6%** · 7/29 · text 88.2% |",
    ),
    (
        "| **23.0%** · 7/31 · text 71.0% |",
        "| **23.6%** · 7/29 · text 71.0% |",
    ),
    (
        "| **21.0%** · 7/31 · text 91.7% |",
        "| **21.1%** · 7/29 · text 91.7% |",
    ),
    (
        "| **20.5%** · 6/31 · text 91.7% |",
        "| **20.6%** · 6/29 · text 91.7% |",
    ),
    # ---- per-repository measured lines -------------------------------------
    (
        "**Measured [MEASURED].** 97/97. The only project with no failed check.",
        "**Measured [MEASURED].** 99/99. One of only two participants with no failed check.",
    ),
    (
        "**Measured [MEASURED].** 98.5%, 100% text, no part lost. Sole loss: `w14:paraId`/`w14:textId` on run properties.",
        "**Measured [MEASURED].** 97.5%, 100% text, no part lost. Two losses: `w14:paraId`/`w14:textId` on run properties, and the move source, which is serialised with `w:delText` where Word writes `w:t`.",
    ),
    (
        "**Measured [MEASURED].** 98.5%, all 35 parts kept, 40 of 41 blocks kept verbatim, **1 block regenerated** — the table, whose content in `w:vMerge=\"continue\"` cells was lost.",
        "**Measured [MEASURED].** 98.5%, all 35 parts kept, 40 of 41 blocks kept verbatim, **1 block regenerated** — the table, whose content in `w:vMerge=\"continue\"` cells was lost. Its second pass is a byte-identical fixed point.",
    ),
    (
        "**Measured [MEASURED].** 98.5% on features, **97.6% text** — the only top-four project that loses visible text.",
        "**Measured [MEASURED].** 98.5% on features, **97.6% text** — the only top-five project that loses visible text. Its second pass is a byte-identical fixed point.",
    ),
    # ---- what each project actually lost -----------------------------------
    (
        "**SuperDoc V2 — nothing.** 97/97 checks. All 35 parts present, none added.",
        "**SuperDoc V2 — nothing.** 99/99 checks. All 35 parts present, none added.",
    ),
    (
        "Seven of the 97 checks are exactly that (`pkg.chart`, `pkg.smartart`, `pkg.ole`, `pkg.media`, `ref.chart`, `ref.smartart`, `ref.ole`), and SuperDoc passes all seven. [MEASURED]",
        "Seven of the 99 checks are exactly that (`pkg.chart`, `pkg.smartart`, `pkg.ole`, `pkg.media`, `ref.chart`, `ref.smartart`, `ref.ole`), and SuperDoc passes all seven. [MEASURED]\n\n**Docxodus — nothing.** 99/99 checks, 35/35 parts, 0 parts lost and 0 added. It is the only participant in the study with **nothing changed and nothing dropped**: 25 parts come through byte-identical and 10 are re-serialised. It reaches that without a policy at all — it opens the package with `WordprocessingDocument.Open(stream, isEditable: true)` and saves the same object graph back out, so parts it has no schema for are carried through untouched and parts it owns are re-printed. Its second pass is a byte-identical fixed point. [MEASURED]",
    ),
    (
        "**Folio — 1 check.** Loses `w14:paraId`/`w14:textId` on run properties. Text is 100% intact. The loser's cause is narrow: Folio models the `w14` namespace for the *document* but does not round-trip `w14` identifiers on `w:rPr` children. [MEASURED]",
        "**Folio — 2 checks.** Text is 100% intact. The first loss is narrow: Folio models the `w14` namespace for the *document* but does not round-trip `w14` identifiers on `w:rPr` children. The second is the move source, which Folio serialises with `w:delText` where Word writes `w:t` — the same construct Word refuses the document for. [MEASURED]",
    ),
    (
        "**office-open — 3 checks.** Drops `w16du:dateUtc`, `w14:paraId`/`w14:textId`, and the `w16du` namespace declaration. Everything else survives, and text is 100% intact. **But it is not idempotent**: feeding its own output back through `parseDocument` → `generateDocument` yields `word/document.xml` that fails to parse with an unbound `a:` prefix — the chart and SmartArt drawings are emitted as `<a:graphic>` without rebinding the namespace. Second-pass score collapses to 32.0%. [MEASURED]",
        "**office-open — 5 checks.** Drops `w16du:dateUtc`, `w14:paraId`/`w14:textId`, and the `w16du` namespace declaration. Everything else survives, and text is 100% intact. The other two are the sharpest kind of loss, because the file looks whole: **the chart and SmartArt relationships in the saved body no longer resolve to any part.** The package still carries `word/charts/chart1.xml` and the four diagram parts, the body still carries the `w:drawing` element, and the original relationships are still in `word/_rels/document.xml.rels` — but the body was rewritten to use *different* relationship ids, and those ids were never written into the relationship part. Resolving the body forwards — every `r:id`, `r:embed`, `r:dm`, `r:lo`, `r:qs` and `r:cs` used in a part, looked up in *that part's* `.rels` — is what finds it. **And it is not idempotent**: feeding its own output back through `parseDocument` → `generateDocument` yields `word/document.xml` that fails to parse with an unbound `a:` prefix — the chart and SmartArt drawings are emitted as `<a:graphic>` without rebinding the namespace. Second-pass score collapses to 32.2%. [MEASURED]",
    ),
    (
        "**Docen — 6 checks.** Inherits every office-open loss, and adds its own: `w:noBreakHyphen`/`w:softHyphen` dropped, the tracked change inside `header2.xml` **relocated to `header3.xml`** (the loss is path-scoped, not content-scoped), and a one-character text difference. Second-pass score 30.5%, same unbound-prefix failure. [MEASURED]",
        "**Docen — 7 checks.** Inherits every office-open loss, including the two unresolvable chart and SmartArt relationships, and adds its own: `w:noBreakHyphen`/`w:softHyphen` dropped, the tracked change inside `header2.xml` **relocated to `header3.xml`** (the loss is path-scoped, not content-scoped), and a one-character text difference. Second-pass score 32.2%, same unbound-prefix failure. [MEASURED]",
    ),
    (
        "**WordCraft — 13 checks.**",
        "**WordCraft — 13 checks.**",
    ),
    (
        "**Fidus Writer — 76 checks.**",
        "**Fidus Writer — 77 checks.**",
    ),
    (
        "**canvas-editor + plugin — 74 checks.**",
        "**canvas-editor + plugin — 75 checks.**",
    ),
    (
        "**docs.plus — 77 checks.**",
        "**docs.plus — 79 checks.**",
    ),
    (
        "**Plate.js — 77 checks.**",
        "**Plate.js — 79 checks.**",
    ),
    # ---- popularity paragraph and star table --------------------------------
    (
        "The winner, SuperDoc, has **1,117★**. The project that ties for second place, Folio, has **31★** — fewer than a hundred people have starred it, and it loses a single check. The two most-starred projects in the trial, WordCraft and Plate, score **83.0%** and **20.5%**.",
        "The winner, SuperDoc, has **1,117★**. The project that ties for second place, Folio, has **32★** — fewer than a hundred people have starred it, and it loses two checks. The two most-starred projects in the trial, WordCraft and Plate, score **84.9%** and **20.6%**.",
    ),
    (
        "so it scores 20.5% while keeping 91.7% of the text.",
        "so it scores 20.6% while keeping 91.7% of the text.",
    ),
    (
        "**Measured [MEASURED].** 98.5%, all 35 parts kept, 40 of 41 blocks kept verbatim, **1 block regenerated** — the table, whose content in `w:vMerge=\"continue\"` cells was lost. Its second pass is a byte-identical fixed point. Its second pass is a byte-identical fixed point.",
        "**Measured [MEASURED].** 98.5%, all 35 parts kept, 40 of 41 blocks kept verbatim, **1 block regenerated** — the table, whose content in `w:vMerge=\"continue\"` cells was lost. Its second pass is a byte-identical fixed point.",
    ),
    (
        "**Measured [MEASURED].** 95.5%, 100% text, all 35 parts present — but `w16du:dateUtc`, `w14:paraId`/`textId` and the `w16du` namespace are dropped, and **the pipeline is not idempotent**: its own output re-parses with an unbound `a:` prefix (second pass 32.0%).",
        "**Measured [MEASURED].** 93.5%, 100% text, all 35 parts present — but `w16du:dateUtc`, `w14:paraId`/`textId` and the `w16du` namespace are dropped, the chart and SmartArt relationships in the saved body do not resolve, and **the pipeline is not idempotent**: its own output re-parses with an unbound `a:` prefix (second pass 32.2%).",
    ),
    (
        "**Measured [MEASURED].** 92.0%, 99.4% text, no part lost but four new header/footer parts. Inherits office-open's metadata losses and adds `w:noBreakHyphen`/`w:softHyphen` loss and relocation of the tracked change inside `header2.xml` to `header3.xml`. Same non-idempotence (second pass 30.5%).",
        "**Measured [MEASURED].** 91.5%, 99.4% text, no part lost but four new header/footer parts. Inherits office-open's metadata losses and the two unresolvable chart and SmartArt relationships, and adds `w:noBreakHyphen`/`w:softHyphen` loss and relocation of the tracked change inside `header2.xml` to `header3.xml`. Same non-idempotence (second pass 32.2%).",
    ),
    (
        "**Measured [MEASURED].** 83.0%, 97.6% text. It keeps the **chart, all four SmartArt parts, the OLE object, the embedded workbook and the image**",
        "**Measured [MEASURED].** 84.9%, 97.6% text. It keeps the **chart, all four SmartArt parts, the OLE object, the embedded workbook and the image**",
    ),
    (
        "**Measured [MEASURED].** 24.0%, 88.2% text, 21 of 35 parts lost.",
        "**Measured [MEASURED].** 24.6%, 88.2% text, 21 of 35 parts lost.",
    ),
    (
        "**Measured [MEASURED].** 23.0%, 71.0% text, 24 of 35 parts lost.",
        "**Measured [MEASURED].** 23.6%, 71.0% text, 24 of 35 parts lost.",
    ),
    (
        "The reported 23.0% is the genuine model-based round trip.",
        "The reported 23.6% is the genuine model-based round trip.",
    ),
    (
        "**Measured [MEASURED].** 21.0%, 91.7% text, 24 of 35 parts lost.",
        "**Measured [MEASURED].** 21.1%, 91.7% text, 24 of 35 parts lost.",
    ),
    (
        "**Measured [MEASURED].** 20.5% weighted, 19.4% critical (6/31), **91.7% text retention**, 11 of 35 parts kept, 77 failed checks.",
        "**Measured [MEASURED].** 20.6% weighted, 20.7% critical (6/29), **91.7% text retention**, 11 of 35 parts kept, 79 failed checks.",
    ),
    (
        "- **Do not choose on stars.** The two most-starred projects here score 83.0% and 20.5%; the winner has 1,117★ and the runner-up 31★.",
        "- **Do not choose on stars.** The two most-starred projects here score 84.9% and 20.6%; the winner has 1,117★ and the runner-up 32★.",
    ),
]


def main() -> int:
    """Apply every edit, refusing to continue if one does not match exactly once."""
    text = REPORT.read_text(encoding="utf-8")
    applied = skipped = 0
    for old, new in EDITS:
        n = text.count(old)
        if n == 0 and text.count(new) == 1:
            skipped += 1
            continue
        if n != 1:
            print(f"MATCH FAIL ({n}): {old[:90]!r}")
            return 1
        text = text.replace(old, new)
        applied += 1
    REPORT.write_text(text, encoding="utf-8")
    print(f"applied {applied} edits, {skipped} already present, to {REPORT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
