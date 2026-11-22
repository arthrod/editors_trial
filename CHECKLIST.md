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

- [x] 7.1 to 7.7 Measured (v0.12.0): OpenDoc, BetterOffice and OnlyOffice timed on 2026-11-22 on the same machine type as the published runs (Amazon EC2 r6a.8xlarge via Hugging Face), primary run `6842e10ab266` (30 repetitions) and reproduction `986d98556538` (10), same documents; 51 of 51 figures reproduced. Report E gives them their own section; OnlyOffice does not return from `complex.docx` (harness stop at 120 s, three in a row in each run). react-docx and Apryse have no headless entry and stay under "Not measured"
- [x] 7.8 LibreOffice, Exceptions, Not measured (names the four new tools and the reason), How it was measured, Appendices

## 8. Report E2: speed in the browser

- [ ] 8.1 Approved for measuring (2026-11-22), not yet measured: the seven action tables have no row for the new tools, and the report says so at the top. Branch `e2/new-editor-lanes`. What each tool can be timed on, from its page in `harness/ui/`:
  - [x] 8.1.1 react-docx (edits; DOM, one contenteditable per paragraph): all seven actions. Every lane gives its result locally; the two refusals (C09/C08, typing) are react-docx's own behaviour, recorded with the evidence below, not dodged. Lane wired: browser target, pin, caret and whole-text surfaces. Check: the warm/cold, input, typing, document, scroll and memory lanes each measure a cell on the 500-word document locally (`python3 -m perf.runner.<lane> … --editors reactdocx`), no content refusal
    - [x] warm/cold: C03, C05, C06 measured on both pairs (local, 2026-11-22)
    - [x] input: C07 measured; C04 does not apply (no deferred work). C09 (undo) fails with `no_painted_frame`, and the failure is react-docx's own: one keystroke on a line in the lower half of the page scrolls the view by a page (0 → 1240 px headless, 0 → 1361 px in real Chrome), so the undone text is off-screen. Same on 0.15.0 (pinned) and 0.15.1 (latest). C08 (paste) fails as a knock-on: run alone it measures (22 ms), but in the lane it runs after C09, which leaves the view at the document's end, so its page-centre click lands below the last line. Left as failures, not dodged by choosing other click points; the attempts record the document region at y=111 at the click and y=−1240 at the undo
    - [x] document: C11 measured (≈240 ms, 3/3); C12 measured 2/3 (44, 46 ms), the third refused `anchor_identity_ambiguous` because the Enter+x never reached the document (paragraphs identical before and after); C15 does not apply (no find UI, as Plate). Needed `DOCUMENT_TARGETS`/`GATE_SURFACES` entries, selectors read in Chrome
    - [x] scroll: C10 measured 3/3 (16–18 ms) after the probe learned to look through a `display: contents` wrapper (react-docx wraps its document in one). The rule runs only when the scroller's own children give no box, so published editors keep their probe; test `perf/tests/test_e2_c10_display_contents.py`, red before, green after
    - [x] memory: C17 measured 2/3 (397, 506 MB), C19 measured (183 MB), C22 does not apply (no feature profile). The third C17 refused "host accepted no text": the same scroll jump as C09 moves another paragraph under the caret point. Needed `FEATURE_SWITCH_PROBE` and lanes-registry entries; the CI-contract editor list is untouched (its seeded order would change for published editors)
    - [x] resources: measured
    - [x] typing: refused `text_mismatch`, and that is react-docx's: at full speed (cadence 0, the campaign's setting for every editor) it drops the first key after each Enter ("BBB" → "BB"); at 60 ms or more between keys nothing is lost. Needs Python Playwright 1.64.1 (`uv run --with playwright==1.64.1`), same as the container
  - [ ] 8.1.2 BetterOffice (edits; its own layout engine): all seven. Same check
  - [ ] 8.1.3 OnlyOffice, CryptPad build (edits; draws on a canvas inside a frame): all seven, typing timed by pixels like Docen and WordCraft. Same check
  - [x] 8.1.4 Nutrient (a viewer: converts to PDF): opening, scrolling and memory; typing, clicking, pasting and undoing print "does not apply". Same check on its lanes. Local, 2026-11-22, prose-500w (commit b3129be). Its page loads the viewer from Nutrient's CDN at the pinned 1.25.0 (installing the npm package means accepting Nutrient's evaluation agreement, which needs the owner's yes), so a cold open includes that download; the report must say so
    - [x] warm/cold: C03 measured on both pairs (1.4–2.0 s). C05/C06 are not in its target (no caret)
    - [x] document: C11 measured 3/3 (2.1–2.2 s); C12 "does not apply" (nothing to edit); C15 not measured: Nutrient has a search box (seen in Chrome), but it is in the viewer's shadow root, where the find probe cannot read the match count (and the 500-word fixture has no NEEDLE: no E2 editor has a C15 figure)
    - [x] scroll: C10 measured 3/3 (14–26 ms)
    - [x] memory: C17 measured 2/3 (608, 787 MB), the third "does not apply" (it types); C19 measured (204 MB); C22 does not apply (no feature profile)
    - [x] resources: measured (load and C17); its edit burst "does not apply" instead of refusing the cell
    - [x] input (C04, C07–C09) and typing (both sessions): "does not apply", with the reason, and the page is not started. A target's `viewer_not_applicable` drives this in the typing, input and resources lanes; only Nutrient sets it, and tests pin that every other editor is untouched
  - [ ] 8.1.5 OpenDoc: the trial has no browser page for it yet (only `harness/ui/opendoc/fetch_engine.py`); build one from its published package, then the same check
  - [x] 8.1.6 Univer: no lane is possible. Its open-source packages cannot open a .docx (`harness/ui/univer/README.md`); Report E2 says so under "Not measured"
  - [ ] 8.1.7 Container: the new pages install in `perf/container/setup.sh` and pass `run.sh --smoke` on a Space
  - [ ] 8.1.8 Campaign: both seeds on Spaces of the same class as the published runs (`shared_guarded`, cpu-upgrade); `perf/container/e2_publication.json` names the runs. The new editors are planned as a campaign of their own (`--campaign later`, commit 1d36299): the published campaign's nine editors are frozen in `policy.E2_CAMPAIGN_EDITORS`, because wiring react-docx had silently grown its plan from 594 to 726 jobs and renumbered them
  - [ ] 8.1.9 Report: the new tools' figures in their own section of Report E2 (a later campaign, like Report E's), facts built by the same rule; gate passes twice; released and seen live
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
| 2026-11-22 | 8.1 | react-docx and Nutrient wired into every E2 lane and measured locally; the published campaign's job plan frozen (later editors get `--campaign later`) |
| 2026-11-21 | 10.3 | The four tools that had no page on editors.benchmarks.law have one; their cards show the figures |
| 2026-11-22 | 1.7, 1.8, 2.4, 3.4, 5.5, 5.6 | et-v0.11.2: the source of react-docx, OpenDoc and BetterOffice read; rankings, master table, boundaries, architectures and Report C sections written |
| 2026-11-22 | 7, 8 | Closed by the owner's decision: no cloud machines, so the new tools stay untimed |
| 2026-11-22 | 10.3 | The four demo-build tools and docen's 500 pages timed on the rented machine; every card with browser figures from that machine is now scored |
| 2026-11-22 | 7, 8 | Reopened: the owner approved rented machines for Reports E and E2 too, which supersedes the no-cloud decision above. Report E's runs for OpenDoc, BetterOffice and OnlyOffice started on the same machine type |
| 2026-11-22 | 7 | Report E measured for OpenDoc, BetterOffice and OnlyOffice on the rented machine (the two runs took 16 minutes; the machine was rented for about 22); E2 still needs browser lanes for the new tools |
