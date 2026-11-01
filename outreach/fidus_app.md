We measured Fidus Writer together with eleven other open-source DOCX tools and published the whole thing — the corpus, the harnesses, the scorer, the logs and the reports — so that every number below can be checked and corrected.

**Everything is here: https://github.com/arthrod/editors_trial**

## What the trial is

One input: `fixture/complex.docx`, a 35-part hand-built OOXML document that deliberately contains tracked changes, complex and simple fields, five content controls, tables with merges and nested tables, three sections including a landscape two-column one, a bar chart, a SmartArt diagram, an OLE object with an embedded workbook, an image, footnotes, endnotes, comments, headers and footers, and a set of namespace extensions Word writes.

Every editor was driven through **its own** documented import and export path — Fidus Writer's own entry point, not a re-implementation of it — and the result was scored by a 99-check diff at package-part, element, attribute and text level. Every output was re-opened to confirm it is still a valid document. The scorer, the harnesses, the fixture and the raw logs are in the repository.

## What we measured for Fidus Writer

**23.6% weighted, 24.1% critical (7/29), 22/99 checks, 71.0% text retention, 11/35 parts kept — 77 failed checks.**

Fidus Writer scores low on fidelity and **highest on safety of every participant in the trial**, and we think both halves of that belong in the same issue.

**On safety, Fidus Writer is the strongest result we measured** (Report D). It **cleaned seven of the ten hostile packages** — the entry flood, the attribute bomb, the zip-slip, the external-relationship bomb, the active-content package, the layout bomb and the corrupt-parts package — put a **named ceiling on the deep nest**, and refused the entity bomb. Its safety grade of 0.72 is the highest in the study, and the reason is specific rather than accidental: the exporter is template-driven, so it writes what the template asks for and not what the input happened to contain.

**On fidelity, one absent feature dominates the number.** There is **no table handling anywhere in `src/importer/docx/*`**, so both fixture tables — 11 rows, 16 cells — are gone before the export even begins. The importer also reports twelve unhandled element classes (`w:proofErr`, `w:ins`, `w:del`, `w:moveFrom`/`w:moveTo` and their range markers, `w:bookmarkStart`/`End`, `w:fldSimple`, `w:permStart`/`End`). **The entire table row in our scorecard comes from that one missing handler.** A DOM census of your running application confirms it: the editor DOM contains no table, no chart, no SmartArt band, no OLE object, no equation and no text box (Report C §2.11).

Two other things we found, which are yours to fix:

- The template-adjustment worker throws `RangeError: Invalid content for node title` on the corpus's first heading, which leaves the "Updating document. Please wait…" cover permanently on screen. The document renders underneath it; the cover is what stops you seeing it.
- The exporter is **placeholder-driven** — `{title}`, `{@<part-id>}`, `{@bibliography}`, `{@copyright}`, `{@licenses}` — so the exported styles, numbering and settings are the *template's*, not the corpus's. That is a reasonable design for an academic publishing tool; it is also why a fidelity score is a poor fit, and we say so in the report rather than only in the number.

**What Fidus Writer does that nothing else in the trial does** is worth saying as well: one schema exporting to JATS, HTML, LaTeX, Pandoc JSON, EPUB, DOCX and ODT, with a custom template. That is a publishing engine, not an editor, and it is why the round trip is the wrong instrument for it.

We are filing the same note on the package repository, because the DOCX importer and exporter we measured live in `@fiduswriter/document` and not in the application. The two findings that belong to the application rather than to the package are these: the "Updating document. Please wait…" cover that never clears, and the fact that the editor DOM contains no table, no chart, no SmartArt band, no OLE object, no equation and no text box when the corpus is opened (Report C §2.11). The fidelity numbers are the same in both places; the round trip we ran was the package's own importer and exporter, not a full application round trip.

## The reports, and what each one is

