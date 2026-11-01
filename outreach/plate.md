We measured Plate.js together with eleven other open-source DOCX tools and published the whole thing — the corpus, the harnesses, the scorer, the logs and the reports — so that every number below can be checked and corrected.

**Everything is here: https://github.com/arthrod/editors_trial**

## What the trial is

One input: `fixture/complex.docx`, a 35-part hand-built OOXML document that deliberately contains tracked changes, complex and simple fields, five content controls, tables with merges and nested tables, three sections including a landscape two-column one, a bar chart, a SmartArt diagram, an OLE object with an embedded workbook, an image, footnotes, endnotes, comments, headers and footers, and a set of namespace extensions Word writes.

Every editor was driven through **its own** documented import and export path — Plate.js's own entry point, not a re-implementation of it — and the result was scored by a 99-check diff at package-part, element, attribute and text level. Every output was re-opened to confirm it is still a valid document. The scorer, the harnesses, the fixture and the raw logs are in the repository.

## What we measured for Plate.js

**20.6% weighted, 20.7% critical (6/29), 20/99 checks, 91.7% text retention, 11/35 parts kept — 79 failed checks.**

Plate.js scores last in the trial, and it is the **only editor in the trial that reports what it lost.** That is worth more than the score, and we would like to be explicit about it.

- **38 typed diagnostics** name each dropped construct — 19 `unsupported-content`, 6 `converter-message`, 2 `resource-omitted`, 8 `property-dropped`, 2 `lossy-content` and 1 `source-unavailable`. No other editor in this trial says anything at all.
- **The default `lossPolicy: 'reject'` refuses a document it cannot represent losslessly.** Handed the corpus, the import fails with 18 typed errors and **writes no output file at all**. There is nothing to corrupt.
- **It is the only editor that detects malformation and refuses it.** Given a corpus carrying all twelve defect classes, Plate fails with `decode-failed` and produces nothing. The other eleven editors read the malformed file and produced output; Plate is the one that declined to process it.
- **The closed "passive vocabulary"** (`internal/sourceEligibility.ts`) decides whether an unchanged document may be exported byte-exactly. That is a genuinely careful piece of design, and it is the reason a low score is not a careless score.

**What the score itself reflects** is the pipeline's shape rather than a defect: DOCX → HTML → editor model → static HTML → DOCX. Every revision is flattened, every field is dropped, every content control is unwrapped, and 24 of the 35 parts go with them. What survives is the text — **91.7%, the second-highest in the trial** — plus the table grid, `gridSpan`, `vMerge`, nested tables, cell shading, bookmarks, `w:vertAlign` and `xml:space="preserve"`.

**On the hostile-input axis, Plate has the strongest ceiling set of any participant** (Report D): named ceilings on the decompression bomb, the entry flood and the deep nest; the attribute bomb **cleaned**; the external-relationship bomb **cleaned** — that is the SSRF and credential vector, and cleaning it is a real result; and the entity bomb, the zip-slip, the active-content package and the corrupt-parts package refused.

Two numbers we would particularly like checked, because they are ours and not yours:

- **The breakdown of the 38 diagnostics.** We counted 19 `unsupported-content`, 6 `converter-message`, 2 `resource-omitted`, 8 `property-dropped`, 2 `lossy-content` and 1 `source-unavailable`. If that enumeration is wrong, the per-tool note is wrong, and we would rather fix it than publish it.
- **The second pass.** The package shrinks from 42,964 to **8,010** bytes as the retained source is replaced by a regenerated one. That is the sharpest second-pass change in the trial, and it is a consequence of the passive-vocabulary gate rather than of a defect.

## The reports, and what each one is

- **[Report A — Serialization by Namespace](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20A%20-%20Serialization%20by%20Namespace%20%282026%29.md)** — what each of the corpus's 27 namespace vocabularies does, and what it costs when it is lost. One section per namespace: what the vocabulary is in WordprocessingML, what each editor's own source does with it, and what each editor actually did to it, measured.
- **[Report A2 — Pass-Through](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20A2%20-%20Pass-Through%20%282026%29.md)** — the complement of fidelity: of the bytes that came out, how many did the editor never even look at. Pass-through is the strongest possible fidelity and the weakest possible editing, and it is the same fact.
- **[Report B — Malformed Parts, Causes, Detection and Repair](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20B%20-%20Malformed%20Parts%2C%20Causes%20and%20Repair%20%282026%29.md)** — twelve defect classes that Microsoft Word refuses to open, found by bisecting the corpus against Word itself; what malformed parts look like, what causes them, and whether any editor repairs them.
- **[Report C — Rendering Versus Word](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20C%20-%20Rendering%20Versus%20Word%20%282026%29.md)** — what each editor's own running application puts on the page, screenshotted and compared with Word's own PDF export of the same corpus. Fidelity in the file and fidelity on the page are two different results, and this report keeps them apart.
- **[Report D — Safety, Resource Bombs and Hostile Input](https://github.com/arthrod/editors_trial/blob/main/reports/Report%20D%20-%20Safety%2C%20Resource%20Bombs%20and%20Hostile%20Input%20%282026%29.md)** — ten hostile packages — decompression, entry flood, attribute bomb, deep nesting, entities, zip-slip, external relationships, active content, layout bomb, corrupt parts — graded on a separate axis, because preserving a hostile payload is not the same result as a crash.

- **The per-tool note for Plate.js:** https://github.com/arthrod/editors_trial/blob/main/reports/extras/plate.md
- **What each measured tool is:** https://github.com/arthrod/editors_trial/blob/main/reports/vendors.md

## If anything here is wrong, please open a pull request

We would rather have a correction from you than a quiet disagreement. Three things are worth correcting, in this order of usefulness:

1. **A number.** Every figure in the reports is produced by `python3 build/score_all.py` over the committed outputs in `out/`, and it is checked against the scorer's own output by `build/check_report_consistency.py`, so a figure that cannot be reproduced fails the gate rather than slipping through. If one of ours is wrong, open a PR against the file that carries it — https://github.com/arthrod/editors_trial/blob/main/reports/extras/plate.md for the per-tool note, or the report that quotes it — and if the figure comes from the measurement rather than from prose, include the corrected `out/plate/score.json` too. `build/test_report_claims.py` enforces that the per-tool note still agrees with the shipped scorer, so it will tell you whether a correction is self-consistent.
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
python3 build/check_roundtrip.py fixture/complex.docx out/plate/complex.docx
bash build/run_second_pass.sh                    # the idempotence table
```
