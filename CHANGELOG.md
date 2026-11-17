# Changelog

Every release of the editors trial is a measurement: the editor commits it
pins, the fixture it feeds them, the scorer that reads their output, and the
reports written from that output. A release never changes a figure without
re-running the measurement behind it. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/) with the trial still pre-1.0.

## [Unreleased]

## [0.10.4] - 2026-11-17

Report E2 times typing in canvas-editor, Docen and WordCraft, the three
editors that draw their text on a canvas. Their 60 typing cells had no
figure; 55 now have one.

### Updated

- No editor pin moved, for the reason given under 0.10.1: the jobs are
  measured again at the pins of 0.10.0, so that the only thing that changed
  between a cell and the cell it replaces is how the harness ends a typing
  time.

### Measured

- **Typing in canvas-editor, Docen and WordCraft** (#245, #238). The
  harness ended a typing time at the frame in which the typed character's
  own outline showed ink, and these editors draw text where it cannot read
  an outline. For them it now uses a settled-pixel witness: it records
  every frame after the key press, takes the picture the caret's line has
  once it is quiet, leaves out what blinks and the caret's own columns, and
  ends the time at the first frame that shows that whole change. A time is
  printed only when the editor also confirms the edit. The report marks
  these times "(by pixels)".
- **The round.** The 20 warm and cold load jobs (500 to 250,000 words and
  the complex document, both seeds) were measured again for those three
  editors on ten Spaces, at harness `377b6320`: 3,360 key presses, 3,359
  measured, one refused (canvas-editor, a late anchor frame).
  `perf/container/e2_publication.json` records it as a witness round
  (`witness_superseded`, `witness_rerun`); the tables read the new jobs for
  those editors and no earlier measurement of them in those jobs, so their
  load figures in that lane are from this round too.
- **What changed.** Report E2 counts 798 of its cells as reproduced
  between the two seeds, where it counted 739. The 59 are 55 typing cells
  (canvas-editor 16, Docen 20, WordCraft 19) and 4 of WordCraft's load
  cells at 500 and 50,000 words. No cell went the other way. Every new
  figure is the agreement of two seeds measured on different Spaces; that
  agreement is the reproduction of each changed cell.
- **The figures**, typing one character, at 500, 5,000, 50,000 and 250,000
  words: canvas-editor 68 ms, 351 ms, 3.0 s, 16.5 s; Docen 45 ms, 76 ms,
  452 ms, 7.3 s; WordCraft 128 ms, 135 ms, 157 ms, 238 ms.
- **Still without a figure.** canvas-editor's page does not finish opening
  the complex document in this lane, so its 4 typing cells there stay
  empty. WordCraft's single-key time on a cold launch at 50,000 words did
  not reproduce (178 ms and 158 ms) and is printed as such.
- **Smallest change read.** On the prose documents the smallest change
  behind a time is 29 pixels (the typed character between the caret's
  columns) for canvas-editor and Docen and 498 for WordCraft. On the
  complex document WordCraft's is 17 pixels, one above the floor of 16;
  the full tables print it beside each cell.
- **Host load.** One of the 20 jobs (complex document, second seed, second
  block) had 4 of its 15 launches begin or end above the bound; the
  report's host-load table names it. Of all 6,676 launches of the report's
  runs, 310 were above the bound, where 291 of 6,376 had been.
- **Before the round**, a traced trial run (no part of the figures) read
  the new witness beside the glyph witness on the six editors that allow
  both: 368 of 384 key presses ended on the same frame. The 16 that
  differed were Folio's first key of a burst; frames show the glyph
  witness ends that key late, on the frame where the caret is drawn again
  inside the character's outline (#253, not yet corrected; Report E2,
  Appendix D).

### Added