- **[Report A — Serialization by Namespace](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20A%20-%20Serialization%20by%20Namespace%20%282026%29.md)** — what each of the corpus's 27 namespace vocabularies does, and what it costs when it is lost. One section per namespace: what the vocabulary is in WordprocessingML, what each editor's own source does with it, and what each editor actually did to it, measured.
- **[Report A2 — Pass-Through](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20A2%20-%20Pass-Through%20%282026%29.md)** — the complement of fidelity: of the bytes that came out, how many did the editor never even look at. Pass-through is the strongest possible fidelity and the weakest possible editing, and it is the same fact.
- **[Report B — Malformed Parts, Causes, Detection and Repair](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20B%20-%20Malformed%20Parts%2C%20Causes%20and%20Repair%20%282026%29.md)** — twelve defect classes that Microsoft Word refuses to open, found by bisecting the corpus against Word itself; what malformed parts look like, what causes them, and whether any editor repairs them.
- **[Report C — Rendering Versus Word](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20C%20-%20Rendering%20Versus%20Word%20%282026%29.md)** — what each editor's own running application puts on the page, screenshotted and compared with Word's own PDF export of the same corpus. Fidelity in the file and fidelity on the page are two different results, and this report keeps them apart.
- **[Report D — Safety, Resource Bombs and Hostile Input](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20D%20-%20Safety%2C%20Resource%20Bombs%20and%20Hostile%20Input%20%282026%29.md)** — ten hostile packages — decompression, entry flood, attribute bomb, deep nesting, entities, zip-slip, external relationships, active content, layout bomb, corrupt parts — graded on a separate axis, because preserving a hostile payload is not the same result as a crash.

- **The per-tool note for Fidus Writer:** https://github.com/arthrod/editors_trial/blob/main/reports/extras/fidus.md
- **What each measured tool is:** https://github.com/arthrod/editors_trial/blob/main/reports/vendors.md

## If anything here is wrong, please open a pull request

We would rather have a correction from you than a quiet disagreement. Three things are worth correcting, in this order of usefulness:

1. **A number.** Every figure in the reports is produced by `python3 build/score_all.py` over the committed outputs in `out/`, and it is checked against the scorer's own output by `build/check_report_consistency.py`, so a figure that cannot be reproduced fails the gate rather than slipping through. If one of ours is wrong, open a PR against the file that carries it — https://github.com/arthrod/editors_trial/blob/main/reports/extras/fidus.md for the per-tool note, or the report that quotes it — and if the figure comes from the measurement rather than from prose, include the corrected `out/fidus/score.json` too. `build/test_report_claims.py` enforces that the per-tool note still agrees with the shipped scorer, so it will tell you whether a correction is self-consistent.
2. **A reading of your code.** The `[CODE]` citations name a file and a line. If we read your implementation wrong — or if it has moved on since the commit we pinned — a PR that fixes the citation is as welcome as one that fixes a number.
3. **A judgement.** Some of the report's claims are readings, not measurements: what a design decision "means", which of two behaviours is the better one. If you disagree with a judgement, the place to say so is a pull request against the report, not a new issue.

We are not going to argue about the framing of a published number. If our reading is wrong, the fix belongs in the repository, in public, where the next person can check it.

## What the trial does not claim

- **One document.** The corpus is deliberately hostile, but it is one document, not a corpus survey.
- **A round trip, not an editing session.** Every project was exercised on import → export with no edits. Selective-save behaviour that only triggers on a dirty block is therefore not distinguished from unconditional regeneration, except where the project documents otherwise.
- **Word as a validator, not as an oracle.** The corpus is checked against the ECMA-376 schemas and opened in Microsoft Word 16.115, but the outputs were judged by the scorer and by LibreOffice. A document that Word opens but that the scorer flags is still a loss.
- **A moving instrument.** The checker gained checks over the life of the study; the published figures come from the current 99-check scorer, and the repository is the record of that.

## Reproducing it

```sh
git clone https://github.com/arthrod/editors_trial.git && cd editors_trial
python3 build/score_all.py                       # the scorecard table
python3 build/check_roundtrip.py fixture/complex.docx out/fidus/complex.docx
bash build/run_second_pass.sh                    # the idempotence table
```
