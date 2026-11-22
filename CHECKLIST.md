# Reports checklist: benchmarks.law/editors-trial (editors_trial)

Every report of the trial, with its parts. Tick a part only when it has been
re-rendered from measurements **and** seen on benchmarks.law. The same file
exists in `open-docs`, `open-docs-viewer` and `editors-arena`.

Legend: `[x]` done and checked live · `[~]` in progress · `[ ]` not done ·
`[!]` blocked, with the reason beside it.

## The field

Measured since v0.11.0 (16 and a baseline): SuperDoc, Folio, GenOffice, eigenpal,
office-open, Docen, WordCraft, Fidus Writer, Plate.js, docs.plus,
canvas-editor, Docxodus, Apryse WebViewer, react-docx, OpenDoc, BetterOffice;
LibreOffice as the baseline.

The six tools that came from editors.benchmarks.law, as of et-v0.11.0 (2026-11-21):

| Tool | In the reports as | What the trial found about its .docx path |
| --- | --- | --- |
| react-docx | a round-trip participant | reads and writes; Word opens its output |
| OpenDoc | a round-trip participant | reads and writes; Word refuses its output |
| BetterOffice | a round-trip participant, two lanes | reads and writes; Word refuses the model lane's output and opens the editor session's |
| OnlyOffice (CryptPad build) | run, with no output | its converter did not return from the test document, twice |
| Univer | probed, no lane | no .docx reader or writer in its 16 open-source packages |
| Nutrient (commercial, view-only) | Report C only | a viewer: it saves no .docx |

A report is complete only when each of these has a row, or the report says,
from a measurement or a source citation, why it has none. Where a part below is
`[~]` or `[!]`, the reason beside it is what is still owed. The code of react-docx,
OpenDoc and BetterOffice was read for v0.11.2; that of OnlyOffice's build, Univer
and Nutrient was not read for any report.

## 1. Main report: round trip