- `perf/runner/pixel_settle.mjs`, the settled-pixel witness, and its
  schema, harness and reader checks: the change must reach a floor (16
  pixels where the editor reports its caret's place, 100 where it does
  not), touch the caret, and go quiet; a late edit is waited out; the
  reader re-checks every sample (#245, #248).
- In a trial run only, a shadow reading of the pixel witness for editors
  that have glyph outlines, so the two witnesses can be compared.
- The probe waits for its own mark to leave the screen before it takes a
  baseline picture and records whether it did (#247).
- The roots builder knows a witness round: some editors' cells of a lane's
  jobs measured again after every other round. A witness-round job must
  record every criterion the cells it replaces recorded (#252).
- `build/e2_witness_trial.py` reads that trial comparison from the trial's
  samples into `perf/container/e2_witness_trial.json`, and the report
  prints its sentence from the record. The draft of this release had the
  counts typed into the template, and wrong (292 of 304, from a partial
  read); CodeRabbit's review of #255 asked for them to be generated.
- A contract test that the clock record the probe writes and the schema
  the harness validates hold the same keys, compared both ways, and tests
  that put recorded probe output through the harness's own validation
  (#250, #251).

### Fixed

- **The round's first launch measured nothing, and that was our error.**
  A field was added to the probe's clock record after the trial run, the
  schema refused it, and every sample of the first launch (harness
  `5afe3ea6`) was refused as `witness_schema_invalid`. The launch was
  stopped, the field removed and the contract test
  above added (#250). The manifest does not name that launch's runs, and no
  figure comes from them.
- Docen keeps its focused input where the page was clicked until a key is
  pressed; on the complex document the witness band was aimed at the
  click and missed the caret's line. The band now follows the caret to
  the line it moved to (#251).
- The ">= 100 pixels" rule first proposed for these editors counted the
  harness's own mark in the corner of the screen; it was withdrawn before
  any figure used it (#247).
- The release gate's check of Report E2's Appendix J looks for a refused
  round's reason in that round's own clause, so two rounds that recorded
  different reasons cannot be swapped unnoticed; and the test of a host
  round older than a first-pass job now fails without that comparison
  (#241). No figure and no sentence of a report changes.

### Not re-measured

- Every other editor, lane and report. The six editors with glyph
  outlines keep their typing figures of 0.10.3, taken with the glyph
  witness; their facts gained two descriptive fields and no value changed.
- Folio's burst-typing figure is not corrected for #253.
- Search and replace is still not measured for any editor.

## [0.10.3] - 2026-11-16

Report E2's four busy-host jobs are measured again on a quiet host, and its
results tables stop printing three labels that hid what was measured:
"varied", "does not apply" for a refusal of our own tooling, and "under 1
frame".

### Updated

- No editor pin moved, for the reason given under 0.10.1: the four jobs are
  measured again at the pins of 0.10.0, so that the only thing that changed
  between a job and the job it replaces is the load on the host.

### Measured

- **Four warm and cold load jobs, every editor, on a quiet host** (#228).
  Jobs 4 and 5 (50,000 words, first seed) and jobs 83 (5,000 words) and 86
  (250,000 words, second seed) first ran while the host's one-minute load
  was above the bound the harness holds a quiet machine to for most of
  their launches. They ran again behind the host-load guard of 0.10.2's
  harness (`71162e7d`): 180 launches, none waited, none started above the
  bound. `perf/container/e2_publication.json` records them as a host round
  (`host_superseded`, `host_rerun`); the tables read the four new jobs and
  no earlier measurement of them.
- **What changed.** Report E2 counts 739 of its 1,061 cells as reproduced
  between the two seeds, where it counted 693. 47 cells that had not
  reproduced now do, most of them at 50,000 words, where the whole first
  seed was measured again; one went the other way (eigenpal's cold load at
  5,000 words). A cell reproduces when a seed measured on the quiet host
  agrees with the other seed, measured days earlier on another Space; that
  agreement is the reproduction of each changed cell.
- The re-measured rounds read lower than the ones they replace, by up to a
  third on the smallest typing figures. No cell that had no figure gained
  one: GenOffice completed 3 of 5 launches at 250,000 words where it had
  completed none, which is still too few for its typing cells there, and
  SuperDoc's three failed launches at 50,000 words did not recur.
- The results tables now hold 6 cells printed as a range, where the same
  tables read from 0.10.2's runs would hold 13.
- After the round, 64 of the lane's 980 launches began or ended above the
  bound, where 221 of 1,000 had.

### Changed

- **"varied" is now the range the two rounds gave** (#239), for example
  "56 ms to 77 ms". Both rounds had a figure in every such cell.
- **"under 1 frame" is now "under 17 ms"**: the screen was redrawn every
  16.7 ms, and the harness cannot time an answer shorter than one redraw.
- **"does not apply" is kept for what truly does not apply**: an editor
  with nothing deferred to measure, or without the feature. Where our
  tooling refused its own sample the cell says "not measured". Typing in
  canvas-editor, Docen and WordCraft is the case that prompted this: the
  harness checks a typed character against the outline of its glyph, those
  editors draw text where it cannot read one, and the 12 cells had printed
  "does not apply".
- The full tables print the reason recorded with each refused cell beside
  the refusal code.

### Added

- **Appendix J**: one row for every results cell that is not a single
  figure, with what each round gave and why. For the typing cells that were
  not measured it prints the times the harness recorded for the first
  change on screen after each key press, as evidence and not as a figure.
- **Host load, launch by launch**, in the machine appendix: for each job
  the load at each launch and how many launches were above the bound.
- The release gate's independent check of the results tables fails on a
  bare "varied", on "does not apply" for a refusal of the tooling, on
  "under 1 frame", and on an Appendix J row that does not match the data.
- The roots builder knows a host round: a few jobs measured again for
  every editor because of the host, not the harness, so the rest of the
  lane stays as measured.

### Not re-measured

- Everything but those four jobs. The other jobs in which a quarter or
  more of the launches were above the bound are named in the report's
  host-load table and stay as measured.
- Typing in canvas-editor, Docen and WordCraft is still not measured
  (#238): it needs a witness read from the screen's pixels and a new run.


## [0.10.2] - 2026-11-15

Report E2's settling column becomes a rate. No measurement was taken for
this release: every figure comes from the runs of 0.10.0.

### Updated

- No editor pin moved, for the reason given under 0.10.1: this release
  changes how the 0.10.0 measurements are read.

### Measured

- Nothing new. The facts are rebuilt from the same runs. Report E2 now
  counts 693 of its 1,061 cells as reproduced between the two seeds, where
  it counted 701: the cells are the same, but 32 settling totals had
  agreed and 24 settling rates do.

### Changed

- **B8, "CPU settling after the edit" is now "CPU per second while
  settling"** (#226). The wait it covers ends at the first half-second poll
  at which two seconds have passed without a long task; in these runs it
  the readings taken during it spanned 0.1 s to 5.6 s, and the column was a
  total over them. Each launch's processor time is now divided by the span
  from its first to its last such reading, read from the samples already
  in each launch's record. A launch counts when that span is a second or
  more, and a seed needs five such launches.
  Of the 44 cells: 24 give a rate, 4 did not reproduce (Docen at 50,000 and
  250,000 words, GenOffice and SuperDoc at 250,000), 11 had a wait too
  short to measure, 5 are WordCraft's, which never went idle. As totals,
  32 of the 39 that are not WordCraft's had printed a figure and 7 had not
  reproduced. The rate is an average over the span, working and quiet time
  together (the two quiet seconds that end the wait can begin before the
  first reading, so a span holds some of them, not always all), and it
  still depends on how long the span ran. The totals stay in
  `out/facts.json`; a settling cell is counted once in the report's
  count of cells, as the rate.
- One function builds a cell's fact key for the tables and the short
  version (CodeRabbit's #230, applied here).

### Not re-measured

- Everything. The busy-host jobs of #228 are still disclosed, not measured
  again.

## [0.10.1] - 2026-11-15

Report E2 gets a short version a person can read, and its resources tables
stop hiding what a cell that did not reproduce read. No measurement was
taken for this release: every figure comes from the runs of 0.10.0.

### Updated

- No editor pin moved. This release changes how the 0.10.0 measurements are
  presented, at Arthur's request of 2026-11-15; moving a pin would require
  every measurement again (AGENTS.md section 2). The update rule of
  section 1 resumes with the next measured release.

### Measured

- Nothing new. The raw runs were pulled back from the bucket
  (`arthrod/editors-trial-e2-runs`) and the facts rebuilt from them: every
  fact of 0.10.0 is unchanged except the two B8 texts below, and 595 facts
  are added (the short version's figures, and each B8 cell's seed medians
  and launch range).

### Not re-measured

- Everything. In particular the four warm/cold jobs that ran while their
  host was busy (#228) and the B8 settling column (#226) are disclosed, not
  measured again: that needs a Space.

### Added

- **`build/verify_e2_summary.py`** (#227, from CodeRabbit's plan): an
  independent check of Report E2's results tables. The generator writes its
  figures into `out/facts.json`, which the number gate reads, so a wrong
  figure would have matched itself. The check shares no code with the
  generator, recomputes every cell and range sentence from the two rounds'
  cell facts, and runs in the gate's "generated" step.
- **Report E2 is a report first and a reference second.** It now opens with
  what the report is, how to read the tables, what the figures cannot tell
  you, and the results; everything else is in lettered appendices (A: what
  was measured; B: the machine; C: the rule, and that every measurement was
  run twice; D: notes and what was measured again; E: the full tables; F to
  I: not measured, cells that did not agree, how to run it again, DOCX
  verification). No figure changes.
- **Report E2, "The short version"** (#227). One small table per question a
  reader asks (opening a document, typing a character, placing the caret,
  pasting, undoing, scrolling, memory with the document open), editors in
  alphabetical order, one column per document size. A figure is the middle
  of the two seeds' medians of a cell that reproduced; a cell without one
  says why in a word (varied, crashed, does not apply, no figure). Nothing
  is ranked. The reference tables follow it unchanged.
- **B8: a cell that did not reproduce says what it read** (#226): both seed
  medians and the lowest and highest launch. canvas-editor's memory at
  50,000 words, printed as "not reproduced", is 3,427.5 to 5,137.1 MiB
  across its launches. Only a reproduced pair is stored as a result.
- **B8: where a never-idle editor's processor time went** (#226). In the
  30-second wait after opening, WordCraft's CPU is the browser's GPU
  process drawing in software on a host with no graphics processor, at every
  document size; the note gives the split, the long tasks and the range of
  its memory readings.
- **B8: a note on the settling window** (#226). It is not a fixed length,
  and the first seed's median is the higher one in 27 of the 39 cells with
  a settling figure and the lower in 4.

### Fixed

- **The gate's Word-open step could not fail** (#231, found through
  CodeRabbit's plan on #204): `build/verify_deliverables.py` printed
  "SOME DELIVERABLE FAILED" and exited 0, and skipped a deliverable Word
  gave no verdict for. It now exits 1 for a missing file, a missing verdict
  or any verdict other than OPENED. The kept gate logs of 0.10.0 and of this
  release show every deliverable OPENED, so no release passed wrongly.

### Found, not fixed

- **An audit of every published speed cell** (#228). Report E (headless) is
  clean: every cell reproduced and neither run is systematically the slower.
  In Report E2, 65 cells failed only because the two seed medians differ;
  the samples of 55 of them could be read back, and 44 of those are the warm/cold lane (C03, C05, C06) at three document
  sizes, and follow the host's recorded load (up to 66.0 on the busy jobs),
  not the editors. The harness records the load and does not refuse on it.
- **Five live demos did not load their document** (#225): the bundle's demo
  folders held only the entry chunks. Rebuilt whole at the pinned commits
  for the bundle of this release (docxodus, Fidus Writer, GenOffice, Plate,
  SuperDoc). Two more showed their document but were missing files and were
  rebuilt too: Folio (its 178 font files) and Docen (two lazy chunks).
  `build/verify_demo.py` opens a built demo in a browser and fails on any
  missing file; all twelve were checked with it. Not fixed: the docs.plus
  demo asks for the fixture's one image at a path its host page never
  stores (a 404; the text is shown).

## [0.10.0] - 2026-11-15

Two new speed reports: Report E (headless opening and saving) and Report E2
(speed in the browser). No figure of Reports A to D2 or of the main report
changes.

### Updated

- No editor pin moved. Arthur decided on 2026-11-11 that this release keeps
  the pins the browser campaign was built and measured on, so the speed
  figures and the round-trip figures describe the same editor code. The
  update rule of AGENTS.md section 1 resumes with the next release.

### Measured

- **Report E2, speed in the browser** (#128, #140). Nine browser editors
  (Plate, Docxodus, SuperDoc, GenOffice, eigenpal, Folio, canvas-editor,
  Docen, WordCraft) in Playwright Chromium 156.0.8078.80, in Linux
  containers on Hugging Face Spaces (CPU upgrade hardware: AMD EPYC 7R13,
  8 CPUs of quota), 2026-11-12 to 2026-11-15. The tables read 212 jobs
  (106 per seed) from 52 run folders, run in interleaved blocks of 5
  repetitions; each cell schedules 10 samples per editor per seed and
  publishes at 5 kept (Arthur, 2026-11-11, #163). 701 of 1,061 scheduled
  editor/criterion/measure cells reproduced between the two seeds within
  10 percent; the others are listed with their reason in the report's
  "Not reproduced" section. Steal time under 0.01 percent; the report's
  host note gives the samples refused for cgroup CPU throttling and the
  host's load average per seed (#209).
- **The document lane and the input lane were measured again for every
  editor** (the lane round, #208; harness `03b683b1`; 52 jobs on 20 Spaces,
  15 November), after an audit of the first tables found two harness bugs
  that both seeds reproduced:
  - #206: the probe's search for a document's opening headings grew with
    the square of the page and ran inside the timed load of C11 and C14.
    First seed / second seed, before and after: Plate.js C11 at 250,000
    words 796 s / 770 s, now 19.7 s / 18.5 s, and at 50,000 words 17.3 s /
    17.2 s, now 4.7 s / 4.6 s; Docxodus C11 at 250,000 words 203 s / 198 s,
    now 47.2 s / 45.4 s; Docxodus C14 at 500,000 words 413 s / 419 s, now
    99.4 s / 98.9 s; Plate.js C14 at 250,000 words 359 s / 335 s, now
    18.4 s / 18.2 s. The other editors' load figures moved by a few
    percent. What the probe's text read still costs inside a load is
    recorded per sample and stated in the report.
  - #207: C08, and WordCraft's C09, ended at a frame in which only the
    editor's own caret had changed. With a floor of 100 changed pixels:
    WordCraft C08 at 500 words 7 ms / 9 ms, now 136 ms / 126 ms;
    canvas-editor 15 ms / 16 ms, now 93 ms / 95 ms; SuperDoc 48 ms /
    47 ms, now 121 ms / 116 ms; Folio at 250,000 words 26 ms / 27 ms, now
    425 ms / 401 ms. SuperDoc's and canvas-editor's paste at 250,000 words
    no longer has a figure: within the 2-second window only the caret
    changed (SuperDoc had printed 421 ms / 400 ms).
  The earlier rounds of those lanes (#173–#175, #181, #183–#185, #190,
  #193, #196, #202, #203) are history: the lane round replaced them, and
  the report's "Re-run jobs" paragraph names each.
- 32 first-pass jobs (job indexes 10–21, 28–31, 90–101 and 108–111) were
  measured again after the harness defects #173, #174 and #175 were fixed;
  the tables read the re-run jobs, and `perf/container/e2_publication.json`
  names every run and every replaced job. Every job of both passes is
  sealed and kept in the private dataset `arthrod/editors-trial-e2-publication`
  (52,090 attempts from 420 sealed jobs of every round; 27,412 of them are
  read by the report, and each row says so).
- Resource figures withheld because they were not what their column said
  (#211; reader and template only, nothing re-measured): WordCraft's three
  B8 CPU columns read "never idle" (its "CPU to open" of 81 s for a
  500-word document was the 30-second settle cap; up to its ready signal it
  uses 6 to 8 s); "Peak memory" is "Highest memory reading"; the C17 ready
  cells of Docxodus, Folio, GenOffice, SuperDoc and WordCraft read
  "unverified" (the document was not checked as loaded at that reading);
  the C19 table is removed (the reading was the browser's own baseline, 318
  to 363 MiB for every editor and size).

- **Report E, speed: opening and saving a document** (#111). The headless
  speed runner (`perf/runner/speed_headless.py`, runner commit `a7b243d`),
  `dedicated_publish`, in a Linux container on a Hugging Face sandbox
  (Amazon EC2 r6a.8xlarge, AMD EPYC 7R13, 32 CPUs), on 2026-11-09:
  primary run `2471956e80e7` (30 repetitions, seed 20261109, 19:25–20:41
  UTC) and reproduction run `62769027c2c2` (10 repetitions, seed 20261110,
  20:41–21:12 UTC). Twelve editors plus LibreOffice's whole conversion, on
  the 500, 5,000, 50,000 and 250,000-word prose documents and
  `complex.docx`. 211 of 211 published figures reproduced within 10 percent
  (or 2 ms). Steal time under 0.01 percent in both runs; no sample started
  above the load limit.
- canvas-editor fails both runs at 250,000 words and on `complex.docx`,
  three runs in a row each time (the discarded warm-up and the first two
  samples), after which the runner stopped the cell. At 250,000 words the save exhausts
  Node's default JavaScript heap. Two diagnostic reruns outside the runs:
  in Vitest's forks pool with the default heap, V8 stopped the save with
  "JavaScript heap out of memory" (heap full at 4,092 MB); in a worker
  thread, as in the runs, with a 16 GB heap, the same sample loaded, saved,
  and its file passed the runner's own content check. `complex.docx` is the
  `w:vMerge` import crash the main report already describes. No lane raises
  the heap.
- SuperDoc's save stays at 8–13 ms from 500 to 250,000 words. A probe
  outside the runs found the file complete (final size, ZIP end record,
  same hash two seconds later) when `doc.save` resolves, so the save clock
  is not cut short. Where SuperDoc does the export work was not traced; the
  report states the flat save as an observation, not a cause.

### Not re-measured

- The release gate (`build/verify_publication.sh --with-word`) passed
  twice, all eight checks, at commit 0cff2dfc. The review that followed
  changed only the two checker scripts, their tests and this file. The
  raw run data had by then been removed from the measuring machine (it
  is in the run bucket), so at the released commit the gate was run twice
  without its facts rebuild step: the other checks, including Word, read
  the facts the two full passes had rebuilt, byte for byte.
- Reports A to D2 and the main report: no pin moved and nothing they read
  changed, so their facts are those `main` last tracked (identical to the
  published et-v0.9.5 facts); the Markdown of every one of them renders
  byte-identical. Their Word twins were rebuilt, as every release does.
  Report E's browser criteria (C03, C05–C12, C14, C15) and the memory
  lanes (C17, C19) are measured in Report E2, not in Report E; the
  WebAssembly boundary (C24, #117) is measured in neither.
- Report E2 does not measure Apryse (its licence key is never placed on
  the measuring machines), docs.plus and Fidus (their application servers
  were not started; Arthur, 2026-11-11), office-open (a library with no
  editing surface) or LibreOffice (the conversion baseline of Report E).
  The report lists each with its reason.
- Seven unit tests
  (`test_every_lane`, `test_ns_tables`, `test_report_claims`) read outputs
  of Reports A to D that #87 deleted from the repository (#204). This
  release did not re-produce those outputs (no pin moved), so it restored
  the missing files from `et-v0.9.5`, overwriting nothing, and the seven
  pass against them. Every Report E and E2 test passes.

### Added

- `reports/Report E2 - Speed in the Browser (2026).md` and its DOCX twin
  (#140), rendered from `templates/` and `out/facts.json`; registered in
  `render_reports.TWINS` and `verify_deliverables.DELIVERABLES`
  (`build/test_report_e2_registration.py`). A "Read this before the
  tables" section states how each editor's edit is confirmed, the typing
  tolerance, the criteria that do not apply, and the Chrome traces.
- `perf/container/`: the Linux container recipe (Playwright Chromium) and
  the Space runner for the browser lanes (#127), detached runs with
  per-job manifests sealed and uploaded to a private Storage Bucket through
  a Space volume mount, with no token in the Space (#144, #162, #164).
- `perf/container/e2_publication.json` and `build/e2_publication_roots.py`:
  the campaign manifest and the tool that turns it into the report's run
  folders, replacing every superseded first-pass job with its re-run (#178).
- Browser-lane criteria C03–C15, C17 and C19 (#104–#110, #113, #115), the
  resource lanes B8 (#142) and the typing marathon B9 (#143), with frame
  witnesses, throttle and steal accounting (#129), and a reader that pools
  each seed's jobs across run folders (#136, #176).
- A 500,000-word rung (`prose-500kw`, #188) on the load lanes only: C11,
  C12 and C15 in the document lane and C14's rung list, with a 1,000 s
  load timeout. Eight new jobs (160–167) appended after the campaign's
  own: the four C14 jobs (162, 163, 166, 167) at harness `d697b98e`, the
  four document jobs (160, 161, 164, 165) at `6885707b`, after the fixes
  of #193 and #195 (`harness.extension` names both); the other lanes are
  not measured at that size.
- `reports/Report E - Speed, Opening and Saving a Document (2026).md` and
  its DOCX twin, rendered from `templates/` and `out/facts.json`;
  registered in `render_reports.TWINS` and `verify_deliverables.DELIVERABLES`
  (`build/test_report_e_registration.py`).
- `perf/`: the performance harness (#91). One schema and outcome set for
  every trial (`measured`, `unsupported`, `not_applicable`, `unverified`,
  `failed`, `not_run`), a 24-scenario catalog (C01–C24) across the `native`,
  `model`, `browser_visible`, and `wasm_boundary` layers, deterministic
  workload fixtures with a size ladder and Unicode/emoji/bidi/IME correctness
  fixtures, execution profiles (`ci_contract`, `ci_broad`,
  `dedicated_publish`), per-lane capability records, summary statistics with
  uncertainty, a publication policy that keeps CI from publishing visible
  latency, and immutable raw trials under `perf/out/`. Runners today:
  `benchmark_ci_contract.py` (headless C02 model load, C16 save, C21 child
  CPU), `benchmark_warm_cold.py` (browser C02/C03/C05/C06 warm-vs-cold on the
  `harness/ui` hosts), and `adversarial_c10_scroll.py` (C10 scroll). Design
  and coverage matrix in `docs/superpowers/specs/`; unit tests in
  `perf/tests/`; documentation in `perf/README.md`.
- Documentation (#92): the README Fidelity section now describes the
  round-trip pipeline end to end — fixture, first and second pass, scoring,
  facts, and report rendering — with what a run needs; `perf/README.md`
  gained the runner-level details (PERF marks, wall/CPU companion samples,
  the 600 s harness timeout).

### Changed
- `RELEASING.md` §7: publishing the bundle is one command, `bench publish editors_trial et-vX.Y.Z`
  (bench-ops plan 6, editors_trial#74; first used for et-v0.9.4, #75), and the site picks the
  release up with `bench bump editors_trial`. No figure changes.

### Fixed

- The release gate was not run for 0.9.4 or 0.9.5 (their changelogs say
  so), and two of its checks failed on things 0.9.3 brought in (#215). The findings check looked the
  Apryse scorecard row up by a name without its version, missed it, and so
  never checked Apryse's figures; it finds the row now and its five figures
  agree with the scorer. The number gate could not find Report C's A/B
  byte deltas, because the measurement holds the two sizes and not their
  difference; it now does the subtraction `build/ab_table.py` does.
  codex's review of these fixes then showed the number gate accepted a
  figure that was only the tail of a longer one; figures now have to
  occur whole, and a section number
  ("4.2 Bytes versus content") is no longer read as a size. No report
  figure failed the stricter check.
  The same gate also read its own last output as evidence: it is called
  with a relative path, its exclusion list is absolute, and nothing was
  ever excluded, so a figure it refused once was accepted on the next run.
  With that closed it refused three figures in older text, none in a
  report: the 0.9.0 entry below gave WordCraft one point less than the
  scorer and the report of 0.9.0 did, which is 85.9% (corrected); the
  README used the same wrong figure in an example (reworded); and the
  0.9.0 entry quotes a figure it corrects (0.0006%), now listed as a
  quotation.
- CodeRabbit's review of the release (#218). One sentence of Report E2
  was wrong after the lane round: it still gave GenOffice at 500,000 words
  as an example of a painted frame minutes after the text, and of a C14
  cell that is the time the text appeared; its C11 is now a few seconds
  and that C14 cell is not published. The example is gone. Three limits of
  the harness that bear on a printed figure are now stated in the report
  and filed for the next campaign (#221): where C04's clock starts, a C14
  no-damage sample when more than 1,200 frames arrived, and the canvas
  hash that the probe-scan share leaves out. Four manifests the roots
  builder should refuse are filed as #222; none is true of this
  release's manifest. Tooling findings are #220.
- In Report E2 the two typing latency tables (eigenpal, GenOffice) had no
  blank line before them, so the Word twin showed them as text (#214).
- `build/test_bombs.py` compared this machine's operating-system version
  with the one quoted in Report D and failed after a system update; only
  the version is set aside now (#213).
- The probe's heading scan is linear in the page and the tick that stamps
  the usable moment no longer builds the document text (#206); C08 and
  WordCraft's C09 need a frame with at least 100 changed pixels (#207).
  Both reviewed by codex (gpt-6-astra), whose findings (a nested page that
  was still quadratic, a `:scope` selector, the scan time of a tick that
  found no text) are tests.
- The publication manifest and its roots builder know a lane round: a
  whole lane measured again for every editor, each job checked against the
  seed, block, editors and criteria of the jobs it replaces (#208). A job
  still measuring counts as unsealed.
- Report E2 prints memory in MiB, states the host load, and says what C03,
  C17 and B8 are (#209, #211).
- Known and open: `pull.py` leaves a file the Space removed after it was
  pulled, which blocks the final check of that run (#212); no measurement
  is affected.

- Browser harness, before Report E2 was published: a frame witness that
  proves the edit and not only a repaint, refused samples that are never
  kept, and blocked cells that never reach the facts (#130–#139, #146,
  #148, #149, #151, #154, #155, #165–#171). Reviewed by models other than
  the one that wrote the code (codex and glm-5.3 among them); every accepted
  finding is fixed with a test.
- Three defects found in the first pass, fixed and their jobs re-run
  (#173–#175): Docxodus's input probe was killed at 300 s because the C09
  reset clicked the editor mode before the page rendered; Docen's C14 was
  refused everywhere because a full-element screenshot was compared with
  viewport-clamped frames; C12 refused "unaccounted layout reads" because a
  frame's own read was stamped outside its window.
- Report E2's reader (#176–#179): it reads each JSON file once instead
  of about 334 times, so the campaign's facts build in about ten minutes; Chrome-profile
  diagnostic launches are no longer labelled `crash`; the header describes
  the 40-folder campaign instead of naming one primary and one
  reproduction run, and lists every editor's pins from every folder; and
  warm/cold's stand-in `not_run` rows for C07–C10, C22 and C23 no longer
  pool with the lanes that measure those criteria. That last fix lifts the
  cells that reproduce from 408 to 551 with no published cell lost and
  identical figures for every cell published before.
- B8 and B9 in the campaign (#180). The resources tables were blocked for
  every editor because each 5-launch job carried its own pair verdict
  ("scheduled_below_10; second_seed_required"), which the reader now
  re-checks on the pooled seed instead; a resources launch the runner
  refused for CPU throttling (a sample row, no record) counts as a refusal,
  not a missing file. The typing tables pooled every job of a run folder
  into each cell ("n = 6 of 292"); a typing cell now reads only the typing
  jobs of its editor and session kind.
- C14's text check (#181). Every C14 cell of the campaign was withheld as
  "I01: combining mark or non-BMP scalar not preserved in output": the
  probe kept only the first 4,000 characters of the document text, and the
  correctness lines sit at the end of each prose document. The probe now
  also keeps the last 4,000 characters and the check reads both. A failed
  check now names its cause: the complex document carries no correctness
  lines, so the check does not apply to it; an editor that exposes no text,
  or whose readable text stops before the closing paragraph, is withheld as
  "not checkable". The four C14 jobs (20, 21, 100, 101) were measured again
  in a second round.
- C14 reads each editor's whole text, and waits 1,000 s per load (#183,
  #184). The second round still withheld Folio and SuperDoc from 5,000
  words up, and WordCraft at every prose size. Their pages hold only part
  of a long document: Folio and SuperDoc mount only the pages near its
  start, and WordCraft paints into a canvas. After the timed sample, and
  outside it, the probe now asks each of them for the whole document:
  SuperDoc through its document model, Folio through its editing
  ProseMirror, and WordCraft through its own select-all and copy. On each
  real editor, typing on a near-empty document and typing after a DOCX
  import both show in the next read. C14's probe target carried no
  workload id, so the 600 s rule for the 250,000-word document never
  reached it: every rung waited 300 s, and the 330 s watchdog cut Plate's
  load. C14 now gives each wait of a load up to 1,000 s, and its watchdog
  outlasts every wait. A C14 sample also logs its stages (navigation,
  ready, surface, witness, text read), so a timeout names the stage it
  stopped in. The four C14 jobs were measured a third time; the tables
  read the third round, and the superseded rounds stay in the dataset.
- canvas-editor's C11 and C14 timed its empty page (#185). The
  `canvas_pixel` signal took the first frame with any ink on the canvas,
  and canvas-editor paints its empty page's margin marks before the
  document is imported: about 130 ms at every size, while the import of
  the 250,000-word document took 51 s. canvas-editor also reports the
  import finished one or two frames before it paints, and at some sizes it
  clears the page first. The usable frame is now the first one in which
  canvas-editor reports the document imported and its first page shows ink
  that differs from its empty page. Its cells of the 24 document jobs
  (C11, C12, C14, C15) were measured again by canvas-editor-only runs
  under the same job indices, seeds and blocks; the publication manifest's
  editor-scoped round (`editor_superseded`, `editor_rerun`) keeps the
  other editors of those jobs as measured, and the tables read
  canvas-editor from the new runs only. canvas-editor still throws on the
  complex corpus (`TypeError` reading `width` in its own
  `computeRowColInfo`), in both seeds; those cells stay refused.
- C07's sub-frame flag (#187). C07 publishes the median of a trial's
  clicks, but its sub-frame flag was taken from every middle click, so a
  trial whose median was under one frame could be flagged otherwise (and
  then refused by the reader's flag check). The flag now follows the
  published median. None of the campaign's 1,160 C07 trials was affected.
- Refused C05 and C06 cells named the wrong reason (#189). The warm/cold
  lane writes a criterion's `not_applicable` or `not_run` row at one cache
  state only, and the other measure of the same launch took the
  launch-level code: `crash` for canvas-editor and Docen when the editor's
  data was cold (18 cells), and no reason at all for WordCraft (10 cells)
  and canvas-editor's complex corpus when warm (2 cells). Nothing crashed.
  The reader now gives such a measure the reason its sibling measure
  records, and the writer names a lone `not_applicable` instead of
  stamping `crash`. Found by an adversarial review of every refused cell.
- The document lane's C11, C12 and C15 probes waited 300 s at every size
  (#190). Their probe targets carried no workload id, so the 600 s rule
  for the 250,000-word document (and the 1,000 s rule for the 500,000-word
  one) never reached them, and Plate's prose-250kw loads were cut at
  300 s. A probe's timeout was also labelled `editor_crash`; it is now
  `editor_timeout`. Plate's cells of the four prose-250kw document jobs
  were measured again by Plate-only runs; the editor round is scoped to
  that workload, so Plate's other document jobs stay as measured.
- C15 was not measured for any editor (#191). The probe drives find only
  through a find box in the page, and none of the hosts as configured has
  one it can type into. The report now says so and names, for each editor,
  what find it ships; no C15 attempt ran, so no figure moves.
- Folio's prose-5kw C11 and C12 did not publish (#192). One launch was
  refused for CPU throttling and moved to `rejected-evidence/`, and the
  seed-block gate counted only `cells/`, so the block looked short of a
  launch. A quarantined launch now counts as a refusal, not as missing.
- C10 scrolled the complex document with its document protection (#192).
  GenOffice and eigenpal open a protected package read-only, as Word does,
  and C10's readiness gate waited for an editable surface that never came.
  The scroll lane now loads the unprotected copy the editing lanes load,
  and records the variant. The four C10 complex-document jobs were
  measured again for every editor in a late round (`late_superseded`,
  `late_rerun`).
- Docen's C11 was refused at every size (#193). The surface of a model
  host was bound to the later of its settled ink frame and its ready time,
  and the ready time was a duration measured from after navigation plus
  the 300 ms post-ready wait, on another clock than the frames. The
  settled ink frame (the first frame identical to the screen captured
  after ready) is now the surface; the ready time stands in only when no
  ink stamp exists, and then as the page-clock instant. eigenpal and
  canvas-editor stamp their first layout box on the page clock and are
  unchanged. Docen's cells of the 20 document jobs below the 500k rung
  were measured again by Docen-only runs.
- The memory lane's pair deadline covered one load (#194). A pair opens
  the document, types a 120-character burst, waits, closes and reopens,
  under one deadline of the load timeout plus 120 s (720 s at 250,000
  words); Docen types at about 8.7 s per keystroke at that size. The
  deadline now covers both loads and a burst budget, and a failed pair
  names the phases it reached. Docen's and canvas-editor's prose-250kw
  memory cells were measured again.
- The document lane killed probes that were still within their own load
  budget (#195). A C11 or C12 probe loads the document, reflows it and
  checks its witness, but its subprocess watchdog was one load timeout
  plus 30 s (630 s at 250,000 words); Plate.js takes 335–397 s to be ready
  and 627–708 s to scan its witness at that size, so every attempt was
  killed. The watchdog now covers every load stage and the probe's own
  work. A refusal that said "clock skew" when the skew was inside the 5 ms
  bound now names the page clock check that failed. Plate.js's prose-250kw
  document cells were measured again.
- WordCraft was refused by our harness on 30 cells (#196, #197, #198),
  found by an adversarial review of every refused cell. Its content check
  (C03, C11) never read its text, although the harness had read its whole
  document through WordCraft's own select all and copy since #183; C08 and
  C09 were skipped as not applicable on the same ground; and C10 never
  selected the scroll overlay our host builds for it. Each now uses the
  copy read or the overlay, outside the timed window. Where timed work
  follows in the same page (the input lane's opening check, C14's witness)
  the copy read is skipped. After that copy, WordCraft's paste inserted its
  own clipboard with the system one (5,720 characters for a 1,500-character
  block), so C08 reloads the document after its baseline read and pastes
  on the fresh page (1,500). A modified flag that had already risen before
  a burst no longer turns WordCraft's C05 and C06, which do not apply, into
  a crash. WordCraft's cells of its warm and cold, document, input and C10
  jobs, and of its 500,000-word document jobs, were measured again by
  WordCraft-only runs. Its four 500,000-word C14 jobs were measured again
  as well, at a later commit (6a037a84), only so that one harness measures
  all of WordCraft's 500,000-word cells: the fix does not change C14, which
  has read WordCraft's text through its own select all and copy since #183.
  The first such round (08:41 UTC, both its Spaces) ran slower on every job
  (medians 8.9-9.8 s), with the same build, browser and command
  and no CPU steal or throttling. It did not reproduce: two runs started
  20 minutes later on two Spaces gave 7.7-7.9 s at this commit and 8.2-8.3 s
  at the older d697b98e, matching the first round's 7.5-8.2 s. A change that
  does not reproduce is not a result (AGENTS.md section 4), so the tables
  read the reproduced runs on e2-eigenpal (jobs 162, 163, 166, 167); the
  slow round stays in the run bucket and is not named in the manifest.
- WordCraft's warm and cold jobs end with exit status 3, "nothing
  measured", although their C03 cells are measured (#199, not fixed in this
  release). The run-level tally reads one row per launch, and WordCraft's
  launch row is marked failed by its C05 and C06 bursts: WordCraft's
  modified mark rises once and stays, so every keystroke after the first
  reads `expected_edit_not_confirmed`. C05 and C06 do not apply to
  WordCraft and are published as such. The tables read each criterion's
  attempts, and the publication gates a job on its completion, not its exit
  status, so no figure is affected.
- The screencast recorder keeps the last 1,200 frames, and once it held
  that many every frame cursor stopped moving (#202): the array's length
  stays 1,200, so a scan from "the frames recorded so far" saw no new
  frame. The page clock's anchor was then never found, and every attempt
  that needed it was refused. It happened to two editors only, those that
  paint the most frames during a long load: Docen at 500,000 words (C11
  and C14) and canvas-editor at 250,000 words (C08 and C09). Frames now
  carry a sequence number that never repeats, and every scan cursors on
  it. A scan of every published probe record found no measured figure
  taken after the cap, so no published number was affected. Docen's cells
  of the eight 500,000-word jobs and canvas-editor's cells of the four
  250,000-word input jobs were measured again with the fix (commit
  52ff8990). A later commit stops the harness from caching the decoded
  bitmap of a frame the cap had already dropped (no splice would ever free
  it); that cache lives in the harness's own process, not the browser, so
  it touches no measured figure, and those runs were not repeated for it.
- C14's damage window let through frames from minutes later (#203). C14
  asks whether the document repainted within 500 ms of a settled frame. If
  it did, the sample is that repaint; if not, it is the time the text
  appeared. The window's deadline started only once the harness's own calls
  into the page returned, and a busy page held them for minutes. Every
  frame recorded meanwhile counted, so GenOffice at 500,000 words read
  about 4.9 minutes from a change of under a hundredth of the frame, 160
  seconds after its window opened. The witness now counts only frames inside the window, widened by
  the clock's measured error (250 to 700 ms), so no frame is dropped on
  timing noise. The reader applies the same rule to runs made before the
  fix. Of the published C14 samples, only GenOffice's at 500,000 words
  change: their repaint was outside the window, so they read the time its
  text appeared. Those jobs were measured again with the fix (commit
  936e526b). The round is scoped to C14 (`criteria` in the publication
  manifest): GenOffice's C11, C12 and C15 jobs at 500,000 words never run
  C14, so they keep their cells. The publication-roots check now accepts a
  round scoped to criteria, and refuses one that leaves a job that measured
  them. GenOffice's two-minute wait is its own, not the harness's: in
  C11, which reads nothing from the page before its witness, its 500,000-word
  text appears at 3.6 seconds and its first painted frame comes about 115
  seconds later. C11, C12 and the input lanes use the same witness
  differently: they wait for the first changed frame after the harness's
  own change, and the input lanes check that frame for the typed
  character. There a late frame is the editor's real, slow response, and
  it stays; cutting it would make the slowest editors look faster.
- C04 counted the load's long tasks as deferred work after ready (#205).
  Its long-task observer is registered with `buffered`, so it also receives
  the long tasks recorded during load, delivered about 2 ms after ready. Each
  counted as activity at its delivery time. Every editor therefore showed
  "deferred work" ending about 2 ms after ready (Docen 1.8 ms, Docxodus
  1.9 ms, …), though none was observed. A long task has ended by its
  delivery, so one whose delivery time minus its duration falls before
  ready began before ready. The harness now passes the ready time into the
  page and counts earlier long tasks apart (`long_tasks_before_ready`, null
  when no ready time was given). The reader drops them from records made
  before the fix, by that rule. A load left with no activity is not applicable, the
  harness's own rule, and an editor whose loads all had none reads "no
  deferred work after ready". In the publication roots, all of canvas-editor's,
  Docen's, Docxodus's, eigenpal's, Folio's, GenOffice's and Plate.js's C04
  samples rested only on those tasks, and 96 of SuperDoc's 100. WordCraft's
  rested on them in 62 of 199 loads; in the rest its own long task comes 250
  to 520 ms after ready, and those samples are unchanged. That split, not a
  change in WordCraft, is why its 50,000-word figure moved between campaigns
  (137 ms, then 423 ms). No job was measured again: the records hold every
  activity's time and duration, so the reader's rule is exact; it gives the
  same counts on the publication roots as the harness's start-time rule
  would. Real-browser fixtures (`busy_load.html`, `deferred_task.html`) and
  three records copied from the campaign cover the cases. Ready is when the
  harness sees the ready signal; work that blocks the page before then
  delays ready and counts in C11, not C04. Reviewed by GLM (octo); four of
  its eight findings were fixed.
- WordCraft's C07, C08 and C09 on the complex document are withheld as a
  limit of the harness (#200, not fixed in this release). Its first page
  holds three lines, and the scan that finds the document body took
  WordCraft's painted window chrome for text: every click point landed
  above the page (C08 and C09 on the title bar, C07 also on a toolbar
  button), and the keystrokes that followed never reached the document
  (its text and the screen were unchanged). The reader now refuses those
  trials with `click_points_on_editor_chrome`; a trial skipped as not
  applicable keeps its own reason. WordCraft's prose cells, and every
  other editor's complex cells, stand.
- Runs abandoned and left out of the publication, each stopped by us and
  measured again at the fixed commit: the first 250,000-word Plate.js round
  (#190; every C11 and C12 attempt cut by the 630 s watchdog of #195), and
  the first run of the four 500,000-word document jobs (stopped for #193
  and #195 while its C14 jobs went on). Their pulls stay in the run bucket;
  neither is named in `perf/container/e2_publication.json`. Two WordCraft
  jobs (27 and 102) were stopped part-way when the rest of their Spaces'
  work moved to e2-plate; the manifest names them under `stopped`, the
  publication check requires each to be unsealed and measured whole by
  another run of the round, and the tables never read them.
- Two tests that failed for reasons outside the code they test (#182): the
  sub-frame witness test asserted a timing instead of the rule, and a
  persistence test read the state of `repos/`.
- Perf harness, before Report E was measured (#100–#103, #118–#123): a
  deterministic size ladder; a host record read from the machine, never
  assumed (cgroup limits resolved through mountinfo, container and
  hypervisor evidence, power with its evidence, steal time per run); PERF
  marks that time the same work for every editor; a headless runner that
  keeps and checks every sample, attests every pin, and refuses a noisy or
  battery-powered machine; a tables builder that recomputes every figure
  from the sample files. Reviewed by codex, glm-5.3, MiniMax-M3 and grok;
  every accepted finding is fixed with a test. The later host-rule commits
  (`8e98f66`, `0aaa40f`, `62c73fc`) do not change what the runs recorded:
  re-run in the same sandbox, `host_record()` still gives AC power from the
  cloud vendor, and the four test suites pass there.
- Report E's tables (#111): the lanes table has a load and a save column
  (GitHub Markdown dropped the save cell), package versions read as
  versions, LibreOffice is not a row of n/a in the timed tables, a failed
  cell quotes the error of its latest failed sample, and the save notes
  agree in number. After codex's review (#124): GenOffice's "the file is the
  input" note names the four prose documents (it rewrote `complex.docx`; the
  old note said "every sample"), SuperDoc's flat save is no longer explained
  as work done during load, and the canvas-editor paragraph names both
  diagnostic configurations.
- Dependabot alerts (#93): `harness/ui` puppeteer 22 → 25 (drops
  `extract-zip`, `basic-ftp@5`, and zod 3 from the lockfile), `pdfjs-dist`
  overridden to 6.2.108 in the SuperDoc UI host, and `katex` overridden to
  0.19.1 for `micromark-extension-math` in the plate harness and demo.
  `perf/runner/warm_cold_browser.mjs` follows puppeteer's new ESM entry
  path. Two alerts have no upstream fix and stay open: `zip` 3.0.0 in
  `harness/wordcraft` (needs a `repos/wordcraft` bump, which the trial
  rules forbid touching) and `elliptic` 6.6.1 in `demos/plate` (no patched
  release exists). No figure changes.

## [0.9.4] - 2026-11-01

Tooling only: every TypeScript project in the trial installs with pnpm, and
nothing newer than 5 days enters it. No figure changes.

### Updated

- No editor pin moved (cutoff 2026-10-27, as in 0.9.2 and 0.9.3).
- Twelve projects (six demos, six harnesses) updated with
  `pnpm update --latest` under `minimumReleaseAge: 7200` (5 days, AGENTS.md
  section 1); the editor pins are excluded and move only through
  `build/update_editors.sh`. npm and bun lockfiles removed (#59, #60).
- Live demos rebuilt on the new dependencies: canvas-editor, docxodus, plate,
  superdoc.

### Measured

- Plate, Docxodus and Apryse round trips, run twice: part-for-part identical
  to the published outputs. Their UI captures match `out/ui`.

### Not re-measured

- Every other lane: no pin moved and no harness changed for them.
- **The release gate (`build/verify_publication.sh --with-word`) was not
  run**: Word was busy with another session's job. Published on the owner's
  instruction without it.
- docs-plus and office-open demos have no rebuild recipe; their live builds
  are those of 0.9.3.

### Fixed

- `build/update_editors.sh` installs the docxodus pin with pnpm, not npm.
- `build/rebuild_demo.sh` never copies a demo's local `node_modules` into the
  build tree (`build/test_rebuild_demo.py`).
- superdoc and office-open demos minify with Oxc: Vite 8 no longer ships
  esbuild.

## [0.9.3] - 2026-11-01

Every pixel measurement is taken at 200 dpi; Apryse WebViewer joins every lane
it was missing from; every remaining typed table and pixel figure in Reports
A2, B and C is generated.

### Updated

- No editor pin moved: the release date and cutoff (2026-10-27) are those of
  0.9.2.
- **Pixel resolution: 200 dpi** (110 before), in `build/pixels.py`, the one
  place every pixel script reads it from (`build/test_pixels.py`). The rule
  is in AGENTS.md and RELEASING.md.

### Measured

Each result below was run twice, with identical outputs.

- **Word's pixel layer** at 200 dpi, from the stored Word PDFs: every verdict
  unchanged. Corpus ink is now 5,450,749 px; Apryse 2,119 px (0.04%).
- **LibreOffice's pixel layer**, now generated (`build/lo_render_compare.py`),
  with an Apryse row: Apryse 24,540 px (4.32%, very close); LibreOffice's own
  round trip 888 px (it was 335 at 110 dpi).
- **SmartArt band** (Report C §5) at 200 dpi: the band holds 469,131 px and
  Word draws 0 of them. The checkerboard control lights up 269,641 px, and
  the border control 28,000 px, all of them its own border. The 151
  differing pixels outside the band are one edge that moves by a pixel.
- **A/B variants** (Report C §6.3), now generated (`build/ab_table.py`), in Word
  and in LibreOffice. LibreOffice's corpus and variants are rendered in one
  run.
- **Construct presence** and the **package inventory** with Apryse: every
  construct is visible in Word's render of its output and present in its
  package.
- **Report C UI:** LibreOffice's own pages are rasterised at 200 dpi, and Apryse
  pages 3 and 4 and its comment panel are captured.
- **XSD and package integrity** (Report B), generated: Plate.js 1 real XSD
  violation (published as 0 in 0.9.2), Apryse 4.

### Not re-measured

- **Word was not opened.** Another session's Word job was running, and
  AGENTS.md forbids sharing Word. The Word pixel layer, the SmartArt
  controls and the A/B variants were re-rasterised from the PDFs Word
  exported for 0.9.2. The Word verdicts are 0.9.2's.
- **The publication gate** (`build/verify_publication.sh --with-word`) needs
  Word, for the same reason. It is outstanding.
- Round trips, second passes, the broken corpus and the hostile packages:
  no pin moved, so 0.9.2's results stand.
- Google Docs and Microsoft Word on the hostile packages (AGENTS.md: never
  re-tested).

### Added

- `build/pixels.py`, `build/lo_render_compare.py`, `build/raster_controls.py`,
  `build/ab_table.py`, `build/smartart_band.py`.
- Facts for the remaining typed figures: `lpx.*`, `sa.*`, `ab.*`, `xsd.*`,
  `pkg.*`, `word.<tool>.cell`, `parts.matrix`, `inventory.table` and
  `pixels.dpi`.
- Report C §2.14 (Apryse WebViewer) and Report A2 §6.8 (Apryse).

### Fixed

- **A missed capture failed silently.** `harness/ui/shot.mjs` printed OK when
  a wait or a scroll found nothing; Apryse's "page 3" was page 1. It now
  exits 4 (`build/test_ui_captures.py`).
- **Absolute relationship targets.** `malformation_audit.py` reported 18
  missing parts for Apryse's `/word/...` targets; it now resolves them from
  the package root.
- **Every lane.** Apryse was missing from 15 measurement scripts, among them
  the audits behind six tables, `verify_findings.py` (part of the publication
  gate), `construct_presence.py` and `inventory_table.py`. `build/test_every_lane.py` now checks both path
  patterns and editor lists.
- **Report C §6.3** cited the picture's figures for the chart. It also listed
  page 3 only for `no_chart`, which changes page 4 too.
- **Report C §4.2(a)** called the parts the regenerators *write* the parts
  they *keep*.
- **The SmartArt band locator** took the box around every difference, which
  at 200 dpi swallowed an object below the band. It now takes the control's
  own footprint.
- **Fixed crops.** `strips.py` cropped in 110-dpi pixels; the crops are now in
  inches.
- **Retired instructions.** Report C's recipe used a `/tmp` venv, and Report
  A's patched a rendered report; both now use the PEP 723 scripts and facts.

## [0.9.2] - 2026-11-01

Apryse WebViewer joins as the first closed-source participant; Word is
driven by the audited driver; every remaining typed figure in the reports
is generated; the live demos are rebuilt at the trial's pins.

### Updated

- No editor pin moved: the release date and cutoff (2026-10-27) are those of
  0.9.1, and `build/update_editors.sh` found nothing newer before the cutoff.
- Added `@pdftron/webviewer` 12.2.1 (Apryse WebViewer, trial key), driven
  through its own DOCX editor in a real browser (`harness/apryse/`).
- Microsoft Word is now opened only through the neurotic bench's audited
  driver (`build/vendor/word_pdf.py`, commit 2f2e23db) and its watchdog
  (`build/vendor/word_watchdog.sh`, commit 6fd25e9c), both vendored
  unmodified with their sha256 in `build/vendor/word_pdf.SOURCE`.

### Measured

- **Apryse WebViewer:** 89.9% weighted, 9 failed of 99; the second pass scores the same.
  Its trial stamp adds parts; `build/apryse_stamp.py` labels them and the
  one failure that cannot be separated from the stamp. Word opens its
  output. Three round trips and three second passes give identical parts,
  after the harness was fixed to export only once the comments had loaded.
- **Apryse on the hostile packages** (Report D), two passes, identical:
  grade 0.32. Cleaned B1, B2, B3, B6; kept B7, B8, B10; ran past the
  40-second wall clock on B4, B5 and B9 in both passes.
- **Word verdicts** through the audited driver, twice, identical: the same
  five outputs refused as in 0.9.1, and Apryse's opens.
- **Broken corpus** (Report B), every editor, twice: every defect cell is
  identical across the passes and to 0.9.1. Word on those outputs, twice,
  identical. WordCraft's output now opens (it was recorded as refused in
  0.9.1, on the same file); the change is in how Word was driven, since the
  file did not change.
- **`w:dirty="true"` is no longer fatal on its own.** The single-defect
  corpora, opened twice through the driver: d10 alone and d11 alone do not
  open, d12 alone opens after Word asks whether to update the fields. The
  first report's table, from a hand-written driver that kept no record of
  Word's dialogs, is kept as history. Report B, the main report and
  Reports A/A2 say so.
- **Report C:** the editors' UI captured twice (identical); only GenOffice
  differs from the published captures. Word's pixel layer twice
  (identical); SuperDoc and Docxodus now 0 px, and the corpus ink moved
  from 1,661,202 to 1,661,285 px with every verdict unchanged, an
  environment change.

### Not re-measured

- Google Docs and Microsoft Word on the hostile packages (AGENTS.md: never
  re-tested).
- The `w:dirty` attribute variants (`"1"`, `"false"`, `w:fldLock`) in the
  first report's table; only `w:dirty="true"` was re-opened.
- Report C §5's controls, the §6.2 LibreOffice table and the §6.3 A/B,
  which are not part of the pipeline.
- Jubarte on the hostile packages (Report D1).
- The hostile-package runs were made at load 40–80 while another session's
  batch ran; Apryse's three wall-clock hangs reproduced in both passes but
  were not re-run on a quiet machine.

### Added

- `RELEASING.md` and the "Release" issue template, kept identical by
  `build/test_release_template.py`.
- `build/release_word.sh` (every Word step twice, passes compared) and
  `build/release_broken.sh` (the broken corpus twice, cells compared).
- Generated facts: release dates, code-read commits, participant counts,
  Report B's three tables, Report C's Word pixel table, Report A's
  per-participant namespace counts, `out/word_isolation.json`.
- `build/rebuild_demo.sh`: every live demo rebuilt at the trial's pins,
  with `SOURCE.txt` written from git.
- `render_reports.py --all-twins` rebuilds every DOCX twin.

### Fixed

- `build/run_broken.sh` gave Plate an unset input variable (Report B's
  "no output" came from the script; Plate's own failure, `decode-failed`,
  is now logged in `out_broken/logs/`), gave canvas no input or output
  path, and looked for LibreOffice's output under the wrong name.
- `build/word_verdicts.py` ran a whole Word batch when imported; every
  Word-driving script is now import-safe, with a test.
- LibreOffice is counted as a participant like any other.

## [0.9.1] - 2026-11-01

Every editor moved to its current upstream and the whole trial re-run, with
every report now generated from the measurement.

### Updated

- Checkouts fast-forwarded with `build/update_editors.sh`: Plate.js
  `60c7f5530` (`next`), eigenpal `3425d4d7a`, Folio `958c582cb`, GenOffice
  `36a509e8f`, SuperDoc `0ee03fd3c`, canvas-editor `1865c9b06`, WordCraft
  `a88e00525`, Docxodus `583a11c7f`. Docen, office-open, docs.plus and the
  Fidus Writer repositories had no new commits.
- `@superdoc/sdk` 2.25.0-next.14 → 2.26.0-next.16 (the `next` channel the
  trial has always measured), now pinned in its own `harness/superdoc-sdk/`;
  `docxodus` and `@docxodus/export` 14.2.0 → 15.0.0.
- The main report's pin table gains a "Measured at" column. The `[CODE]`
  file:line citations still refer to the commits the code was read at.

### Measured

- Round trip, second pass, LibreOffice re-open and the eigenpal and Folio
  editor lanes: **no score changed.** Every output keeps the same parts,
  in the same state, as in 0.9.0; only volatile content differs (the
  `core.xml` timestamps, generated media names) and a few byte sizes.
- Microsoft Word 16.115 opens the same outputs and refuses the same five
  (Folio, Folio's editor lane, office-open, Docen, Fidus Writer).
- Hostile packages (Report D), re-run on a quiet machine, every changed
  cell reproduced twice:
  - Docxodus 15.0.0 now names ceilings on the decompression bomb
    (`compression_ratio_limit_exceeded`) and the deep nest
    (`xml_depth_limit_exceeded`, 128 levels), where 14.2.0 kept the bomb and
    ran out of stack. It now keeps the corrupt parts it used to refuse. Its
    grade goes from 0.20 to 0.34, above SuperDoc.
  - Plate does not finish the attribute package inside the 30-second CPU
    budget (0.70 → 0.62, now below Google Docs). This is not attributable to
    Plate's update: the 0.9.0 commit, re-run with the same lockfile on the
    same quiet machine, does not finish either. The cell sits at the edge of
    the budget.
  - Every other cell is unchanged. docs.plus B9 and canvas-editor B4 failed
    only while another 12-worker job saturated the machine, and measured as
    in 0.9.0 when re-run. No other cell's output reached the 64 KB pipe
    limit below, so no other cell lost its message.
- Star counts re-fetched on 2026-11-01.

### Not re-measured

- Report C's screenshots and Word pixel renders (dated 2026-10-30): the
  outputs they render are part-identical, but Docxodus moved a major version
  and its rendering was not re-captured.
- Report A's namespace matrix, and the Google Docs and Jubarte rows.
- The live demos on benchmarks.law are still built at the 0.9.0 commits.

### Added

- Generated reports (#28): every report is rendered from `templates/` and
  `out/facts.json` by `build/render_reports.py`; `build/facts.py` builds the
  facts from the scores, part maps, pins, star snapshot (`build/stars.py`),
  Word verdicts (`build/word_verdicts.py`) and bomb protection levels.
  `--stale OLD_FACTS` lists literal figures an update would leave behind, and
  the release gate gains a "generated" check.
- `build/run_trial.sh` runs the whole measurement end to end;
  `build/score_extra.py` scripts the second-pass and editor-lane scoring that
  0.9.0 did by hand.

### Fixed

- The hostile-package scorer labelled a run stopped by the sandbox's CPU
  limit (SIGXCPU) as a `crash`; it is now a `hang`, like a wall-clock
  timeout. No 0.9.0 cell carried that label.
- The hostile-package sandbox read a child's output through a pipe. Node on
  macOS writes pipes asynchronously and drops what is past the 64 KB buffer
  when it dies, which cut off the message Docxodus prints after a 200 KB
  runtime dump. Output now goes to a file. The labeller also reads
  snake_case ceiling codes (`…_limit_exceeded`) and the .NET DTD refusal.
  Re-running Docxodus 14.2.0 this way confirms the 0.9.0 levels; only their
  wording ("does not name a ceiling") was vague.
- Report D quotes its scorecard and protection labels from the logs, so they
  can no longer drift from the run.
- The DOCX twin-parity gate failed on the v0.9.0 tag because it counted
  `CHANGELOG.md` as a report; it no longer does.

## [0.9.0] - 2026-11-01

The first tagged release: the edition published on benchmarks.law on
2026-11-01, after the correction of that day.

### Measured

- Thirteen participants on `fixture/complex.docx` (35 package parts, 31
  critical exception cases): Plate.js, Docxodus, SuperDoc, Folio (model and
  editor lanes), GenOffice, eigenpal (store and editor lanes), office-open,
  Docen, WordCraft, Fidus Writer, canvas-editor and docs.plus, with LibreOffice
  as the baseline.
- Each editor driven through its own import and export entry point, at the
  commits pinned in the main report (`08b1571f2` Plate, `f52c959b2` SuperDoc
  with `@superdoc/sdk` 2.25.0-next.14, `docxodus` 14.2.0, and so on).
- A 99-check scorer; a second pass that feeds each editor its own output; a
  LibreOffice re-open; Microsoft Word 16.115 opening every output.
- Ten hostile packages run in a sandbox against every editor (Report D), the
  same packages read by Jubarte 0.14.0 (Report D1) and by Word (Report D2).

### Results

- SuperDoc, Docxodus and eigenpal tie for first; Folio is fifth at 97.5%;
  Plate.js is last at 20.6%.

### Corrected (2026-11-01)

- The scorer no longer fails equivalent rewrites that Word itself makes
  (`text.exact` and two field and part checks); eigenpal was rescored
  (#24).
- Every report counts 99 checks, not 97, and quotes the rescored figures
  (Folio 97.5%, Plate.js 20.6%, WordCraft 85.9%).
- Report C: 83 differing pixels are 0.005% of the corpus's ink, not 0.0006%.
- The "only" claims and stale statuses that the reports' own tables
  contradicted were corrected; Report E became Reports D1 and D2.

### Added

- `build/make_demo_docs.py`: one sanitized copy of the fixture per editor
  for the live demos on benchmarks.law (#19, #23), and the demo build
  recipes under `demos/` (#20).
- The release gate `build/verify_publication.sh`: repository claims, DOCX
  twin parity, the findings ledger, the number gate, ECMA-376 schema
  validation, the claim-evidence matrix and, with `--with-word`, Word.
- The per-tool notes filed as issues on each project's repository
  (`outreach/`).

[0.9.1]: https://github.com/arthrod/editors_trial/releases/tag/v0.9.1
[0.9.0]: https://github.com/arthrod/editors_trial/releases/tag/v0.9.0
