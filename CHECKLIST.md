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
    - [x] warm/cold: C03, C05, C06 measured on both pairs (local, 2026-11-22). On Linux (Space test run, 2026-11-22) C05 and C06 refused `witness_sparse`: the edit's frame pulse needs a window corner outside the document, and react-docx's edit root fills the window, so frames came only every 383 ms. Fixed for react-docx only (2d19678: the pulse keeps clear of its pages); locally 8/8 measured after the fix, 16–30 ms
    - [x] input: C07 measured; C04 does not apply (no deferred work). C09 (undo) fails with `no_painted_frame`, and the failure is react-docx's own: one keystroke on a line in the lower half of the page scrolls the view by a page (0 → 1240 px headless, 0 → 1361 px in real Chrome), so the undone text is off-screen. Same on 0.15.0 (pinned) and 0.15.1 (latest). C08 (paste) fails as a knock-on: run alone it measures (22 ms), but in the lane it runs after C09, which leaves the view at the document's end, so its page-centre click lands below the last line. Left as failures, not dodged by choosing other click points; the attempts record the document region at y=111 at the click and y=−1240 at the undo
    - [x] document: C11 measured (≈240 ms, 3/3); C12 measured 2/3 (44, 46 ms), the third refused `anchor_identity_ambiguous` because the Enter+x never reached the document (paragraphs identical before and after); C15 does not apply (no find UI, as Plate). Needed `DOCUMENT_TARGETS`/`GATE_SURFACES` entries, selectors read in Chrome
    - [x] scroll: C10 measured 3/3 (16–18 ms) after the probe learned to look through a `display: contents` wrapper (react-docx wraps its document in one). The rule runs only when the scroller's own children give no box, so published editors keep their probe; test `perf/tests/test_e2_c10_display_contents.py`, red before, green after
    - [x] memory: C17 measured 2/3 (397, 506 MB), C19 measured (183 MB), C22 does not apply (no feature profile). The third C17 (after the edit burst) fails: the same scroll jump as C09 moves another paragraph under the caret point. It used to say "host accepted no text", which the evidence did not support; since 35d48f0 it fails `caret_block_moved` with the paragraph before and after in the record (Linux and local alike). Needed `FEATURE_SWITCH_PROBE` and lanes-registry entries; the CI-contract editor list is untouched (its seeded order would change for published editors)
    - [x] resources: measured
    - [x] typing: refused `text_mismatch`, and that is react-docx's: at full speed (cadence 0, the campaign's setting for every editor) it drops the first key after each Enter ("BBB" → "BB"); at 60 ms or more between keys nothing is lost. Needs Python Playwright 1.64.1 (`uv run --with playwright==1.64.1`), same as the container
  - [x] 8.1.2 BetterOffice (edits; its own layout engine): all seven. Same check. Local, 2026-11-22, prose-500w, @betteroffice/docx-react 0.5.1 (latest on npm); commits 978cde5 to 91e3fa5
    - [x] warm/cold: C03 221–224 ms warm, 351–376 ms cold; C05 71–95 ms; C06 70–86 ms; the whole text (4,220 characters, from its model) matches. 5,000 words: C03 520–712 ms. 50,000 words ran only under a profile that is not this machine's, so not publishable (C03 1.3–1.5 s)
    - [x] input: C04 74–89 ms; C07 25–28 ms, 3 of 3 points; C08 105–112 ms; C09 59–63 ms (undo restored the exact text). The last-line point (cut by the window's bottom edge) used to be refused `caret_not_on_clicked_line`: BetterOffice scrolls the clicked line into view (27 px) and C07 compared the caret with the line's box from before the click. Owner's decision (2026-11-22): C07 now judges the caret against where the clicked line ends up after the click's own scroll, for every editor (`caretOnClickedLine`; the shift is consulted only after the old comparison failed, and the published campaign has no such refusal in 3,144 C07 attempts, so no published figure moves; docxodus re-run unchanged, C07 12 ms)
    - [x] typing: 591 characters/s (throughput); latency session measured; the saved .docx matches
    - [x] document: C11 425–456 ms; C12 does not apply (pages are canvases); C15 find 241–276 ms, 3/3, through the package's own find dialog (re-run after the 60-frame fix, 3351374; before it most cells were refused `frame_interval_inconsistent`)
    - [x] scroll: C10 3–33 ms
    - [x] memory: C17 755–803 MB (3/3); C19 207 MB; C22 does not apply
    - [x] resources: measured (peak memory 812 MB, 32 MB fetched at load, edit verified)
  - [x] 8.1.3 OnlyOffice, CryptPad build (edits; draws on a canvas inside a frame): all seven, typing timed by pixels like Docen and WordCraft. Same check. Local, 2026-11-22, prose-500w (commits f1a2266 to ab3484c; warm/cold re-run after the rebase: C03 707/839 ms, C05 28/50 ms, C06 40/56 ms)
    - [x] warm/cold: C03 706–839 ms, C05 28–52 ms, C06 35–62 ms; the whole text (4,213 characters) matches. Also measured on 5,000 and 50,000 words (C03 755–995 ms)
    - [x] input: C07 46.5 ms, C08 37.2 ms, C09 34.8 ms; C04 does not apply (no deferred work)
    - [x] document: C11 806–824 ms; C15 find 409–428 ms through OnlyOffice's own find bar; C12 does not apply (whole pages drawn on one canvas: no paragraph box, as canvas-editor and Docen)
    - [x] scroll: measured from canvas pixels (owner's decision 2026-11-22; 9e085ed, merged in 79a4401). OnlyOffice's scrollbar is its own canvas widget, so no page element scrolls: one real wheel notch over the canvas (OnlyOffice steps 45 px per notch), timed from a wheel listener in its frame to the first presented frame matching the earlier picture moved up 44 px, with its caret div hidden. C10 13–46 ms (local, prose-500w, 6/6 over two runs); a repaint in place or a wheel that moves nothing is refused. Only OnlyOffice takes this path; OpenDoc's DOM control is unchanged
    - [x] typing: 450 chars/s (throughput); load 807 ms (latency). OnlyOffice's default autocorrect capitalised the first letter of a sentence ("PETITIONER v." became "V.") and failed the text check although every key arrived. Owner's decision (2026-11-22): sentence capitalisation off on the measured page (`asc_SetAutoCorrectFirstLetterOfSentences(false)`, published as `window.__host.autocorrect`), disclosed in Report E2
    - [x] memory: C17 779 MB ready, 839 MB after the edit burst; C19 223 MB; C22 does not apply
    - [x] resources: measured (load CPU 1,810 ms, peak memory 804 MB, edit verified)
    - [x] complex.docx: OnlyOffice's converter never returns (an altChunk); without the altChunk it converts in 125 ms but OnlyOffice refuses the file (error -82). Both are OnlyOffice's own
    - [x] container: setup skips OnlyOffice's fetched vendor trees and a dependency-free manifest; the three `missing_lockfile` tests pass
  - [x] 8.1.4 Nutrient (a viewer: converts to PDF): opening, scrolling and memory; typing, clicking, pasting and undoing print "does not apply". Same check on its lanes. Local, 2026-11-22, prose-500w (commit b3129be). Its page loads the viewer from Nutrient's CDN at the pinned 1.25.0 (installing the npm package means accepting Nutrient's evaluation agreement, which needs the owner's yes), so a cold open includes that download; the report must say so
    - [x] warm/cold: C03 measured on both pairs (1.4–2.0 s). C05/C06 are not in its target (no caret)
    - [x] document: C11 measured 3/3 (2.1–2.2 s); C12 "does not apply" (nothing to edit); C15 not measured: Nutrient has a search box (seen in Chrome), but it is in the viewer's shadow root, where the find probe cannot read the match count (and the 500-word fixture has no NEEDLE: no E2 editor has a C15 figure)
    - [x] scroll: C10 measured 3/3 (14–26 ms)
    - [x] memory: C17 measured 2/3 (608, 787 MB), the third "does not apply" (it types); C19 measured (204 MB); C22 does not apply (no feature profile)
    - [x] resources: measured (load and C17); its edit burst "does not apply" instead of refusing the cell
    - [x] input (C04, C07–C09) and typing (both sessions): "does not apply", with the reason, and the page is not started. A target's `viewer_not_applicable` drives this in the typing, input and resources lanes; only Nutrient sets it, and tests pin that every other editor is untouched
  - [x] 8.1.5 OpenDoc: the trial had no browser page for it (only `harness/ui/opendoc/fetch_engine.py`); one is built (`harness/ui/opendoc/host.mjs`, the pinned web app and engine, opens the document with no user action, ready flag once laid out and painted), then the same check. Local, 2026-11-22, prose-500w, commits e6966e6 to e12fa2e
    - [x] warm/cold: C03 239–396 ms; C05 32–57 ms; C06 31–60 ms
    - [x] input: C07 27 ms, C08 82 ms, C09 37–53 ms; C04 does not apply. (One earlier run's C08 missed its frame `no_painted_frame`; the later run measured)
    - [x] document: C11 357–360 ms; C12 does not apply (whole pages painted, no paragraph box); C15 find 151–178 ms, 3/3, through OpenDoc's own find bar
    - [x] scroll: C10 6–10 ms
    - [x] memory: C17 631–635 MB (3/3); C19 199 MB; C22 not run (no feature profile)
    - [x] resources: measured, edit burst verified
    - [x] typing: 138 chars/s (throughput); load 360 ms (latency). Same autocorrect as OnlyOffice ("v." became "V." at character 97); same owner's decision: OpenDoc's own preference `opendoc.autoCapitalise=off` set before it boots, published as `window.__host.autocorrect`, disclosed in Report E2
    - [x] C15 harness fix (commit 3351374): the find probe read the screen's frame interval over 6 frames, the rest of the harness over 60, so two good samples rarely carried the same interval and the cell was refused `frame_interval_inconsistent`. It now takes the same 60-frame reading. No published figure moves (no published editor has a C15 figure). Re-run after it: OpenDoc 3/3, BetterOffice 3/3 (241–276 ms), OnlyOffice 3/3 (420–431 ms)
  - [x] 8.1.6 Univer: no lane is possible. Its open-source packages cannot open a .docx (`harness/ui/univer/README.md`); Report E2 says so under "Not measured"
  - [x] 8.1.7 Container: the new pages install in `perf/container/setup.sh` (OnlyOffice's and OpenDoc's engines fetched, SHA-pinned; 307ade7) and run on a Space (arthrod/e2-publish, cpu-upgrade, `shared_guarded`). Two test runs, 2026-11-22, never publishable (`--shakedown 1`): run `20261122T161717258844Z-11876-654865` at 9b62c3f (one job of each of the seven lanes, 806 files verified) found two harness faults on Linux, both fixed: react-docx's C05/C06 `witness_sparse` (no frame pulse, 2d19678) and its after-edit memory row mislabelled "host accepted no text" (now `caret_block_moved`, 35d48f0). Run `20261122T170856603140Z-35279-167993` at 35d48f0 (warm/cold, scroll, memory; 1,332 files verified, exit 0): every opening and typing cell measured for all five; C10 measured for all five, OnlyOffice's by canvas pixels; memory as expected. Results are mirrored to the bucket every 5 minutes and duplicated and verified at the end (3c31d37). The Space is paused Review from another corpus (Codex, 2026-11-22, `.scratch/e2-later/review/codex-1.md`, 12 findings): ten fixed with tests red before and green after — C07 judges the caret only against the line's place after the click's own scroll and no longer counts window scrolling twice (24e3c1b); `caret_block_moved` only for a failed pair whose block really moved (a6c35dd); the checkpoint prunes build trees, never installs a torn copy, copies within 5 s of RUN-DONE after run.py exits, exits non-zero when unverified (273a484) and treats a zombie run.py as exited (e8e3281); the report's build refuses other seeds, lanes, machine types, unhashed documents or another micro-search generator, and its notes state OnlyOffice's 45 px C10 step and C07's change (4bb921b). #1 (throttle limit max(100 ms, 10%) is shared) pushed back: the published figures are carried, the later campaign runs only the new editors; under the old max(1 ms, 1%) the published campaign refused 4 of 9,061 samples for throttling (jobs 156, 157 resources; 097 document), so no rerun and no note beyond each section's printed limit; owner's decision, 2026-11-22. Third test run `20261122T181016191345Z-11874-522550` at 273a484 through `.scratch/e2-later/launch_one.sh` (restart, setup, job 22, pull FINAL-VERIFIED 96 files, bucket MANIFEST verified, Space paused) found the zombie run.py and a missing launcher dependency, both fixed.
  - [x] 8.1.8 Campaign: both seeds on Spaces of the same class as the published runs (`shared_guarded`, cpu-upgrade); `perf/container/e2_publication.json` names the runs. The new editors are planned as a campaign of their own (`--campaign later`, commit 1d36299): the published campaign's nine editors are frozen in `policy.E2_CAMPAIGN_EDITORS`, because wiring react-docx had silently grown its plan from 594 to 726 jobs and renumbered them
    - [x] Campaign `later`, blocks 2: 152/152 jobs on 15 Spaces (2026-11-22 to 23), every Space FINAL-VERIFIED, bucket duplicate verified and paused
    - [x] react-docx's C10 re-measured after the review found the content walk inside the timed window (owner's decision 2026-11-23): 20 jobs, react-docx only, on e2-plate and e2-publish; ticked when both Spaces are FINAL-VERIFIED and paused (2026-11-23: 20/20 jobs status=0; e2-plate FINAL-VERIFIED 398 files, paused 17:25 UTC; e2-publish FINAL-VERIFIED 398 files, paused 17:30 UTC; both bucket duplicates verified)
    - [x] OnlyOffice typing rerun (e2-plate, jobs 46, 47, 118, 119): 4/4 passed after hyphens-with-dash off (owner's decision, disclosed)
    - [x] BetterOffice typing rerun (e2-superdoc, jobs 48, 49, 120, 121): all 4 passed; FINAL-VERIFIED (196 files), bucket duplicate verified, Space paused 2026-11-23 07:58 UTC
    - [x] OpenDoc typing rerun (e2-genoffice, jobs 50, 51, 122, 123): all 4 done (both sessions of each over the hour, the rest not tried); FINAL-VERIFIED (112 files), bucket duplicate verified, Space paused 2026-11-23 09:24 UTC. Each session hits the one-hour budget kept for every editor, so the report says "did not finish within the hour" with the words typed
  - [ ] 8.1.9 Report: the new tools' figures in their own section of Report E2 (a later campaign, like Report E's), facts built by the same rule; gate passes twice; released and seen live
    - [x] Re-measured cells may carry their own editor pin, disclosed with both pins and the reason (owner's decision 2026-11-23; f2f59f2)
    - [x] The later section keeps its results in the report part; its method, runs and full tables move to Appendix K (eeba0dc)
    - [x] Disclosed in Appendix K: OnlyOffice capitalisation and hyphens-with-dash off; OpenDoc automatic lists and replace-as-you-type off; Nutrient's CDN; C07 judged after the click's own scroll; OnlyOffice's C10 pixel probe
    - [x] `later` entry added to `out/report_e2_runs.json`, facts rebuilt with the carry, report re-rendered (2026-11-23; outside `perf.e2.later.*` only `ver.cdn.nutrient` differs from v0.12.0's facts)
    - [x] Read back in full: a viewer's cells say "does not apply" (f781b87, afe31b2); react-docx's mismatch cells say so; jobs replaced whole by reruns are not counted (152 jobs, 76 per seed: 622f231, 72a433c); Space note says "this campaign" (83234c3)
    - [x] Vendor notes and Report C §2.19 cite the later figures; react-docx's "not measured" and Nutrient's "in no other" gone (bfbc8b9; Codex checked every figure)
    - [x] `verify_publication.sh --with-word` passes twice (2026-11-23, on e2/review-fixes 105a625: 8/8 both times, Word opened every deliverable; an earlier pair that ran on main by mistake is void, see RERUNS). Again after Gitar's review fixes: 8/8 on 5326618 and on 89809ff (CHANGELOG lines only), Word opened every deliverable
    - [x] Gitar's 7 review comments (#283-#286): 5 fixed (47c84bf typing brief compared by SHA-256; 62622dd; 0d9bb76; 3aaeab9; 273a484), 1 fixed with the marker pushed back, 1 pushed back; each answered in its thread
    - [x] CodeRabbit's 20 and CodeAnt's 9 comments (#283, #285) gated one by one, each answered; any that touches a recorded figure goes to the owner before merging (2026-11-23: 16 fixed with a test red before and green after, 7894c6c..9e5e314; 7 pushed back; 6 duplicates linked; 29/29 replied. Only CodeAnt's C10 walk moved a figure: owner chose fix and re-measure)
    - [x] react-docx's C10 re-measured with the walk outside the timed window (all five documents x 2 seeds, react-docx only; jobs 032-041 and 104-113 on e2-plate and e2-publish since 16:20 UTC), old cells superseded and disclosed in Appendix K and the CHANGELOG (7cac484: 20/20 jobs, both spaces FINAL-VERIFIED; 250,000 words 116.8 -> 61.5 ms, 50,000 words 26.8 -> 21.9 ms, complex 17.9 ms -> under one frame)
    - [ ] CodeRabbit's re-review of #287 (14 comments), its #283 follow-ups (2) and Sonar's 2 findings gated one by one, each answered (2026-11-23: 12 fixed with a test red before and green after, f6a7688..3eb4977; 1 pushed back with the seed medians (OpenDoc 500 words, 12.4 and 17.7 ms); Sonar: 1 hardened, 1 pushed back; three new test modules converted to pytest, 825c219; ledger 14 = 13 fixed + 1 pushed back, 2/2 #283 follow-ups fixed, 2/2 Sonar answered). None moved a published figure; Report E2's later memory table marks Nutrient's and react-docx's readings "(no typing before it)"
    - [ ] `verify_publication.sh --with-word` passes twice again after the #287 re-review fixes
    - [ ] Stacked PRs, release, deploy, seen live in Chrome
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
| 2026-11-22 | 8.1 | BetterOffice, OnlyOffice and OpenDoc (page built) wired and measured locally; C15 frame-interval fix; three owner decisions open (autocorrect in typing, OnlyOffice scroll, C07 click into a scrolled line) |
| 2026-11-21 | 10.3 | The four tools that had no page on editors.benchmarks.law have one; their cards show the figures |
| 2026-11-22 | 1.7, 1.8, 2.4, 3.4, 5.5, 5.6 | et-v0.11.2: the source of react-docx, OpenDoc and BetterOffice read; rankings, master table, boundaries, architectures and Report C sections written |
| 2026-11-22 | 7, 8 | Closed by the owner's decision: no cloud machines, so the new tools stay untimed |
| 2026-11-22 | 10.3 | The four demo-build tools and docen's 500 pages timed on the rented machine; every card with browser figures from that machine is now scored |
| 2026-11-22 | 7, 8 | Reopened: the owner approved rented machines for Reports E and E2 too, which supersedes the no-cloud decision above. Report E's runs for OpenDoc, BetterOffice and OnlyOffice started on the same machine type |
| 2026-11-22 | 7 | Report E measured for OpenDoc, BetterOffice and OnlyOffice on the rented machine (the two runs took 16 minutes; the machine was rented for about 22); E2 still needs browser lanes for the new tools |
| 2026-11-23 | 9, 10; open-docs 3.7, 3.8 | Re-checked live in Chrome: 20 card About links land on vendor-notes headings; 28 "Use X" summaries; speed, data and memory grades shown; `lane-docxodus` 301 to its section; blog burger menu opens at 400 px; post footers chain parts 1 to 5 in order |
| 2026-11-23 | open-docs-viewer 1.6, 1.7, 1.10 | Re-checked live in Chrome: `/r/opendoc` and `/r/betteroffice` render the rich sample page by page; the viewers home page has no "not built" left; 9 of its 10 tables list both engines |
