# Reports checklist: benchmarks.law/editors-trial (editors_trial)

Every report of the trial, with its parts. Tick a part only when it has been
re-rendered from measurements **and** seen on benchmarks.law. The same file
exists in `open-docs`, `open-docs-viewer` and `editors-arena`.

Legend: `[x]` done and checked live · `[~]` in progress · `[ ]` not done ·
`[!]` blocked, with the reason beside it.

## The field

Measured before v0.11.0 (13 and a baseline): SuperDoc, Folio, GenOffice, eigenpal,
office-open, Docen, WordCraft, Fidus Writer, Plate.js, docs.plus,
canvas-editor, Docxodus, Apryse WebViewer; LibreOffice as the baseline.

Added to the reports in v0.11.0 (2026-11-21), with the following measurement scope; their source was not reviewed:

| Editor | Package | Has a .docx import and export of its own? |
| --- | --- | --- |
| react-docx | `@extend-ai/react-docx` | yes, measured in Chromium |
| Univer | `@univerjs/presets` + `preset-docs-core` | no: its .docx path is not in the open-source packages |
| OpenDoc | `opendoc` engine; `@casualoffice/opendoc-viewer` for UI | yes, measured through `Document::open` and `Document::save` |
| BetterOffice | `@betteroffice/docx`, `@betteroffice/docx-react` | yes, document-model and unedited editor-session lanes |
| OnlyOffice (CryptPad build) | `cryptpad/onlyoffice-editor`, `onlyoffice-x2t-wasm` | through x2t; no output from either corpus within 120 seconds |
| Nutrient (commercial, view-only) | its Web SDK | view-only: rendering reports only |

Reports E and E2 retain the earlier timing campaign; these tools were not timed. Report C’s hand-written construct tables were not extended. Publication here does not mark the live-site checks below complete.

A report is complete only when each of these has a row, or the report says,
from a measurement or a source citation, why it has none.

## 1. Main report: round trip

- [ ] 1.1 TL;DR
- [ ] 1.2 Method and its limits
- [ ] 1.3 The corpus
- [ ] 1.4 Harnesses: the exact code path each project was driven through (one entry per editor, new editors included)
- [ ] 1.5 Measured results (scores, critical features, text retention, parts kept)
- [ ] 1.6 Word compatibility of the corpus (Word opens every output)
- [ ] 1.7 Executive summary: rankings
- [ ] 1.8 Master comparison table
- [ ] 1.9 Preserved-vs-dropped matrix
- [ ] 1.10 Per-repository findings (one section per editor)
- [ ] 1.11 Changes from the previous report
- [ ] 1.12 Recommendations, Caveats, Reproducing this

## 2. Report A: serialization by namespace

- [ ] 2.1 TL;DR · [ ] 2.2 Method · [ ] 2.3 Namespace inventory
- [ ] 2.4 Where each editor's serialization boundary is (one per editor)
- [ ] 2.5 Measured namespace survival
- [ ] 2.6 Consequences, namespace by namespace
- [ ] 2.7 The cross-editor matrix
- [ ] 2.8 What this means, Reproducing, Gaps

## 3. Report A2: pass-through

- [ ] 3.1 TL;DR · [ ] 3.2 Method · [ ] 3.3 Package-level map
- [ ] 3.4 Architectures that produce pass-through
- [ ] 3.5 What pass-through gives, and the failure modes it hides
- [ ] 3.6 Per-editor pass-through (one per editor)
- [ ] 3.7 What this means, Reproducing, Gaps

## 4. Report B: malformed parts

- [ ] 4.1 TL;DR · [ ] 4.2 Method · [ ] 4.3 The corpus's own malformation
- [ ] 4.4 The editors' own malformations (one per editor)
- [ ] 4.5 Does any editor repair malformed input?
- [ ] 4.6 Causes, detector catalogue, corrections, Reproducing

## 5. Report C: rendering versus Word

- [ ] 5.1 TL;DR · [ ] 5.2 Method
- [ ] 5.3 The editors, one at a time (one section per editor, new editors and Nutrient included)
- [ ] 5.4 Construct-by-construct table
- [ ] 5.5 In the DOCX but not rendered
- [ ] 5.6 The SmartArt
- [ ] 5.7 The quantitative layer: pixels
- [ ] 5.8 What this means, Reproducing, Gaps

## 6. Report D: hostile input

- [ ] 6.1 TL;DR · [ ] 6.2 Grades (one per editor)
- [ ] 6.3 Unsandboxed refusal · [ ] 6.4 Sandboxed matrix · [ ] 6.5 Protection degrees
- [ ] 6.6 Measured scorecard · [ ] 6.7 Protection record
- [ ] 6.8 Where the safety word is the wrong name, Kept payloads
- [ ] 6.9 Google Docs and Word rows (never re-tested; stay as measured)
- [ ] 6.10 Report D1, Jubarte (unchanged unless the packages change)
- [ ] 6.11 Report D2, Word (unchanged)

## 7. Report E: speed without a browser

- [ ] 7.1 TL;DR · [ ] 7.2 What was timed · [ ] 7.3 Documents
- [ ] 7.4 Round trip · [ ] 7.5 Load · [ ] 7.6 Save
- [ ] 7.7 Process cost at 50,000 words
- [ ] 7.8 LibreOffice, Exceptions, Not measured, How it was measured, Appendices

## 8. Report E2: speed in the browser

- [ ] 8.1 The seven action tables (open, type, click, paste, undo, scroll, resources), one row per editor
- [ ] 8.2 What the figures can and cannot tell

## 9. Notes

- [x] 9.1 `reports/vendors.md` is the one place a vendor is described (benchmarks.law/editors-trial/vendor-notes). Released in et-v0.10.6 and seen live 2026-11-21: 20 sections
  - [x] Each vendor's lane note is folded into its vendor section; each file in `reports/extras/` is a one-line pointer to it
  - [x] The new vendors are added: react-docx, Univer, OpenDoc, BetterOffice, OnlyOffice, Nutrient (their trial figures follow the new lanes, sections 1 to 6 above)
  - [x] Each vendor section ends with **Pros** and **Cons** in plain language, drawn from every report and from the three benchmark sites (20 of each, live)
- [ ] 9.2 Rendering openability

## 10. The field page (benchmarks.law/editors-trial/vendors, in `benchmarks-law`)

Live since 2026-11-21 (site PRs 97 and 99), each line checked on the deployed page.

- [x] 10.1 One card per tool, new editors included: 19 cards and the LibreOffice baseline
- [x] 10.2 Each card's summary says what the tool is good for, in the reader's terms ("Use X for Y"), not a list of scores
- [x] 10.3 Each card shows grades for speed, data transferred and memory, beside round trip and hostile input, with the rule that produces each grade printed on the page. Tools not on editors.benchmarks.law, and readings from another machine, are left unscored with the reason
- [x] 10.4 "About" on each card goes to that vendor's section of `/editors-trial/vendor-notes` (all 19 land on a heading)
- [x] 10.5 The old `/editors-trial/lane-<editor>` addresses redirect to the vendor's section (301, fragment kept)
- [x] 10.6 The index page counts and names match the field

## Log

| Date | Part | What changed |
| --- | --- | --- |
| 2026-11-21 | all | Checklist created |
| 2026-11-21 | 9.1, 10 | Vendor notes rewritten and the field page rebuilt, both in branches awaiting a release |
| 2026-11-21 | 9.1, 10 | Released (et-v0.10.6) and deployed; checked on the live pages |
