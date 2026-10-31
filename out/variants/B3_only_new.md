# Malformed Parts: Causes, Detection, and Repair (2026-10-30)

**A companion to *Open-Source DOCX Editors, Re-verified Against Code and Measured by Round-Trip (2026-10-29)*** and to *What Is Serialized, What Is Pass-Through, and What Is Actually Rendered (2026-10-30)*.

The first report found that the corpus it used — a hand-built 35-part adversarial DOCX — **Microsoft Word 16.115 would not open at all**, and located twelve defect classes behind that. This report closes the loop: what malformed parts look like, what causes them, and — the question the first report could not answer — **does any editor repair a malformed input, or does it preserve the damage?**

---

### 4.1 The Word verdict is *explained* by the defect table — and it inverts the ranking

The last column of the table above is not an independent measurement; it falls out of the other columns. This is worth stating precisely, because the pattern is the single most useful result in this report.

Three of the eleven defect classes are fatal to Word on their own, established by isolation in the first report: **d10** (`w:delText` inside `w:moveFrom`), **d11** (block-level `m:oMathPara`) and **d12** (`w:dirty="true"` on a `w:fldChar`). Every editor's Word verdict is consistent with its own defect table:

| Editor | d10 | d11 | d12 | Word verdict | The verdict is explained by |
|---|---|---|---|---|---|
| SuperDoc | YES | YES | YES | REFUSED | all three fatal classes survive |
| Folio | YES | YES | YES | REFUSED | all three fatal classes survive |
| GenOffice | YES | YES | YES | REFUSED | all three fatal classes survive |
| eigenpal | YES | YES | YES | REFUSED | all three fatal classes survive |
| office-open | YES | YES | no | REFUSED | two fatal classes survive |
| Docen | YES | YES | no | REFUSED | two fatal classes survive |
| WordCraft | no | no | **YES** | REFUSED | **one** fatal class survives — `w:dirty` alone is enough |
| Fidus Writer | no | no | no | REFUSED | **not explained by the corpus** — see below |
| canvas-editor + plugin | no | no | no | OPENED | nothing fatal survives |
| docs.plus | no | no | no | OPENED | nothing fatal survives |
| LibreOffice (baseline) | no | no | no | OPENED | nothing fatal survives; the surviving `w:trPr` reorder is tolerated |

Two of these rows are individually decisive:

- **WordCraft isolates `w:dirty` as the sole cause of its refusal.** It is the only editor that removed d10 and d11 and kept d12 — and it still died. That is the cleanest possible confirmation that `w:dirty="true"` on a `w:fldChar` is fatal on its own, arrived at through a completely different route than the isolation probes in the first report.
- **Fidus Writer's refusal is its own, not the corpus's.** Fidus dropped every defect and still could not open. It was *also* refused on the clean corpus (§3.3, eleven schema violations), so the broken corpus changed nothing for it. This is the one row where "the corpus killed it" is the wrong explanation, and it is the row that prevents the table from being read as a rule.

### 4.2 The broken corpus kills exactly the four editors that were faithful — and spares exactly the three that discard

Putting the two Word matrices side by side is the clearest single statement of what pass-through costs.

| Editor | Clean corpus | Broken corpus | Verdict flipped by the corpus? |
|---|---|---|---|
| SuperDoc | OPENED | REFUSED | **yes** |
| GenOffice | OPENED | REFUSED | **yes** |
| eigenpal | OPENED | REFUSED | **yes** |
| WordCraft | OPENED | REFUSED | **yes** |
| Folio | REFUSED | REFUSED | no — already broken |
| office-open | REFUSED | REFUSED | no — already broken |
| Docen | REFUSED | REFUSED | no — already broken |
| Fidus Writer | REFUSED | REFUSED | no — its own defect |
| canvas-editor + plugin | OPENED | OPENED | no — it dropped the damage |
| docs.plus | OPENED | OPENED | no — it dropped the damage |
| LibreOffice (baseline) | OPENED | OPENED | no — it dropped the damage |

**Four editors that were faithful to the clean file die on the malformed one, and the three that survive are the three that throw the content away.** Fidelity and robustness are anti-correlated here, and the reason is structural rather than accidental: an editor that preserves the document preserves the damage inside it, because the damage *is* the document as far as a pass-through writer is concerned. The editors that survive the malformed input are the ones that were already losing most of the document — they lose nothing more.

That is the uncomfortable trade a fidelity score hides completely. The first report's ranking puts SuperDoc first and canvas second-to-last. On malformed input the order **inverts**: canvas and docs.plus open, and SuperDoc does not.

### 4.3 What "repair" would even have looked like

For completeness, the three interventions that would have turned a REFUSED into an OPENED, none of which any editor performs:

1. **Re-emit the three fatal constructs in the shape Word accepts.** `w:delText` → `w:t` inside `w:moveFrom`; `m:oMathPara` → wrapped in a `w:p`; `w:dirty="true"` → `w:dirty="false"` or removed. Each is a one-attribute or one-element change, and each was proven to flip the verdict in the first report.
2. **Validate the output against the transitional schema before writing it.** This catches the five ordering classes and the malformed `ST_LongHexNumber`, and it is cheap: `build/validate_ooxml.py` does it in under a second for the whole corpus.
3. **Re-import the output and compare.** This catches the shape-5 failures — the ones where a writer emits markup it never validated, such as office-open's `<a:graphic>` with no `xmlns:a` — because the second pass is the one that fails to bind the prefix.

Not one editor does any of the three. The pass-through editors cannot, by construction: repairing a part requires modelling it, and modelling it is what pass-through refuses to do.


---

