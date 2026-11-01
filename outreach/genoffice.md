We measured GenOffice together with eleven other open-source DOCX tools and published the whole thing — the corpus, the harnesses, the scorer, the logs and the reports — so that every number below can be checked and corrected.

**Everything is here: https://github.com/arthrod/editors_trial**

## What the trial is

One input: `fixture/complex.docx`, a 35-part hand-built OOXML document that deliberately contains tracked changes, complex and simple fields, five content controls, tables with merges and nested tables, three sections including a landscape two-column one, a bar chart, a SmartArt diagram, an OLE object with an embedded workbook, an image, footnotes, endnotes, comments, headers and footers, and a set of namespace extensions Word writes.

Every editor was driven through **its own** documented import and export path — GenOffice's own entry point, not a re-implementation of it — and the result was scored by a 99-check diff at package-part, element, attribute and text level. Every output was re-opened to confirm it is still a valid document. The scorer, the harnesses, the fixture and the raw logs are in the repository.

## What we measured for GenOffice

**98.5% weighted, 96.6% critical (28/29), 98/99 checks, 98.8% text retention, 35/35 parts kept — 1 failed check.**

GenOffice keeps the whole package and loses almost nothing, and the way it keeps it is worth naming:

- **The "verbatim copy of untouched blocks" claim holds for 40 of 41 blocks.** The save plan showed 40 blocks kept as `original` and **1 regenerated as `xml`** — the table, whose block signature did not match. That is the design working as intended: a selective save that falls back to regeneration for the one block it does not recognise.
- **Its second pass is a byte-identical fixed point**, one of five in the trial.
- **It is the only editor in the trial that draws the SmartArt's node texts** (Report C §2.3). Where Word reserves a completely blank band, GenOffice draws a dashed band labelled "SmartArt" containing "Step one" and "Step two". The two applications show the reader *different information in the same place*: Word shows nothing, GenOffice shows the diagram's data as text. That is a defensible reading of an underspecified construct, and it is the kind of thing that is easy to miss in a benchmark and impossible to miss in a screenshot.
- It **paginates the corpus into six pages — the same count as Word** — and draws the chart as SVG with the correct bar heights (4.3 / 2.5 / 3.5) and the correct axis labels.
- On the hostile-input axis it puts a **named ceiling on the zip entry flood**, cleans the attribute bomb and refuses the corrupt-parts package (Report D).
- The single failing check is `text.exact`: the text inside the vertically-merged continuation cells. Worth saying plainly that **this matches Word's own merge semantics** — Word discards content in vertically-merged continuation cells too — so the behaviour is defensible, and it is still a text loss, which is why it is counted as one.

## The reports, and what each one is

- **[Report A — Serialization by Namespace](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20A%20-%20Serialization%20by%20Namespace%20%282026%29.md)** — what each of the corpus's 27 namespace vocabularies does, and what it costs when it is lost. One section per namespace: what the vocabulary is in WordprocessingML, what each editor's own source does with it, and what each editor actually did to it, measured.
- **[Report A2 — Pass-Through](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20A2%20-%20Pass-Through%20%282026%29.md)** — the complement of fidelity: of the bytes that came out, how many did the editor never even look at. Pass-through is the strongest possible fidelity and the weakest possible editing, and it is the same fact.
- **[Report B — Malformed Parts, Causes, Detection and Repair](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20B%20-%20Malformed%20Parts%2C%20Causes%20and%20Repair%20%282026%29.md)** — twelve defect classes that Microsoft Word refuses to open, found by bisecting the corpus against Word itself; what malformed parts look like, what causes them, and whether any editor repairs them.
- **[Report C — Rendering Versus Word](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20C%20-%20Rendering%20Versus%20Word%20%282026%29.md)** — what each editor's own running application puts on the page, screenshotted and compared with Word's own PDF export of the same corpus. Fidelity in the file and fidelity on the page are two different results, and this report keeps them apart.
- **[Report D — Safety, Resource Bombs and Hostile Input](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20D%20-%20Safety%2C%20Resource%20Bombs%20and%20Hostile%20Input%20%282026%29.md)** — ten hostile packages — decompression, entry flood, attribute bomb, deep nesting, entities, zip-slip, external relationships, active content, layout bomb, corrupt parts — graded on a separate axis, because preserving a hostile payload is not the same result as a crash.

- **The per-tool note for GenOffice:** https://github.com/arthrod/editors_trial/blob/main/reports/extras/genoffice.md
- **What each measured tool is:** https://github.com/arthrod/editors_trial/blob/main/reports/vendors.md

## If anything here is wrong, please open a pull request

We would rather have a correction from you than a quiet disagreement. Three things are worth correcting, in this order of usefulness:

1. **A number.** Every figure in the reports is produced by `python3 build/score_all.py` over the committed outputs in `out/`, and it is checked against the scorer's own output by `build/check_report_consistency.py`, so a figure that cannot be reproduced fails the gate rather than slipping through. If one of ours is wrong, open a PR against the file that carries it — https://github.com/arthrod/editors_trial/blob/main/reports/extras/genoffice.md for the per-tool note, or the report that quotes it — and if the figure comes from the measurement rather than from prose, include the corrected `out/genoffice/score.json` too. `build/test_report_claims.py` enforces that the per-tool note still agrees with the shipped scorer, so it will tell you whether a correction is self-consistent.
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
python3 build/check_roundtrip.py fixture/complex.docx out/genoffice/complex.docx
bash build/run_second_pass.sh                    # the idempotence table
```