- [x] 1.1 TL;DR (the fixed-point count names all seven; live 2026-11-21)
- [x] 1.2 Method and its limits (a paragraph at the top says what v0.11.0 added, and that the new tools' code was read in v0.11.2 and at which commits)
- [x] 1.3 The corpus (unchanged)
- [x] 1.4 Harnesses: one row per new lane, with the call each was driven through
- [x] 1.5 Measured results: scorecard and second-pass rows for react-docx, OpenDoc, BetterOffice; OnlyOffice's row says no output
- [x] 1.6 Word compatibility of the corpus (unchanged; the verdicts on the new outputs are in §12 and in Report B)
- [x] 1.7 Executive summary: rankings. react-docx, OpenDoc and BetterOffice are ranked (places 7, 9, 10) since v0.11.2, when their code was read
- [x] 1.8 Master comparison table: a row each for react-docx, OpenDoc and BetterOffice (v0.11.2)
- [x] 1.9 Preserved-vs-dropped matrix (generated; three new columns)
- [x] 1.10 Per-repository findings: §12 covers the four new tools and the Univer probe
- [x] 1.11 Changes from the previous report (CHANGELOG 0.11.0)
- [x] 1.12 Recommendations, Caveats, Reproducing this (unchanged)

## 2. Report A: serialization by namespace

- [x] 2.1 TL;DR · [x] 2.2 Method · [x] 2.3 Namespace inventory
- [x] 2.4 Where each editor's serialization boundary is: §3.13 react-docx, §3.14 OpenDoc, §3.15 BetterOffice (v0.11.2). The matrix of §6 has no column for them, and the report says so
- [x] 2.5 Measured namespace survival (generated tables with three new columns; §4.6)
- [x] 2.6 Consequences, namespace by namespace (§4.6 says where a new output breaks an earlier count)
- [x] 2.7 The cross-editor matrix
- [x] 2.8 What this means, Reproducing, Gaps

## 3. Report A2: pass-through

- [x] 3.1 TL;DR · [x] 3.2 Method · [x] 3.3 Package-level map (generated; new columns)
- [x] 3.4 Architectures that produce pass-through: §3.7 for the three tools (v0.11.2)
- [x] 3.5 What pass-through gives, and the failure modes it hides (BetterOffice's dropped SmartArt pointer is in §5.6)
- [x] 3.6 Per-editor pass-through: §6.10 for the four new lanes
- [x] 3.7 What this means, Reproducing, Gaps

## 4. Report B: malformed parts

- [x] 4.1 TL;DR · [x] 4.2 Method · [x] 4.3 The corpus's own malformation
- [x] 4.4 The editors' own malformations: §3.9 for the new tools
- [x] 4.5 Does any editor repair malformed input? §4.5, cell by cell for the new outputs
- [x] 4.6 Causes, detector catalogue, corrections, Reproducing

## 5. Report C: rendering versus Word

- [x] 5.1 TL;DR · [x] 5.2 Method
- [x] 5.3 The editors, one at a time: §2.15 react-docx, §2.16 OpenDoc, §2.17 BetterOffice, §2.18 OnlyOffice, §2.19 Nutrient, each with figures (OnlyOffice has none: it showed no document)
- [x] 5.4 Construct-by-construct table (generated; new columns)
- [x] 5.5 In the DOCX but not rendered: §4.2 (e) for the three tools, counted in their outputs and explained from the code (v0.11.2)
- [x] 5.6 The SmartArt: §5.9 says what each of the three draws in the band and, for BetterOffice, why. The band was not measured in pixels for them, and the section says so
- [x] 5.7 The quantitative layer: pixels (rows for the new outputs; the note on Word's unstable pixel column)
- [x] 5.8 What this means, Reproducing, Gaps

## 6. Report D: hostile input

- [x] 6.1 TL;DR · [x] 6.2 Grades (one per lane; five new)
- [x] 6.3 Unsandboxed refusal · [x] 6.4 Sandboxed matrix · [x] 6.5 Protection degrees
- [x] 6.6 Measured scorecard · [x] 6.7 Protection record (generated; 210 cells)
- [x] 6.8 Where the safety word is the wrong name, Kept payloads (unchanged; not re-read against the new rows)
- [x] 6.9 Google Docs and Word rows (never re-tested; stay as measured)
- [x] 6.10 Report D1, Jubarte (unchanged)
- [x] 6.11 Report D2, Word (unchanged)

## 7. Report E: speed without a browser

- [x] 7.1 to 7.7 Decided, not measured: the new tools are not timed. OpenDoc, BetterOffice and OnlyOffice have lanes that could be, but the figures are taken on rented cloud machines and the owner chose not to rent any (2026-11-21, confirmed 2026-11-22). Report E says so in its section "Not measured in this report"
- [x] 7.8 LibreOffice, Exceptions, Not measured (names the four new tools and the reason), How it was measured, Appendices

## 8. Report E2: speed in the browser

- [x] 8.1 Decided, not measured: the seven action tables have no row for the new tools, for the same reason as Report E. The report says so at the top
- [x] 8.2 What the figures can and cannot tell

## 9. Notes

- [x] 9.1 `reports/vendors.md` is the one place a vendor is described (benchmarks.law/editors-trial/vendor-notes). Released in et-v0.10.6 and seen live 2026-11-21: 20 sections
  - [x] Each vendor's lane note is folded into its vendor section; each file in `reports/extras/` is a one-line pointer to it
  - [x] The new vendors are added: react-docx, Univer, OpenDoc, BetterOffice, OnlyOffice, Nutrient (their trial figures follow the new lanes, sections 1 to 6 above)
  - [x] Each vendor section ends with **Pros** and **Cons** in plain language, drawn from every report and from the three benchmark sites (20 of each, live)
- [x] 9.2 Rendering openability (names the two new refused outputs; live 2026-11-21)

## 10. The field page (benchmarks.law/editors-trial/vendors, in `benchmarks-law`)

Live since 2026-11-21 (site PRs 97 and 99), each line checked on the deployed page.

- [x] 10.1 One card per tool, new editors included: 19 cards and the LibreOffice baseline
- [x] 10.2 Each card's summary says what the tool is good for, in the reader's terms ("Use X for Y"), not a list of scores
- [x] 10.3 Each card shows grades for speed, data transferred and memory, beside round trip and hostile input, with the rule that produces each grade printed on the page. Tools not on editors.benchmarks.law, and readings from another machine, are left unscored with the reason. GenOffice, office-open, Fidus Writer and docs.plus were put on editors.benchmarks.law on 2026-11-21 through this repository's demo builds and measured on a Mac; on 2026-11-22 the owner approved the rented machine, they were timed there (same machine type and Chrome build as the pass), and all three of their axes are scored. docen's 500 pages were timed there the same day, so docen is scored on all three too (arthrod/open-docs#95, #97; arthrod/open-docs-viewer#42; arthrod/benchmarks-law#109)
- [x] 10.4 "About" on each card goes to that vendor's section of `/editors-trial/vendor-notes` (all 19 land on a heading)
- [x] 10.5 The old `/editors-trial/lane-<editor>` addresses redirect to the vendor's section (301, fragment kept)
- [x] 10.6 The index page counts and names match the field

## Log

| Date | Part | What changed |
| --- | --- | --- |
| 2026-11-21 | all | Checklist created |
| 2026-11-21 | 9.1, 10 | Vendor notes rewritten and the field page rebuilt, both in branches awaiting a release |
| 2026-11-21 | 9.1, 10 | Released (et-v0.10.6) and deployed; checked on the live pages |
| 2026-11-21 | 1 to 9 | et-v0.11.0: four tools join the round trip, five join Report C; live on benchmarks.law and checked in Chrome |
| 2026-11-21 | 7, 8 | Blocked: the new tools are not timed (no cloud machines rented) |
| 2026-11-21 | 10.3 | The four tools that had no page on editors.benchmarks.law have one; their cards show the figures |
| 2026-11-22 | 1.7, 1.8, 2.4, 3.4, 5.5, 5.6 | et-v0.11.2: the source of react-docx, OpenDoc and BetterOffice read; rankings, master table, boundaries, architectures and Report C sections written |
| 2026-11-22 | 7, 8 | Closed by the owner's decision: no cloud machines, so the new tools stay untimed |
| 2026-11-22 | 10.3 | The four demo-build tools and docen's 500 pages timed on the rented machine; every card with browser figures from that machine is now scored |
