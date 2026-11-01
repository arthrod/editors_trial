We measured office-open together with eleven other open-source DOCX tools and published the whole thing — the corpus, the harnesses, the scorer, the logs and the reports — so that every number below can be checked and corrected.

**Everything is here: https://github.com/arthrod/editors_trial**

## What the trial is

One input: `fixture/complex.docx`, a 35-part hand-built OOXML document that deliberately contains tracked changes, complex and simple fields, five content controls, tables with merges and nested tables, three sections including a landscape two-column one, a bar chart, a SmartArt diagram, an OLE object with an embedded workbook, an image, footnotes, endnotes, comments, headers and footers, and a set of namespace extensions Word writes.

Every editor was driven through **its own** documented import and export path — office-open's own entry point, not a re-implementation of it — and the result was scored by a 99-check diff at package-part, element, attribute and text level. Every output was re-opened to confirm it is still a valid document. The scorer, the harnesses, the fixture and the raw logs are in the repository.

## What we measured for office-open

**93.5% weighted, 86.2% critical (25/29), 94/99 checks, 100.0% text retention, 35/35 parts kept, none lost and none added — 5 failed checks.**

office-open keeps **100% of the text** and every one of the 35 package parts. That is the joint-highest text retention in the trial, and it is not a small thing for a library that rebuilds the package from a parsed model.

The README's own coverage claim — all 2,273 elements and 1,969 attributes across the 21 OOXML Transitional schemas — is ambitious, and the measurement is broadly consistent with it: what a typed, XSD-shaped model carries is what it carries, and the gaps are where the gaps are.

**Three findings, all in the chart and diagram path, all of which we would like fixed:**

1. **The chart and SmartArt relationships in the saved body do not resolve to any part.** The package still carries `word/charts/chart1.xml` and the four diagram parts, and the body still carries the `w:drawing` element — but the body was rewritten to use *different* relationship ids, and those ids were never written into `word/_rels/document.xml.rels`. The original relationships survive, still resolve, and nothing uses them. This is the defect class every conventional checker misses: the file passes a part-level diff, a content-types audit, a schema validation and an XML fidelity score, and still does not draw the chart. Resolving the body *forwards* — every `r:id`, `r:embed`, `r:dm`, `r:lo`, `r:qs` and `r:cs` used in a part, looked up in *that part's* `.rels` — is what finds it.
2. **The second pass is not well-formed XML.** Feeding office-open its own output through `parseDocument` → `generateDocument` yields a `word/document.xml` that fails to parse: `unbound prefix`, column 13606. The chart and SmartArt `<a:graphic>` elements are emitted bare, because the namespace is declared on an ancestor element that the regenerated tree does not reproduce. The second-pass score collapses from 93.5% to 32.2%. **This is invisible in a first-pass diff** — the file looks fine, opens in LibreOffice, and only breaks when the tool's own output is fed back in.
3. `w16du:dateUtc`, the `w14` run identifiers and the `w16du` namespace declaration are dropped, which is what a full regeneration does to markup it does not model.

We are not filing separate bug reports for these, because the trial already has a page for exactly this: https://github.com/arthrod/editors_trial/blob/main/reports/extras/officeopen.md and Report B §3.6. A pull request that fixes the relationship ids and the namespace rebinding would change both the fidelity table and the second-pass table, and we would update the reports in the same pull request.

## The reports, and what each one is

- **[Report A — Serialization by Namespace](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20A%20-%20Serialization%20by%20Namespace%20%282026%29.md)** — what each of the corpus's 27 namespace vocabularies does, and what it costs when it is lost. One section per namespace: what the vocabulary is in WordprocessingML, what each editor's own source does with it, and what each editor actually did to it, measured.
- **[Report A2 — Pass-Through](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20A2%20-%20Pass-Through%20%282026%29.md)** — the complement of fidelity: of the bytes that came out, how many did the editor never even look at. Pass-through is the strongest possible fidelity and the weakest possible editing, and it is the same fact.
- **[Report B — Malformed Parts, Causes, Detection and Repair](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20B%20-%20Malformed%20Parts%2C%20Causes%20and%20Repair%20%282026%29.md)** — twelve defect classes that Microsoft Word refuses to open, found by bisecting the corpus against Word itself; what malformed parts look like, what causes them, and whether any editor repairs them.
- **[Report C — Rendering Versus Word](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20C%20-%20Rendering%20Versus%20Word%20%282026%29.md)** — what each editor's own running application puts on the page, screenshotted and compared with Word's own PDF export of the same corpus. Fidelity in the file and fidelity on the page are two different results, and this report keeps them apart.
- **[Report D — Safety, Resource Bombs and Hostile Input](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20D%20-%20Safety%2C%20Resource%20Bombs%20and%20Hostile%20Input%20%282026%29.md)** — ten hostile packages — decompression, entry flood, attribute bomb, deep nesting, entities, zip-slip, external relationships, active content, layout bomb, corrupt parts — graded on a separate axis, because preserving a hostile payload is not the same result as a crash.

- **The per-tool note for office-open:** https://github.com/arthrod/editors_trial/blob/main/reports/extras/officeopen.md
- **What each measured tool is:** https://github.com/arthrod/editors_trial/blob/main/reports/vendors.md

## If anything here is wrong, please open a pull request

We would rather have a correction from you than a quiet disagreement. Three things are worth correcting, in this order of usefulness:

1. **A number.** Every figure in the reports is produced by `python3 build/score_all.py` over the committed outputs in `out/`, and it is checked against the scorer's own output by `build/check_report_consistency.py`, so a figure that cannot be reproduced fails the gate rather than slipping through. If one of ours is wrong, open a PR against the file that carries it — https://github.com/arthrod/editors_trial/blob/main/reports/extras/officeopen.md for the per-tool note, or the report that quotes it — and if the figure comes from the measurement rather than from prose, include the corrected `out/officeopen/score.json` too. `build/test_report_claims.py` enforces that the per-tool note still agrees with the shipped scorer, so it will tell you whether a correction is self-consistent.
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
python3 build/check_roundtrip.py fixture/complex.docx out/officeopen/complex.docx
bash build/run_second_pass.sh                    # the idempotence table
```
