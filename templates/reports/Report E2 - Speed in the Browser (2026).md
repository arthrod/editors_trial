# Report E2 — Speed in the Browser (2026)

{{perf.e2.status}}

## What this report is

Nine editors that open Word documents in a web browser were each given the same documents, in a real browser, and timed doing what a person does: opening a document, typing, clicking, pasting, undoing and scrolling. This report gives the results in seven small tables, one per action, and says what the figures can and cannot tell you.

It is written to be read from here to the end of the results. The appendices after that hold everything needed to check it: how each time was taken, the machine, the rule a figure had to pass before it was printed, the full tables, what was not measured and why, and how to run it again.

## How to read the tables

- **A figure is a typical time.** Each action was repeated many times, across several fresh launches of the browser, and the figure is a typical (middle) result of those repeats. Appendix C gives the exact rule.
- **Lower is quicker, or lighter.** Times are in milliseconds (ms, thousandths of a second) or seconds (s); memory is in MiB and GiB (1 GiB is 1,024 MiB).
- **Read down a column.** Each column is one document size, and every editor in it was given the same document. The editors were measured on separate cloud machines of the same type, each shared with other work, so a small difference between two editors can be the machine and not the editor.
- **"under 17 ms"** means the change was on screen at the very next redraw after the action. The screen was redrawn 60 times a second, once every 16.7 ms, and the harness times an action to the redraw that shows it, so a time shorter than one redraw cannot be told apart from any other.
- **A range, such as "48 ms to 81 ms",** is printed where the repeated measurements disagreed too much to print one figure; its ends are what they gave. Neither end is the editor's time; read it as "somewhere about here, and not settled".
- **"not measured"** means the editor can do the action and our tooling could not time it there. It says nothing about the editor. **"crashed"** means the editor's page crashed in every launch of that test at that size; it says nothing about the other tests. **"no figure"** means too few launches gave a confirmed result, whether because of the editor or of our tooling. **"does not apply"** is printed only where there was nothing to measure. A dash means the cell was not part of these runs.
- **Every cell that is not a single figure has a line in Appendix J** saying what was measured there and why no single figure is printed.
- **The editors are in alphabetical order.** This report does not rank them.

## What the figures cannot tell you

- **They are not the times you will see on your own computer.** The tests ran on a cloud server with no graphics processor, so everything an editor draws was drawn by the processor. For WordCraft, which redraws its page continuously, that drawing is nearly all of the processor time it used in the half minute after opening a document (table B8 in Appendix E). The figures compare the editors with each other on machines of that kind.
- **The two largest documents are deliberately extreme.** They are stress tests, not ordinary work; the first two columns are the ones to reason from.
- **A range can be the machine, not the editor.** The machines are shared with other work, and some measurements were taken while a machine was much busier than at other times (issue #228; Appendix B gives the load of each run). The typing cells that print a range at 50,000 words are of that kind. A range should not be read as a property of the editor.
- **Typing was not timed for three editors.** canvas-editor, Docen and WordCraft draw their text where the harness cannot read the outline of a typed character, and the harness refuses to time a keystroke it cannot see land. They can be typed in, and every typed character was confirmed in the editor. The harness did record when the screen changed after each key press, and Appendix J gives those times; it does not print them as the typing time because it cannot check that the change was the character and not, say, the caret (issue #238).
- **Search and replace was not measured** for any editor, because of a gap in our tooling. This report says nothing about it.
- **The line under each table is for orientation.** It says how many of the editors have a figure in the first and in the last column, and the lowest and highest of those figures. An editor without a figure is not in that spread.
- **Only what is listed is measured.** Whether an editor keeps a document's content and formatting intact is the subject of the other reports of this trial.

## The results

{{perf.e2.short_version}}

## Appendix A — What was measured, and how each time was taken

The seven tables of the results come from seven of the criteria described here: opening a document is C11; typing one character is C05, in an editor that has already been typed in; clicking to place the caret is C07; pasting is C08; undoing is C09; scrolling is C10; memory is C17, read two seconds after a burst of typing. The other criteria are in the full tables of Appendix E only.

A "cell" below is one editor, one criterion, one measure and one document: far more cells than the boxes of the results tables. A "seed" is one of the two rounds in which everything was run (Appendix C).

This report concerns browser-visible first paint, typing, scrolling, and related interactions. {{perf.e2.intro}}

Each criterion is one browser-visible or model clock on the same corpus the headless report uses.

{{perf.e2.criterion.C03}}

{{perf.e2.criterion.C04}}

{{perf.e2.criterion.C05}}

{{perf.e2.criterion.C06}}

{{perf.e2.criterion.C07}}

{{perf.e2.criterion.C08}}

{{perf.e2.criterion.C09}}

{{perf.e2.criterion.C10}}

{{perf.e2.criterion.C11}}

{{perf.e2.criterion.C12}}

{{perf.e2.criterion.C13}}

{{perf.e2.criterion.C14}}

{{perf.e2.criterion.C15}}

## Appendix B — The machine and its limits

{{perf.e2.relaxed_bounds}}

{{perf.e2.host_note}}

{{perf.e2.provenance}}

Playwright {{perf.e2.playwright}}, Chromium {{perf.e2.chromium}}. Renderer: {{perf.e2.renderer}}.

## Appendix C — Every measurement was run twice: the rule a figure had to pass

Everything in this report was run twice, in two separate rounds (called seeds below), and a figure is printed only when the two agree. Each round gives one number per cell: the median of its kept launches, where each launch counts as the median of its own samples. The figure in the results above is the midpoint (the average) of the two rounds' numbers. The results print that figure alone; the count of launches, the range and the 90th percentile described below are in the full tables of Appendix E. "under 17 ms" is printed only when both rounds were under one redraw of the screen (16.7 ms, called a frame below); a range is printed for a cell whose two rounds did not agree within {{perf.e2.rel_tol_pct}} percent (or, for times that short, within one frame), and gives the two rounds' numbers.

{{perf.e2.sample_plan}}

{{perf.e2.typing_sample_plan}}

{{perf.e2.rule}}

{{perf.e2.runs}}

## Appendix D — Notes on the full tables, and what was measured again

{{perf.e2.reruns}}
- **How an edit is confirmed.** After each timed interval, and outside it, the harness checks that the edit landed once. It counts the typed text near the caret in the page (Plate, Docxodus, SuperDoc, GenOffice, eigenpal, and Folio through its hidden editing layer) or in the editor's model (canvas-editor, Docen). WordCraft paints into one canvas and puts no document text in the page, so the typing criteria (C04 to C07) confirm its edit by the modified mark in its window title. C08 and C09 confirm it through WordCraft's own select-all and copy, which gives its whole text: a read before the timed interval and one after it, both outside it.
- **WordCraft.** WordCraft puts no document text in the page, so the harness reads its text through WordCraft's own select-all and copy (issue #196), after the timed interval and outside it. C03 and C11 check its content that way. Where timed work follows in the same page (the input lane's opening check before C04 and C07, and C14's frame witness, which reads the whole text itself afterwards), that read is skipped, so a copy never runs before a timed keystroke. After that copy, WordCraft's paste inserted its own clipboard as well as the system one: a 1,500-character block grew the document by 5,720 characters. C08 therefore reloads the document after its baseline read and pastes into the fresh page, where the same block grew it by 1,500 (issue #197). WordCraft scrolls a host overlay (`#wc-scroll`) above its canvas, not the page, so C10 scrolls that overlay with the pointer over the canvas and watches the canvas for the moved frame (issue #198). On the complex document, whose first page holds three lines, the harness's scan for the document body takes WordCraft's painted window chrome for text, so C07, C08 and C09 clicked above the page (the title bar, and for C07 also a toolbar button), and their keystrokes never reached the document. Those three cells are withheld as a limit of the harness, `click_points_on_editor_chrome`, and say nothing about WordCraft (issue #200); its prose cells stand. Its C03 and C10 cells come from jobs that ran WordCraft alone, with the same seeds and blocks; its cells of the document and input lanes come from the last round, which measured every editor again.
- **canvas-editor's load.** canvas-editor paints every page into a canvas and puts no text in the page, so C11 and C14 time it to the first frame in which its canvas shows ink. It paints its empty page's margin marks at once, before the document is imported, so that frame alone came before the document. Its first measurement stopped there: about 130 ms at every size, while the import of the 250,000-word document took 51 seconds (issue #185). canvas-editor reports the import finished one or two frames before it paints the document, and at some sizes it clears the page first. The usable frame is now the first one in which canvas-editor reports the document imported and its first page shows ink that differs from its empty page. Its C11, C12, C14 and C15 cells are measured that way.
- **Docxodus** opens a read-only, paginated view. Lanes that edit switch it to its block editor before the timed interval starts, so its load times are those of the paginated view.
- **The complex document.** It carries Word's document protection. The lanes that edit it, and C10, which scrolls it, open a copy with that protection removed; the lanes that only load it open the original. GenOffice and eigenpal honour the protection by opening the document read-only.
- **The 500,000-word document.** It was added after the campaign (issue #188), for the criteria that only load a document: C11, C12 and C15 in the document lane, and a rung of C14. Each wait of its load may last 1,000 seconds. The lanes that edit, type, scroll or measure memory stop at 250,000 words. Its eight jobs (160 to 167) ran after the campaign's own, and were measured again in the last round with every other job of the document lane.
- **The harness's own work inside a load (issue #206).** To check what an editor shows, the harness reads the document's text from the page while the load is timed. Its search for the document's opening headings grew with the square of the page: on a long document whose paragraphs and headings sit side by side in the page, it ran for many minutes inside the timed interval of C11 and C14, and the first tables gave that time to the editor. The search now grows with the page, and the tick that stamps the usable moment no longer builds the text at all. Every job of the document lane was measured again, for every editor. What remains is recorded with each load (`probe_scan_ms_at_text`) and is inside the C11 and C14 times. {{perf.e2.probe_scan}} canvas-editor's share is the largest because the harness reads its text from the editor's model; no such read is recorded for Docen and WordCraft. The recorded figure is the text read alone: for canvas-editor the same tick also hashes the first page's canvas, which is not in it, so its share is a lower bound (issue #221).
- **A frame that was only a caret (issue #207).** C08 (paste) and C09 (undo) end at the first frame that differs from the picture before the keystroke. Editors that draw their own caret change a few pixels on their own, and such a frame was taken for the paste: the same cell held samples of a few milliseconds and of several hundred. C08, and WordCraft's C09, now wait for a frame in which at least 100 pixels changed; a pasted block changes tens of thousands. Every job of the input lane was measured again, for every editor. C09 for the other editors undoes one typed character, which changes fewer pixels than that, so it keeps the smaller threshold: read a C09 figure of a few milliseconds with that in mind.
- **Typing tolerance.** GenOffice turns autocorrect on by default (Word's defaults except sentence capitalisation). The typing check compares the whole typed text after three folds: typographic quotes, backticks and guillemets count as straight quotes; (c), (r) and (tm), in either case, may become ©, ® and ™; and any run of whitespace (spaces, tabs, non-breaking spaces, line breaks) counts as one space. A typed list marker (`1.`, `a.`, `(i)`) is excused when the editor turned that line into a real list item, or when the editor painted another marker in its place (a renumbered `1.` shown as `2.`, or a line holding only a marker); in this run every excused marker was of the first kind. A missing or extra character still fails.
- **Waiting for a paint.** Where a criterion times the editor's response to the harness's own change (a keystroke, a paste, a reflow, the document's first frame in C11), the sample ends at the first screencast frame that differs from the picture taken before the change; the input lanes also check that frame for the typed character's own ink. The harness then waits at least the criterion's window for that frame, and longer while the page does not answer it: frames are recorded the whole time and read in order, so a busy editor's late frame is its real response and is kept. An editor whose page stayed idle and painted only after the window is refused instead (`paint_witness_unavailable`). No such refusal occurs in C05, C06 or C12. It occurs in C08 at 250,000 words for SuperDoc, in every launch, and for canvas-editor, in most: within the 2-second window only the caret changed, so the paste has no figure there. It also occurs in one of GenOffice's C11 launches at 500,000 words. C14's damage window is different: it classifies, and a frame outside it does not count (issue #203).
- **C14's text check.** Each prose document of the C14 ladder ends with lines of combining marks, characters outside the Basic Multilingual Plane, emoji sequences and right-to-left text; C14 checks (I01 to I03) that they survive in the editor's text, read from its first and last 4,000 characters. Folio and SuperDoc mount only the pages near the start of a long document, and WordCraft paints into a canvas, so for these three the page holds only part of the text. After the timed sample, and outside it, the harness asks each of them for the whole document: SuperDoc through its document model, Folio through its editing layer (mounted by a click on the page), and WordCraft through its own select-all and copy. For the other editors the text the harness already reads is the whole document: from the page for Plate, Docxodus and GenOffice, and from the editor's model for canvas-editor, Docen and eigenpal. C14 gives each wait of a document's load (navigation, the editor's ready signal, the page's load event for the canvas editors Docen and WordCraft, the painted document) up to 1,000 seconds. The complex document carries no such lines, so the check does not apply to it: its C14 cells are timings whose text is not checked. When the check fails, the harness names the cause: an editor whose text could not be read, or whose readable text is a window shorter than nine tenths of the document and stops before its closing paragraph, is withheld as "not checkable", a limit of the harness rather than a fault of the editor; an editor whose whole document was read and still fails keeps the failure.
- **Criteria our harness could not time.** canvas-editor and Docen paint text without glyph geometry the harness can read, so C05 and C06, which time the keystroke's own paint, were not measured for them. WordCraft also paints on one canvas without glyph geometry the harness can read, so its C05 and C06 were not measured either. All three can be typed in, and the harness confirmed each typed character in the editor; it records these launches as `not_applicable`, which is the harness's word for "refused by rule" and not a statement about the editor (issue #238 is the work to time them from the screen's pixels). C15 (search and replace) was not measured for any editor in this run, and that is a gap in our harness, not in the editors. The probe drives find only through a find box in the page, and no host was configured with one. Docen and GenOffice open a find box on Ctrl+F in the hosts we measured. SuperDoc, eigenpal, Docxodus and canvas-editor ship a find box that our hosts do not mount. Plate's find is an optional plugin that its default editor leaves out, Folio's playground has no control that opens its find dialog, and WordCraft paints its find dialog on a canvas, where the probe cannot type into it. The document lane also ran C15 in each of its five jobs per block, so the C15 cells are refused as a duplicate block index as well. No C15 attempt ran, so no figure is affected.
- **Chrome traces.** In every first-block job, each timed launch was followed by a separate, untimed launch that recorded a Chrome trace for diagnosis; second-block jobs ran without them, and so did most typing sessions. Traces never feed a table.
- **Throttling and steal.** The host note in Appendix B gives, per seed, the CPU steal and the samples refused for cgroup CPU throttling; a refused sample is never kept. The Spaces are containers with a CPU quota on a host shared with other tenants. The host note also gives, per seed, the range of that host's 1-minute load average read at the start and end of each job. A sample is never refused for host load: a job that ran while the host was busier is slower, and that is one reason a cell's two seeds can differ.

## Appendix E — The full tables

### C03 — first visible content

C03 ends when the editor's page raises its ready signal: the mark each editor's page sets when the editor reports the document loaded. The harness then checks, outside the timed interval, that the document's opening text is there. Each editor decides when it is ready, so C03 is not one event across editors: an editor that mounts only the first pages of a long document can be ready long before the document is laid out. C11 and C14 time the document itself.

{{perf.e2.table.C03}}

### C04 — deferred work

C04 asks whether the editor keeps working after the document is ready. Ready is the moment the harness sees the editor's ready signal: work that blocks the page before then delays that moment, and counts in the load lanes (C11), not here. The clock runs from ready to the last DOM mutation, long task or main-thread gap over 200 ms, ending once 200 ms pass with none of them. A load with none of them has no deferred work: no sample is recorded and the load counts as not applicable. The harness reads the clock for ready after its own readiness wait returns, so work an editor does in the short span between its signal and that reading counts as load, not as deferred work (issue #221). The observer of long tasks also receives the long tasks recorded during load, delivered about 2 ms after ready. Until issue #205 the harness counted them as deferred work, so every editor showed about 2 ms. A long task has ended by the time it is delivered, so one whose delivery time minus its duration falls before ready began before ready. The reader drops those from the records, and the fixed harness, which sees each task's start, no longer counts them. An editor whose loads all had only those tasks reads "no deferred work after ready". WordCraft runs its own long task 250 to 520 ms after ready in most loads, and its figure is the median of those loads.

{{perf.e2.table.C04}}

### C05 — single-edit responsiveness

{{perf.e2.table.C05}}

### C06 — sustained typing

{{perf.e2.table.C06}}

### C07 — cursor and selection

{{perf.e2.table.C07}}

### C08 — clipboard and bulk editing

{{perf.e2.table.C08}}

### C09 — undo and redo

{{perf.e2.table.C09}}

### C10 — scrolling

{{perf.e2.table.C10}}

### C11 — initial layout

{{perf.e2.table.C11}}

### C12 — incremental reflow

{{perf.e2.table.C12}}

### C13 — global invalidation

{{perf.e2.table.C13}}

### C14 — large-document scaling

Each C14 size rung is a separate measure, and within a rung each clock is its own measure: `presented_frame` (document damage followed load; the sample ends at the first compositor screencast frame at or after the document became usable) and `usable_no_damage` (no damage followed; the sample ends at the DOM document-surface mark and is never labelled a compositor frame). Rungs and measures are never pooled. The damage window is 500 ms after a settled frame, widened by the clock's measured error; a frame recorded later, while the page kept the harness waiting, is not damage inside it (issue #203). The witness looks at the last 1,200 frames the recorder kept. The campaign's records do not count dropped frames, so where more than 1,200 arrived before the witness looked, a damage frame may be gone and the sample recorded as `usable_no_damage`; the figure is still the time the text appeared (issue #221). The two measures must not be read as the same thing: a `usable_no_damage` sample is the time the text appeared in the page, not the time the document was painted (C11 times the painted frame).

{{perf.e2.table.C14}}

### C15 — search and replace

Each C15 step is a separate measure; steps are never pooled.

{{perf.e2.table.C15}}

### C17 — memory by phase

Memory is the resident set size summed over the browser's process tree, in MiB; it counts a page shared by two processes once for each. The phases are: ready, read once the editor's ready signal (see C03) has been raised and the settle delay the harness gives that editor has passed; after a fixed burst of edits, once the harness has verified them in the document; and quiescent, which is a fixed wait, 2 seconds after the burst, with no test that the page is idle.

A ready reading is printed only where the harness checked the length of the mounted text against the document. In this campaign's records it checked the opening text only, or nothing, for Docxodus, Folio, GenOffice, SuperDoc and WordCraft, so at their ready reading the document is not known to be loaded, and those cells read "unverified": an editor can raise its ready signal before a long document is in memory. Their later phases are read after the burst was typed and are printed.

canvas-editor has no figure for the complex document, which it fails to open in every lane, or for 250,000 words, where its page crashed or the burst did not finish in the time allowed.

{{perf.e2.table.C17}}

### C19 — browser memory after the page is closed (not published)

C19 was meant to show memory an editor leaves behind. The harness read the browser's process tree 1 second and 5 seconds after closing the editor's page, and took no reading of an empty browser to subtract. What it read is therefore the browser itself, about the same for every editor and document size, and it cannot be attributed to an editor. No table is printed. {{perf.e2.withheld.C19}} The readings are in the dataset.

### B8 — resources while opening and editing

{{perf.e2.criterion.B8}}

Each cell shows the first seed's median and the second seed's median. A figure is printed as a result only when the two agree within 10 percent (20 ms for CPU; for the settling column, which is a rate, those 20 ms over the typical settling wait of the launches counted); a cell that does not agree says so and gives both medians and the lowest and highest launch, so that what was read is not hidden. The CPU counters advance in steps of 10 ms, so a cell of a few tens of milliseconds is at the counter's resolution. The host has no graphics processor: what an editor draws is drawn by the processor and counts as CPU.

{{perf.e2.table.B8}}

### B9 — typing marathon

Throughput sessions publish chars/s and resources. Latency sessions publish load and key-to-paint with witness counts; their instrumented throughput and resources are withheld.

{{perf.e2.table.TYPING}}

## Appendix F — Not measured in the browser run

{{perf.e2.not_run}}

## Appendix G — Cells whose two rounds did not agree

{{perf.e2.not_reproduced}}

## Appendix H — How to run it again

{{perf.e2.reproduce}}

## Appendix I — DOCX verification

{{perf.e2.word_verification}}

## Appendix J — Every results cell that is not a single figure, and why

The results at the top print a single figure only where two rounds of measurement agreed. This appendix has one line for every other cell of those tables that was part of these runs: {{perf.e2.no_figure.rows}} cells, of which {{perf.e2.no_figure.ranges}} print a range, {{perf.e2.no_figure.not_measured}} "not measured", {{perf.e2.no_figure.no_figure}} "no figure" and {{perf.e2.no_figure.crashed}} "crashed". A launch is one fresh start of the browser; a round has ten. A launch is kept when the harness confirmed the action and saw its result on screen, and refused otherwise; a round needs five kept launches. The reasons are the ones each launch recorded.

{{perf.e2.no_figure}}
