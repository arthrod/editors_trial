# Report E2 — Speed in the Browser (2026)



## The short version

The editors in the tables below were opened in a real browser, each with the same documents, and timed doing what a person does: opening a document, typing, clicking, pasting, undoing and scrolling. This section gives those results in a few small tables. Everything after it is the reference: the full tables, how each measurement was taken, and what was left out and why.

How to read the tables:

- **A figure is a typical time, measured twice.** Each test was run in two separate rounds, each of several fresh launches of the browser. A figure is printed only when the two rounds agree within 10 percent (or, for times that short, within one picture of the screen), and it is the middle of the two rounds' typical (median) values.
- **Lower is quicker, or lighter.** Times are in milliseconds (ms, thousandths of a second) or seconds (s); memory is in MiB and GiB (1 GiB is 1,024 MiB).
- **"under 1 frame"** means the result was on screen in less than the time between two pictures of the screen, in both rounds. The screen was redrawn 60 times a second, so a shorter time cannot be told apart.
- **"varied"** means the two rounds did not agree, so no figure is given. **"crashed"** means the editor's page crashed in every launch. **"does not apply"** means the test cannot be run on that editor. **"no figure"** means too few launches gave a confirmed result, whether because of the editor or of our tooling. A dash means the cell was not part of these runs. The reference tables give the reason for each.
- **The editors are in alphabetical order.** This report does not rank them.

What these figures cannot tell you:

- **They are not the times you will see on your own computer.** The tests ran on a cloud server with no graphics processor, so everything an editor draws was drawn by the processor. For WordCraft, which redraws its page continuously, that drawing is nearly all of the processor time it used in the half minute after opening a document (see B8 in the reference). Compare the editors with each other, in the same column.
- **The two largest documents are far longer than most real documents.** The first two columns are the common case.
- **"varied" is often the machine, not the editor.** The server is shared. Most of the cells that varied in opening and typing at 50,000 words come from one round that ran while the server was busy with other work (issue #228). They should not be read as a property of those editors.
- **Search and replace was not measured** for any editor: that is a gap in our tooling, not in the editors.
- **Only what is listed is measured.** Whether an editor keeps a document's content and formatting intact is the subject of the other reports of this trial.

### Opening a document

From the moment the page is asked for the document until the first frame that shows it, with the text on screen checked against the document.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words | 500,000 words |
|---|---|---|---|---|---|
| canvas-editor + plugin | 344 ms | 1.0 s | 8.3 s | 64.8 s | 285 s |
| Docen | 1.1 s | 1.3 s | 2.3 s | 8.2 s | varied |
| Docxodus | 2.4 s | 3.3 s | 11.2 s | 46.3 s | 99.9 s |
| eigenpal | 547 ms | 698 ms | 1.1 s | 2.4 s | 3.9 s |
| Folio | 797 ms | 940 ms | 1.8 s | 4.7 s | 8.1 s |
| GenOffice | 689 ms | 890 ms | 1.1 s | 2.1 s | 3.2 s |
| Plate.js | 752 ms | 1.2 s | 4.6 s | 19.1 s | 37.4 s |
| SuperDoc | 2.4 s | 2.8 s | 5.8 s | 15.9 s | 29.2 s |
| WordCraft | 1.3 s | 1.3 s | 1.7 s | 2.9 s | 4.5 s |

At 500 words the figures run from 344 ms to 2.4 s; at 500,000 words, from 3.2 s to 285 s.

### Typing one character

From a key press until the frame in which that character is on screen, in a document that is already open.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | does not apply | does not apply | does not apply | does not apply |
| Docen | does not apply | does not apply | does not apply | does not apply |
| Docxodus | under 1 frame | under 1 frame | 18 ms | 31 ms |
| eigenpal | 46 ms | 48 ms | varied | 81 ms |
| Folio | 46 ms | 46 ms | varied | varied |
| GenOffice | 19 ms | 28 ms | varied | no figure |
| Plate.js | 25 ms | 27 ms | 56 ms | varied |
| SuperDoc | 135 ms | varied | varied | 556 ms |
| WordCraft | does not apply | does not apply | does not apply | does not apply |

At 500 words the figures run from under 1 frame to 135 ms; at 250,000 words, from 31 ms to 556 ms.

### Clicking to place the caret

From a click in the text until the next frame the editor paints.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | under 1 frame | 27 ms | 61 ms | 391 ms |
| Docen | 27 ms | 28 ms | 93 ms | 1.8 s |
| Docxodus | under 1 frame | under 1 frame | under 1 frame | 42 ms |
| eigenpal | 29 ms | 28 ms | 26 ms | 20 ms |
| Folio | 63 ms | 77 ms | 387 ms | 1.9 s |
| GenOffice | under 1 frame | under 1 frame | 19 ms | 40 ms |
| Plate.js | 30 ms | 30 ms | 86 ms | 379 ms |
| SuperDoc | 60 ms | 77 ms | 235 ms | 337 ms |
| WordCraft | 185 ms | 175 ms | 173 ms | varied |

At 500 words the figures run from under 1 frame to 185 ms; at 250,000 words, from 20 ms to 1.9 s.

### Pasting a block of text

From the paste of a 1,500-character block until the first frame in which the page visibly changed.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | 94 ms | 361 ms | no figure | no figure |
| Docen | 32 ms | 63 ms | 558 ms | 9.3 s |
| Docxodus | 16 ms | 19 ms | under 1 frame | under 1 frame |
| eigenpal | 53 ms | 57 ms | 109 ms | 109 ms |
| Folio | 49 ms | 107 ms | 131 ms | 413 ms |
| GenOffice | 22 ms | 24 ms | 170 ms | 2.8 s |
| Plate.js | 44 ms | 47 ms | varied | 433 ms |
| SuperDoc | 118 ms | 332 ms | 966 ms | no figure |
| WordCraft | 131 ms | 129 ms | 154 ms | 248 ms |

At 500 words the figures run from 16 ms to 131 ms; at 250,000 words, from under 1 frame to 9.3 s.

### Undoing

From the undo of one typed character until the first frame that differs.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | 56 ms | 25 ms | varied | 65 ms |
| Docen | 25 ms | 50 ms | 463 ms | 8.8 s |
| Docxodus | 69 ms | 325 ms | 3.1 s | 16.6 s |
| eigenpal | 26 ms | 26 ms | 30 ms | 46 ms |
| Folio | 48 ms | 47 ms | 146 ms | 162 ms |
| GenOffice | 18 ms | 19 ms | 158 ms | 2.6 s |
| Plate.js | 23 ms | 21 ms | 45 ms | 154 ms |
| SuperDoc | 67 ms | 123 ms | 230 ms | 270 ms |
| WordCraft | 133 ms | 129 ms | 150 ms | 245 ms |

At 500 words the figures run from 18 ms to 133 ms; at 250,000 words, from 46 ms to 16.6 s.

### Scrolling

From a scroll of the document until the first frame in which its content has moved.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | under 1 frame | 16 ms | under 1 frame | under 1 frame |
| Docen | under 1 frame | 18 ms | under 1 frame | 22 ms |
| Docxodus | under 1 frame | under 1 frame | under 1 frame | 62 ms |
| eigenpal | under 1 frame | 26 ms | 25 ms | 29 ms |
| Folio | 15 ms | under 1 frame | under 1 frame | under 1 frame |
| GenOffice | under 1 frame | 17 ms | 20 ms | 60 ms |
| Plate.js | under 1 frame | under 1 frame | 21 ms | 64 ms |
| SuperDoc | 16 ms | 19 ms | 26 ms | 51 ms |
| WordCraft | varied | 150 ms | varied | 148 ms |

At 500 words the figures run from under 1 frame to 16 ms; at 250,000 words, from under 1 frame to 148 ms.

### Memory with the document open

The memory of the whole browser with the document open, read two seconds after a short burst of typing. It includes the browser itself, so it is not the editor alone.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | 855 MiB | 1.7 GiB | 7.1 GiB | crashed |
| Docen | 698 MiB | 947 MiB | 1.9 GiB | 7.4 GiB |
| Docxodus | 695 MiB | 733 MiB | 985 MiB | 1.9 GiB |
| eigenpal | 657 MiB | 682 MiB | 758 MiB | 996 MiB |
| Folio | 567 MiB | 602 MiB | 875 MiB | 1.9 GiB |
| GenOffice | 585 MiB | 647 MiB | 971 MiB | 2.2 GiB |
| Plate.js | 619 MiB | 676 MiB | 906 MiB | 2.0 GiB |
| SuperDoc | 660 MiB | 773 MiB | 909 MiB | 1.3 GiB |
| WordCraft | 1.1 GiB | 1.1 GiB | 1.1 GiB | 1.3 GiB |

At 500 words the figures run from 567 MiB to 1.1 GiB; at 250,000 words, from 996 MiB to 7.4 GiB.

## What is measured

This report concerns browser-visible first paint, typing, scrolling, and related interactions. 701 of 1061 scheduled editor/criterion/measure cells reproduced between the two seeds. 52 run folders contributed 212 jobs (seed 1: 106 jobs; seed 2: 106 jobs); earliest job start 2026-11-12, latest job end 2026-11-15.

Each criterion is one browser-visible or model clock on the same corpus the headless report uses.

**C03 (first visible content/first usable state).** First visible content/first usable state at the first usable boundary (layer browser visible).

**C04 (deferred work).** Deferred work at the deferred quiescence boundary (layer model).

**C05 (single-edit responsiveness).** Single-edit responsiveness at the presented frame boundary (layer browser visible).

**C06 (sustained typing/bursts).** Sustained typing/bursts at the input to next paint boundary (layer browser visible).

**C07 (cursor/selection/hit testing).** Cursor/selection/hit testing at the input to next paint boundary (layer browser visible).

**C08 (clipboard/bulk editing).** Clipboard/bulk editing at the input to next paint boundary (layer browser visible).

**C09 (undo/redo).** Undo/redo at the input to next paint boundary (layer browser visible).

**C10 (scrolling/viewport).** Scrolling/viewport at the frame time boundary (layer browser visible).

**C11 (initial layout/pagination).** Initial layout/pagination at the first contentful paint boundary (layer browser visible).

**C12 (incremental reflow).** Incremental reflow at the presented frame boundary (layer browser visible).

**C13 (global invalidation).** Global invalidation at the model ready boundary (layer model).

**C14 (large-document scaling).** Large-document scaling at the first usable boundary (layer browser visible).

**C15 (search/replace/indexing).** Search/replace/indexing at the model ready boundary (layer model).

## The host and its limits

Relaxed bounds: Clock skew: 5 ms. Ready/navigation load timeouts: 300 s by default, 600 s on the largest document workload; C14 (large-document scaling) gives each wait of a load (navigation, the editor's ready signal, the page's load event for the canvas editors Docen and WordCraft, the painted document) up to 1000 s. Sparse-witness settle onset floor: 100 ms. CPU throttle tolerance: max(1 ms, 1% of the sample span). Witness anchor lag: max(3 frame intervals, 250 ms). Typing/document content length tolerance: 2% for the prose documents; the complex document (complex-corpus) is accepted at 75% to 125% of the expected length.

Each seed ran on the same hardware class (shared_guarded) on separate virtual machines (Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-2, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft), not on one host. A Space name is a machine name: the editors measured are those in the tables. Spaces e2-apryse, e2-docsplus, e2-fidus are machines named for editors this report does not measure.

Seed 1 — 106 jobs on Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-2, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft: CPU model AMD EPYC 7R13 Processor; CPU quota 8.0; logical CPUs 64; OS linux 6.12.113-138.209.amzn2023.x86_64 (102 jobs), linux 6.12.111-136.204.amzn2023.x86_64 (4 jobs); Chromium 156.0.8078.80; renderer ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver); stolen CPU time less than 0.01%; throttle refusals: 0 of 3198 samples refused for cgroup CPU throttling; host load average (1 min) at the start and end of each job: 2.1 to 40.6, median 10.0.

Seed 2 — 106 jobs on Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-2, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft: CPU model AMD EPYC 7R13 Processor; CPU quota 8.0; logical CPUs 64; OS linux 6.12.113-138.209.amzn2023.x86_64 (96 jobs), linux 6.12.111-136.204.amzn2023.x86_64 (10 jobs); Chromium 156.0.8078.80; renderer ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver); stolen CPU time less than 0.01%; throttle refusals: 4 of 3198 samples refused for cgroup CPU throttling; host load average (1 min) at the start and end of each job: 1.9 to 43.2, median 8.3.

Editor pins (built-editor tree SHA-256 of every attempt that ran, in every run folder): canvas-editor + plugin: db742f005c4542a8afa75f4801dd40785e1ce298331903d5ac84bce79c3b24a0; Docen: cf72bd0ee7f16b61d2751113a6533b63697cc437fdf1916e6cb8c6307a343204; Docxodus: dc663a3ee106917d5b93f06fa3ceaa2527bc917b7accfe582cf6ef411dc121ce; eigenpal: 94bdb0c2ee05a56bff1734c3b11f6d39805e4965fab5d778300ee288ce0af40e; Folio: 34e784f890d8ae99129f7ef98c0af4ca3225278b3f9f1a6ed93bee23a9b14ab4; GenOffice: 746b793e0ad8f2a0a12ec5ecf1aeddfa79895102244ac1c717bce6fbbe523789; Plate.js: 0b3c24cc2bf9348a9e904d22757449915be9abee764f5d345557f928cad6f32d; SuperDoc: 4ab1fc57f5e418532f50bc84c5380723c5ae52750d5ae2fdab55c3a4cefcfed6; WordCraft: 003a46b20c05597e3e385e745c9ddec19a4f0ecb43d57e596209e02c5623849a.

Jobs per Space, from each job summary's host-build records: e2-apryse: 10; e2-canvas: 8; e2-docen: 12; e2-docsplus: 10; e2-docxodus: 9; e2-eigenpal: 9; e2-fidus: 11; e2-folio: 10; e2-genoffice: 11; e2-plate: 21; e2-publish: 4; e2-publish-2: 14; e2-publish-3: 5; e2-publish-4: 5; e2-publish-5: 8; e2-publish-6: 6; e2-publish-7: 7; e2-publish-8: 17; e2-superdoc: 23; e2-wordcraft: 12.

Playwright not recorded, Chromium 156.0.8078.80. Renderer: ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver).

## The rule

This is a first pass with fewer samples than planned. Each cell schedules 10 samples per editor per seed and is published when at least 5 samples are kept. The 90th percentile is printed only when at least 10 samples are kept; with 5 to 9 kept, the table prints the median and the range from the smallest kept sample to the largest, because a percentile of a short sample is not a stable figure.

Typing schedules 6 sessions per kind per seed and publishes a cell when at least 5 are kept. With 5 kept sessions and fewer than 6, the table prints the median and the range from the smallest kept session to the largest. A key-to-paint 90th percentile inside one session is over keys, not over sessions.

Each launch contributes the median of its own samples; n counts kept launches. Scheduled counts come from each run's order. Publishability is decided per trial — job summaries delegate it to their trials — and a cell publishes only from trials that are publishable and record the built editor's identity (host_provenance.tree_sha256, else a pinned editor_version); a trial recording neither is refused as pin not recorded, and a reproduction across different built-editor trees is refused. Each of the two seeds must keep at least 5 launches per cell, its launches pooled across the campaign's run folders, and a run-level block — a shakedown run, dirty repos, unavailable CPU accounting or a failed run — refuses the whole run. The medians must agree within 10 percent of the larger median or the larger witnessed frame interval. Samples of frame-witnessed criteria require complete boolean flags checked against a witnessed interval; model-layer clocks such as C04 and byte counts publish without them, and sub-frame medians are buckets; p90 is printed only when at least 10 launches are kept; with 5 to 9 kept, the table prints the median and the range. p90 is over launch medians. C14 rungs and C14 measures (presented_frame, usable_no_damage) and C15 steps are separate measures; a no-damage C14 sample is the DOM document-surface time, never a compositor frame.

212 jobs in 52 run folders — seed 1: 106 jobs; seed 2: 106 jobs. Dates: 2026-11-12 to 2026-11-15.

## Read this before the tables

- **Re-run jobs.** 32 first-pass jobs were measured again after three harness defects were fixed (issues #173, #174 and #175). The lane round below replaced those re-run jobs in turn. `perf/container/e2_publication.json` names every run and every replaced job. In a second round, 4 C14 jobs of the re-run were measured again after the C14 correctness check was fixed (issue #181). In a third round, those 4 C14 jobs were measured again after C14 was given the editor's own whole-document read and a 1,000-second load timeout (issues #183 and #184). Then single editors' cells of those lanes were measured again alone, each after a change in how the harness measured that editor: canvas-editor (issues #185, #202); Plate.js (issue #190); Docen (issues #193, #202); WordCraft (issues #196, #197); GenOffice (issue #203). The lane round replaced those cells. Then Docen's and canvas-editor's cells of the 4 prose-250kw memory jobs (C17 and C19) were measured again after the memory pair's deadline was found to cover one load where the pair runs two loads and a 120-character burst (issue #194). Those runs measured Docen and canvas-editor alone, under the same job indices and seeds; the tables read them for Docen and canvas-editor, and the other editors of those jobs stay as measured. Then WordCraft's cells of the 20 warm and cold load jobs (C03, with C05 and C06 of the same jobs) were measured again after its opening check was found never to read WordCraft's text, although the harness reads the whole document through WordCraft's own select all and copy; every C03 attempt had been refused as unverifiable (issue #196). Those runs measured WordCraft alone, under the same job indices and seeds; the tables read them for WordCraft, and the other editors of those jobs stay as measured. Then WordCraft's cells of the 20 C10 scroll jobs were measured again after C10 was found never to scroll WordCraft's document: the host's scroll overlay, built for this probe, was never selected, so every attempt found no scroll container (issue #198). Those runs measured WordCraft alone, under the same job indices and seeds; the tables read them for WordCraft, and the other editors of those jobs stay as measured. In a late round, the 4 C10 jobs on the complex document were measured again for every editor after C10 was found to load that document with its document protection, which GenOffice and eigenpal honour by opening it read-only, so C10 never started for them; it now loads the unprotected copy the editing criteria load (issue #192). The tables read the 4 late-round jobs in their place. In a lane round, every job of the document lane (32 jobs) and of the input lane (20 jobs) was measured again for every editor, interleaved as in the campaign, after two harness defects that touched every editor were fixed. The document probe's own scan for the opening headings grew with the square of the page and ran inside the timed load: in the Chrome traces of the replaced jobs it took about 19 minutes of a 250,000-word Plate.js load whose own scripts ran about 21 seconds (issue #206). C08 took the frame in which an editor redrew its own caret for the pasted text, and WordCraft's C09 did the same for an undo: a caret changes 16 to 58 pixels, a painted paste 677 or more, and the criteria now wait for a frame that changes at least 100 (issue #207). For those lanes the tables read the 52 lane-round jobs only; every earlier measurement of them is replaced. 2 editor-round jobs were stopped part-way when their work moved to another Space; each was measured whole there, and the tables never read the stopped parts.
- **How an edit is confirmed.** After each timed interval, and outside it, the harness checks that the edit landed once. It counts the typed text near the caret in the page (Plate, Docxodus, SuperDoc, GenOffice, eigenpal, and Folio through its hidden editing layer) or in the editor's model (canvas-editor, Docen). WordCraft paints into one canvas and puts no document text in the page, so the typing criteria (C04 to C07) confirm its edit by the modified mark in its window title. C08 and C09 confirm it through WordCraft's own select-all and copy, which gives its whole text: a read before the timed interval and one after it, both outside it.
- **WordCraft.** WordCraft puts no document text in the page, so the harness reads its text through WordCraft's own select-all and copy (issue #196), after the timed interval and outside it. C03 and C11 check its content that way. Where timed work follows in the same page (the input lane's opening check before C04 and C07, and C14's frame witness, which reads the whole text itself afterwards), that read is skipped, so a copy never runs before a timed keystroke. After that copy, WordCraft's paste inserted its own clipboard as well as the system one: a 1,500-character block grew the document by 5,720 characters. C08 therefore reloads the document after its baseline read and pastes into the fresh page, where the same block grew it by 1,500 (issue #197). WordCraft scrolls a host overlay (`#wc-scroll`) above its canvas, not the page, so C10 scrolls that overlay with the pointer over the canvas and watches the canvas for the moved frame (issue #198). On the complex document, whose first page holds three lines, the harness's scan for the document body takes WordCraft's painted window chrome for text, so C07, C08 and C09 clicked above the page (the title bar, and for C07 also a toolbar button), and their keystrokes never reached the document. Those three cells are withheld as a limit of the harness, `click_points_on_editor_chrome`, and say nothing about WordCraft (issue #200); its prose cells stand. Its C03 and C10 cells come from jobs that ran WordCraft alone, with the same seeds and blocks; its cells of the document and input lanes come from the last round, which measured every editor again.
- **canvas-editor's load.** canvas-editor paints every page into a canvas and puts no text in the page, so C11 and C14 time it to the first frame in which its canvas shows ink. It paints its empty page's margin marks at once, before the document is imported, so that frame alone came before the document. Its first measurement stopped there: about 130 ms at every size, while the import of the 250,000-word document took 51 seconds (issue #185). canvas-editor reports the import finished one or two frames before it paints the document, and at some sizes it clears the page first. The usable frame is now the first one in which canvas-editor reports the document imported and its first page shows ink that differs from its empty page. Its C11, C12, C14 and C15 cells are measured that way.
- **Docxodus** opens a read-only, paginated view. Lanes that edit switch it to its block editor before the timed interval starts, so its load times are those of the paginated view.
- **The complex document.** It carries Word's document protection. The lanes that edit it, and C10, which scrolls it, open a copy with that protection removed; the lanes that only load it open the original. GenOffice and eigenpal honour the protection by opening the document read-only.
- **The 500,000-word document.** It was added after the campaign (issue #188), for the criteria that only load a document: C11, C12 and C15 in the document lane, and a rung of C14. Each wait of its load may last 1,000 seconds. The lanes that edit, type, scroll or measure memory stop at 250,000 words. Its eight jobs (160 to 167) ran after the campaign's own, and were measured again in the last round with every other job of the document lane.
- **The harness's own work inside a load (issue #206).** To check what an editor shows, the harness reads the document's text from the page while the load is timed. Its search for the document's opening headings grew with the square of the page: on a long document whose paragraphs and headings sit side by side in the page, it ran for many minutes inside the timed interval of C11 and C14, and the first tables gave that time to the editor. The search now grows with the page, and the tick that stamps the usable moment no longer builds the text at all. Every job of the document lane was measured again, for every editor. What remains is recorded with each load (`probe_scan_ms_at_text`) and is inside the C11 and C14 times. Share of the C11 load that is the harness's own text read, at the document size where it is largest: canvas-editor + plugin 10.5 percent (prose-50kw); eigenpal 1.3 percent (prose-500w); GenOffice 1.3 percent (prose-5kw); Plate.js 3.4 percent (prose-500kw); SuperDoc 1.3 percent (prose-5kw); under 1 percent for Docxodus, Folio. canvas-editor's share is the largest because the harness reads its text from the editor's model; no such read is recorded for Docen and WordCraft. The recorded figure is the text read alone: for canvas-editor the same tick also hashes the first page's canvas, which is not in it, so its share is a lower bound (issue #221).
- **A frame that was only a caret (issue #207).** C08 (paste) and C09 (undo) end at the first frame that differs from the picture before the keystroke. Editors that draw their own caret change a few pixels on their own, and such a frame was taken for the paste: the same cell held samples of a few milliseconds and of several hundred. C08, and WordCraft's C09, now wait for a frame in which at least 100 pixels changed; a pasted block changes tens of thousands. Every job of the input lane was measured again, for every editor. C09 for the other editors undoes one typed character, which changes fewer pixels than that, so it keeps the smaller threshold: read a C09 figure of a few milliseconds with that in mind.
- **Typing tolerance.** GenOffice turns autocorrect on by default (Word's defaults except sentence capitalisation). The typing check compares the whole typed text after three folds: typographic quotes, backticks and guillemets count as straight quotes; (c), (r) and (tm), in either case, may become ©, ® and ™; and any run of whitespace (spaces, tabs, non-breaking spaces, line breaks) counts as one space. A typed list marker (`1.`, `a.`, `(i)`) is excused when the editor turned that line into a real list item, or when the editor painted another marker in its place (a renumbered `1.` shown as `2.`, or a line holding only a marker); in this run every excused marker was of the first kind. A missing or extra character still fails.
- **Waiting for a paint.** Where a criterion times the editor's response to the harness's own change (a keystroke, a paste, a reflow, the document's first frame in C11), the sample ends at the first screencast frame that differs from the picture taken before the change; the input lanes also check that frame for the typed character's own ink. The harness then waits at least the criterion's window for that frame, and longer while the page does not answer it: frames are recorded the whole time and read in order, so a busy editor's late frame is its real response and is kept. An editor whose page stayed idle and painted only after the window is refused instead (`paint_witness_unavailable`). No such refusal occurs in C05, C06 or C12. It occurs in C08 at 250,000 words for SuperDoc, in every launch, and for canvas-editor, in most: within the 2-second window only the caret changed, so the paste has no figure there. It also occurs in one of GenOffice's C11 launches at 500,000 words. C14's damage window is different: it classifies, and a frame outside it does not count (issue #203).
- **C14's text check.** Each prose document of the C14 ladder ends with lines of combining marks, characters outside the Basic Multilingual Plane, emoji sequences and right-to-left text; C14 checks (I01 to I03) that they survive in the editor's text, read from its first and last 4,000 characters. Folio and SuperDoc mount only the pages near the start of a long document, and WordCraft paints into a canvas, so for these three the page holds only part of the text. After the timed sample, and outside it, the harness asks each of them for the whole document: SuperDoc through its document model, Folio through its editing layer (mounted by a click on the page), and WordCraft through its own select-all and copy. For the other editors the text the harness already reads is the whole document: from the page for Plate, Docxodus and GenOffice, and from the editor's model for canvas-editor, Docen and eigenpal. C14 gives each wait of a document's load (navigation, the editor's ready signal, the page's load event for the canvas editors Docen and WordCraft, the painted document) up to 1,000 seconds. The complex document carries no such lines, so the check does not apply to it: its C14 cells are timings whose text is not checked. When the check fails, the harness names the cause: an editor whose text could not be read, or whose readable text is a window shorter than nine tenths of the document and stops before its closing paragraph, is withheld as "not checkable", a limit of the harness rather than a fault of the editor; an editor whose whole document was read and still fails keeps the failure.
- **Criteria that do not apply.** canvas-editor and Docen paint text without glyph geometry the harness can read, so C05 and C06, which time the keystroke's own paint, do not apply to them. WordCraft also paints on one canvas without glyph geometry the harness can read, so its C05 and C06 do not apply either. C15 (search and replace) was not measured for any editor in this run, and that is a gap in our harness, not in the editors. The probe drives find only through a find box in the page, and no host was configured with one. Docen and GenOffice open a find box on Ctrl+F in the hosts we measured. SuperDoc, eigenpal, Docxodus and canvas-editor ship a find box that our hosts do not mount. Plate's find is an optional plugin that its default editor leaves out, Folio's playground has no control that opens its find dialog, and WordCraft paints its find dialog on a canvas, where the probe cannot type into it. The document lane also ran C15 in each of its five jobs per block, so the C15 cells are refused as a duplicate block index as well. No C15 attempt ran, so no figure is affected.
- **Chrome traces.** In every first-block job, each timed launch was followed by a separate, untimed launch that recorded a Chrome trace for diagnosis; second-block jobs ran without them, and so did most typing sessions. Traces never feed a table.
- **Throttling and steal.** The host note above gives, per seed, the CPU steal and the samples refused for cgroup CPU throttling; a refused sample is never kept. The Spaces are containers with a CPU quota on a host shared with other tenants. The host note also gives, per seed, the range of that host's 1-minute load average read at the start and end of each job. A sample is never refused for host load: a job that ran while the host was busier is slower, and that is one reason a cell's two seeds can differ.

## Tables

### C03 — first visible content

C03 ends when the editor's page raises its ready signal: the mark each editor's page sets when the editor reports the document loaded. The harness then checks, outside the timed interval, that the document's opening text is there. Each editor decides when it is ready, so C03 is not one event across editors: an editor that mounts only the first pages of a long document can be ready long before the document is laid out. C11 and C14 time the document itself.

| Editor | Workload | Measure | C03 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | process_cold_fs_warm | 1196.0 ms; 0% sub-frame launches; p90 1236.5 ms; n = 10 of 10 |
| Docxodus | complex-corpus | process_cold_fs_warm | 2980.0 ms; 0% sub-frame launches; p90 2999.3 ms; n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 903.5 ms; 0% sub-frame launches; p90 937.8 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 889.0 ms; 0% sub-frame launches; p90 904.6 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 1295.5 ms; 0% sub-frame launches; p90 1329.9 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 892.5 ms; 0% sub-frame launches; p90 915.2 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 997.0 ms; 0% sub-frame launches; p90 1028.3 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | 1586.0 ms; 0% sub-frame launches; p90 1702.6 ms; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | warm_steady | 930.5 ms; 0% sub-frame launches; p90 958.4 ms; n = 10 of 10 |
| Docxodus | complex-corpus | warm_steady | 2496.0 ms; 0% sub-frame launches; p90 2549.6 ms; n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 597.5 ms; 0% sub-frame launches; p90 608.9 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 505.0 ms; 0% sub-frame launches; p90 527.3 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | not reproduced (first 1082.5 ms; second 883.5 ms) |
| Plate.js | complex-corpus | warm_steady | 579.0 ms; 0% sub-frame launches; p90 613.7 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 383.0 ms; 0% sub-frame launches; p90 389.2 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | 911.5 ms; 0% sub-frame launches; p90 1189.4 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | 45500.0 ms; 0% sub-frame launches; p90 50419.8 ms; n = 10 of 10 |
| Docen | prose-250kw | process_cold_fs_warm | not reproduced (first 9218.0 ms; second 10338.0 ms) |
| Docxodus | prose-250kw | process_cold_fs_warm | 44168.5 ms; 0% sub-frame launches; p90 47092.3 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 5861.0 ms; 0% sub-frame launches; p90 6465.6 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | 4677.0 ms; 0% sub-frame launches; p90 5024.6 ms; n = 10 of 10 |
| GenOffice | prose-250kw | process_cold_fs_warm | 2699.0 ms; 0% sub-frame launches; p90 2924.6 ms; n = 10 of 10 |
| Plate.js | prose-250kw | process_cold_fs_warm | 18758.0 ms; 0% sub-frame launches; p90 19900.9 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | process_cold_fs_warm | 1000.0 ms; 0% sub-frame launches; p90 1026.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | process_cold_fs_warm | not reproduced (first 3188.5 ms; second 3626.5 ms) |
| canvas-editor + plugin | prose-250kw | warm_steady | 57138.0 ms; 0% sub-frame launches; p90 61205.7 ms; n = 10 of 10 |
| Docen | prose-250kw | warm_steady | 8858.5 ms; 0% sub-frame launches; p90 10014.8 ms; n = 10 of 10 |
| Docxodus | prose-250kw | warm_steady | 43563.0 ms; 0% sub-frame launches; p90 47171.4 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 5575.0 ms; 0% sub-frame launches; p90 6140.5 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | 4366.0 ms; 0% sub-frame launches; p90 4616.3 ms; n = 10 of 10 |
| GenOffice | prose-250kw | warm_steady | 2443.0 ms; 0% sub-frame launches; p90 2695.4 ms; n = 10 of 10 |
| Plate.js | prose-250kw | warm_steady | 17202.0 ms; 0% sub-frame launches; p90 19075.1 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | warm_steady | 434.5 ms; 0% sub-frame launches; p90 517.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | warm_steady | 2511.5 ms; 0% sub-frame launches; p90 2687.6 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | 222.5 ms; 0% sub-frame launches; p90 242.9 ms; n = 10 of 10 |
| Docen | prose-500w | process_cold_fs_warm | 1145.0 ms; 0% sub-frame launches; p90 1214.5 ms; n = 10 of 10 |
| Docxodus | prose-500w | process_cold_fs_warm | 2445.0 ms; 0% sub-frame launches; p90 2592.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 675.0 ms; 0% sub-frame launches; p90 694.6 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 784.5 ms; 0% sub-frame launches; p90 806.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | 760.0 ms; 0% sub-frame launches; p90 790.7 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 784.0 ms; 0% sub-frame launches; p90 824.2 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 993.5 ms; 0% sub-frame launches; p90 1019.3 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | not reproduced (first 1568.5 ms; second 2006.0 ms) |
| canvas-editor + plugin | prose-500w | warm_steady | 147.0 ms; 0% sub-frame launches; p90 153.2 ms; n = 10 of 10 |
| Docen | prose-500w | warm_steady | 842.5 ms; 0% sub-frame launches; p90 929.3 ms; n = 10 of 10 |
| Docxodus | prose-500w | warm_steady | 2116.5 ms; 0% sub-frame launches; p90 2262.9 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 458.5 ms; 0% sub-frame launches; p90 547.5 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 473.5 ms; 0% sub-frame launches; p90 520.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 438.0 ms; 0% sub-frame launches; p90 478.2 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 512.5 ms; 0% sub-frame launches; p90 549.9 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 389.5 ms; 0% sub-frame launches; p90 395.4 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | not reproduced (first 1003.5 ms; second 1143.5 ms) |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | not reproduced (first 6478.5 ms; second 5217.5 ms) |
| Docen | prose-50kw | process_cold_fs_warm | not reproduced (first 3378.0 ms; second 2551.0 ms) |
| Docxodus | prose-50kw | process_cold_fs_warm | not reproduced (first 13686.5 ms; second 10022.5 ms) |
| eigenpal | prose-50kw | process_cold_fs_warm | not reproduced (first 2716.0 ms; second 1818.0 ms) |
| Folio | prose-50kw | process_cold_fs_warm | not reproduced (first 2335.5 ms; second 1669.0 ms) |
| GenOffice | prose-50kw | process_cold_fs_warm | not reproduced (first 1774.5 ms; second 1441.0 ms) |
| Plate.js | prose-50kw | process_cold_fs_warm | not reproduced (first 6324.0 ms; second 4222.0 ms) |
| SuperDoc | prose-50kw | process_cold_fs_warm | not reproduced (first 1116.5 ms; second 988.5 ms) |
| WordCraft | prose-50kw | process_cold_fs_warm | not reproduced (first 2159.0 ms; second 2471.5 ms) |
| canvas-editor + plugin | prose-50kw | warm_steady | not reproduced (first 6818.0 ms; second 4463.0 ms) |
| Docen | prose-50kw | warm_steady | not reproduced (first 3088.5 ms; second 2218.0 ms) |
| Docxodus | prose-50kw | warm_steady | not reproduced (first 12095.0 ms; second 9142.5 ms) |
| eigenpal | prose-50kw | warm_steady | not reproduced (first 2220.5 ms; second 1535.0 ms) |
| Folio | prose-50kw | warm_steady | not reproduced (first 2072.5 ms; second 1309.0 ms) |
| GenOffice | prose-50kw | warm_steady | not reproduced (first 1386.5 ms; second 1237.0 ms) |
| Plate.js | prose-50kw | warm_steady | not reproduced (first 5563.5 ms; second 3694.5 ms) |
| SuperDoc | prose-50kw | warm_steady | not reproduced (first 941.5 ms; second 388.5 ms) |
| WordCraft | prose-50kw | warm_steady | not reproduced (first 1356.0 ms; second 1539.5 ms) |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | 653.0 ms; 0% sub-frame launches; p90 739.0 ms; n = 10 of 10 |
| Docen | prose-5kw | process_cold_fs_warm | not reproduced (first 1432.5 ms; second 1597.0 ms) |
| Docxodus | prose-5kw | process_cold_fs_warm | 3399.5 ms; 0% sub-frame launches; p90 3784.8 ms; n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | 1020.0 ms; 0% sub-frame launches; p90 1089.1 ms; n = 10 of 10 |
| Folio | prose-5kw | process_cold_fs_warm | not reproduced (first 938.0 ms; second 1058.0 ms) |
| GenOffice | prose-5kw | process_cold_fs_warm | 940.0 ms; 0% sub-frame launches; p90 1391.3 ms; n = 10 of 10 |
| Plate.js | prose-5kw | process_cold_fs_warm | 1199.0 ms; 0% sub-frame launches; p90 1279.5 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | 1035.0 ms; 0% sub-frame launches; p90 1083.8 ms; n = 10 of 10 |
| WordCraft | prose-5kw | process_cold_fs_warm | not reproduced (first 1588.5 ms; second 1991.5 ms) |
| canvas-editor + plugin | prose-5kw | warm_steady | 526.5 ms; 0% sub-frame launches; p90 548.7 ms; n = 10 of 10 |
| Docen | prose-5kw | warm_steady | 1099.0 ms; 0% sub-frame launches; p90 1213.6 ms; n = 10 of 10 |
| Docxodus | prose-5kw | warm_steady | 2772.0 ms; 0% sub-frame launches; p90 2904.2 ms; n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | not reproduced (first 796.5 ms; second 904.5 ms) |
| Folio | prose-5kw | warm_steady | 602.0 ms; 0% sub-frame launches; p90 633.2 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 655.0 ms; 0% sub-frame launches; p90 722.0 ms; n = 10 of 10 |
| Plate.js | prose-5kw | warm_steady | 823.5 ms; 0% sub-frame launches; p90 837.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | 394.5 ms; 0% sub-frame launches; p90 413.7 ms; n = 10 of 10 |
| WordCraft | prose-5kw | warm_steady | not reproduced (first 932.0 ms; second 1142.5 ms) |

### C04 — deferred work

C04 asks whether the editor keeps working after the document is ready. Ready is the moment the harness sees the editor's ready signal: work that blocks the page before then delays that moment, and counts in the load lanes (C11), not here. The clock runs from ready to the last DOM mutation, long task or main-thread gap over 200 ms, ending once 200 ms pass with none of them. A load with none of them has no deferred work: no sample is recorded and the load counts as not applicable. The harness reads the clock for ready after its own readiness wait returns, so work an editor does in the short span between its signal and that reading counts as load, not as deferred work (issue #221). The observer of long tasks also receives the long tasks recorded during load, delivered about 2 ms after ready. Until issue #205 the harness counted them as deferred work, so every editor showed about 2 ms. A long task has ended by the time it is delivered, so one whose delivery time minus its duration falls before ready began before ready. The reader drops those from the records, and the fixed harness, which sees each task's start, no longer counts them. An editor whose loads all had only those tasks reads "no deferred work after ready". WordCraft runs its own long task 250 to 520 ms after ready in most loads, and its figure is the median of those loads.

| Editor | Workload | C04 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docxodus | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) |
| eigenpal | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) |
| Folio | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) |
| GenOffice | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) |
| Plate.js | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) |
| SuperDoc | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) |
| WordCraft | complex-corpus | 951.0 ms; range 255.9 to 2577.9 ms; n = 8 of 10; 2 of 10 launches failed: not_applicable: 2; second: 3 of 10 launches failed: not_applicable: 3 |
| canvas-editor + plugin | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docen | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docxodus | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| eigenpal | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Folio | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| GenOffice | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Plate.js | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| SuperDoc | prose-250kw | first: not enough samples (n = 4 of 10; reasons not_applicable: 6) |
| WordCraft | prose-250kw | 479.5 ms; range 442.9 to 2549.6 ms; n = 6 of 10; 4 of 10 launches failed: not_applicable: 4; second: 5 of 10 launches failed: not_applicable: 5 |
| canvas-editor + plugin | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docen | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docxodus | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) |
| eigenpal | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) |
| Folio | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) |
| GenOffice | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) |
| Plate.js | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) |
| SuperDoc | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) |
| WordCraft | prose-500w | not reproduced (first 664.9 ms; second 886.9 ms); first: 2 of 10 launches failed: not_applicable: 2; second: 3 of 10 launches failed: not_applicable: 3 |
| canvas-editor + plugin | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docen | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docxodus | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| eigenpal | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Folio | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| GenOffice | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Plate.js | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| SuperDoc | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| WordCraft | prose-50kw | second: not enough samples (n = 4 of 10; reasons not_applicable: 6) |
| canvas-editor + plugin | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docen | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Docxodus | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| eigenpal | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Folio | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| GenOffice | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| Plate.js | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| SuperDoc | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) |
| WordCraft | prose-5kw | first: not enough samples (n = 4 of 10; reasons not_applicable: 6); second: not enough samples (n = 2 of 10; reasons not_applicable: 8) |

### C05 — single-edit responsiveness

| Editor | Workload | Measure | C05 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | complex-corpus | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 37.1 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 59.3 ms; 0% sub-frame launches; p90 63.1 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 28.4 ms; 0% sub-frame launches; p90 38.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 40.7 ms; 0% sub-frame launches; p90 51.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 228.9 ms; 0% sub-frame launches; p90 240.9 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | complex-corpus | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 42.4 ms; 0% sub-frame launches; p90 48.1 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 51.3 ms; 0% sub-frame launches; p90 56.2 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | 25.8 ms; 20% sub-frame launches; p90 28.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | warm_steady | 24.1 ms; 0% sub-frame launches; p90 32.3 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 219.3 ms; 0% sub-frame launches; p90 222.7 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-250kw | process_cold_fs_warm | 32.9 ms; 0% sub-frame launches; p90 36.4 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 85.1 ms; 0% sub-frame launches; p90 95.6 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | 442.7 ms; 0% sub-frame launches; p90 469.5 ms; n = 10 of 10 |
| GenOffice | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 1 of 10; reasons unverified: 9) |
| Plate.js | prose-250kw | process_cold_fs_warm | not reproduced (first 175.2 ms; second 205.5 ms) |
| SuperDoc | prose-250kw | process_cold_fs_warm | 549.2 ms; 0% sub-frame launches; p90 616.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-250kw | warm_steady | 27.6 ms; 0% sub-frame launches; p90 32.8 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 76.7 ms; 0% sub-frame launches; p90 85.4 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | not reproduced (first 427.2 ms; second 483.5 ms) |
| GenOffice | prose-250kw | warm_steady | second: not enough samples (n = 1 of 10; reasons unverified: 9) |
| Plate.js | prose-250kw | warm_steady | not reproduced (first 129.7 ms; second 161.8 ms) |
| SuperDoc | prose-250kw | warm_steady | 557.2 ms; 0% sub-frame launches; p90 602.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 70% sub-frame launches; p90 17.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 60.1 ms; 0% sub-frame launches; p90 61.2 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 51.3 ms; 0% sub-frame launches; p90 58.8 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | 25.6 ms; 20% sub-frame launches; p90 30.6 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 47.3 ms; 0% sub-frame launches; p90 51.2 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 148.9 ms; 0% sub-frame launches; p90 153.2 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500w | warm_steady | < 1 frame (16.7 ms); 60% sub-frame launches; p90 19.5 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 46.2 ms; 0% sub-frame launches; p90 50.2 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 45.2 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 17.5 ms; 30% sub-frame launches; p90 26.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 22.9 ms; 0% sub-frame launches; p90 27.1 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 137.4 ms; 0% sub-frame launches; p90 139.7 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-50kw | process_cold_fs_warm | 18.6 ms; 30% sub-frame launches; p90 26.5 ms; n = 10 of 10 |
| eigenpal | prose-50kw | process_cold_fs_warm | not reproduced (first 97.6 ms; second 65.5 ms) |
| Folio | prose-50kw | process_cold_fs_warm | not reproduced (first 215.3 ms; second 134.0 ms) |
| GenOffice | prose-50kw | process_cold_fs_warm | not reproduced (first 193.6 ms; second 143.4 ms) |
| Plate.js | prose-50kw | process_cold_fs_warm | not reproduced (first 98.0 ms; second 67.9 ms) |
| SuperDoc | prose-50kw | process_cold_fs_warm | not reproduced (first 644.0 ms; second 450.2 ms); first: 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-50kw | warm_steady | 22.2 ms; 20% sub-frame launches; p90 26.2 ms; n = 10 of 10 |
| eigenpal | prose-50kw | warm_steady | not reproduced (first 77.3 ms; second 56.2 ms) |
| Folio | prose-50kw | warm_steady | not reproduced (first 182.8 ms; second 121.5 ms) |
| GenOffice | prose-50kw | warm_steady | not reproduced (first 207.3 ms; second 139.5 ms) |
| Plate.js | prose-50kw | warm_steady | 64.1 ms; 0% sub-frame launches; p90 77.6 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | warm_steady | not reproduced (first 614.5 ms; second 431.5 ms); first: 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-5kw | process_cold_fs_warm | < 1 frame (16.7 ms); 70% sub-frame launches; p90 18.9 ms; n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | 72.0 ms; 0% sub-frame launches; p90 79.5 ms; n = 10 of 10 |
| Folio | prose-5kw | process_cold_fs_warm | 56.4 ms; 0% sub-frame launches; p90 73.5 ms; n = 10 of 10 |
| GenOffice | prose-5kw | process_cold_fs_warm | 32.3 ms; 0% sub-frame launches; p90 35.7 ms; n = 10 of 10 |
| Plate.js | prose-5kw | process_cold_fs_warm | 49.0 ms; 0% sub-frame launches; p90 57.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | 301.1 ms; 0% sub-frame launches; p90 335.8 ms; n = 10 of 10 |
| WordCraft | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-5kw | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.1 ms; n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | 45.8 ms; 0% sub-frame launches; p90 52.7 ms; n = 10 of 10 |
| Folio | prose-5kw | warm_steady | 44.7 ms; 0% sub-frame launches; p90 48.0 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 26.7 ms; 10% sub-frame launches; p90 31.2 ms; n = 10 of 10 |
| Plate.js | prose-5kw | warm_steady | 27.1 ms; 0% sub-frame launches; p90 32.1 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | not reproduced (first 286.2 ms; second 318.5 ms) |
| WordCraft | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C06 — sustained typing

| Editor | Workload | Measure | C06 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | complex-corpus | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 16.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 39.8 ms; 0% sub-frame launches; p90 42.6 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 54.1 ms; 0% sub-frame launches; p90 66.4 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 21.4 ms; 10% sub-frame launches; p90 23.1 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 25.1 ms; 0% sub-frame launches; p90 29.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 126.0 ms; 0% sub-frame launches; p90 134.9 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) |
| Docen | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | complex-corpus | warm_steady | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 43.1 ms; 0% sub-frame launches; p90 44.9 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 53.4 ms; 0% sub-frame launches; p90 66.3 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | 21.8 ms; 20% sub-frame launches; p90 25.7 ms; n = 10 of 10 |
| Plate.js | complex-corpus | warm_steady | 21.7 ms; 0% sub-frame launches; p90 26.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 121.6 ms; 0% sub-frame launches; p90 132.8 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-250kw | process_cold_fs_warm | 29.0 ms; 0% sub-frame launches; p90 32.2 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 59.8 ms; 0% sub-frame launches; p90 68.4 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | prose-250kw | process_cold_fs_warm | 129.6 ms; 0% sub-frame launches; p90 140.5 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | process_cold_fs_warm | 313.2 ms; 0% sub-frame launches; range 286.1 to 410.3 ms; n = 9 of 10; 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-250kw | warm_steady | 27.6 ms; 0% sub-frame launches; p90 32.8 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 60.7 ms; 0% sub-frame launches; p90 75.1 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | prose-250kw | warm_steady | second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | prose-250kw | warm_steady | 131.8 ms; 0% sub-frame launches; p90 147.0 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | warm_steady | not reproduced (first 303.3 ms; second 337.5 ms); first: 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 16.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 41.8 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 44.4 ms; 0% sub-frame launches; p90 52.3 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 60% sub-frame launches; p90 21.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 22.1 ms; 0% sub-frame launches; p90 26.6 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 73.4 ms; 0% sub-frame launches; p90 85.4 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500w | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.1 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 38.6 ms; 0% sub-frame launches; p90 40.0 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 48.7 ms; 0% sub-frame launches; p90 57.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 17.3 ms; 50% sub-frame launches; p90 21.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 22.3 ms; 0% sub-frame launches; p90 25.5 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 76.6 ms; 0% sub-frame launches; p90 82.7 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-50kw | process_cold_fs_warm | 17.4 ms; 30% sub-frame launches; p90 22.5 ms; n = 10 of 10 |
| eigenpal | prose-50kw | process_cold_fs_warm | not reproduced (first 66.5 ms; second 44.0 ms) |
| Folio | prose-50kw | process_cold_fs_warm | not reproduced (first 171.4 ms; second 117.5 ms) |
| GenOffice | prose-50kw | process_cold_fs_warm | not reproduced (first 176.3 ms; second 134.7 ms) |
| Plate.js | prose-50kw | process_cold_fs_warm | not reproduced (first 59.2 ms; second 39.2 ms) |
| SuperDoc | prose-50kw | process_cold_fs_warm | not reproduced (first 369.9 ms; second 278.9 ms); first: 3 of 10 launches failed: unverified: 3 |
| WordCraft | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-50kw | warm_steady | 16.9 ms; 50% sub-frame launches; p90 24.8 ms; n = 10 of 10 |
| eigenpal | prose-50kw | warm_steady | 64.5 ms; 0% sub-frame launches; p90 76.3 ms; n = 10 of 10 |
| Folio | prose-50kw | warm_steady | not reproduced (first 163.5 ms; second 107.9 ms) |
| GenOffice | prose-50kw | warm_steady | not reproduced (first 203.2 ms; second 143.2 ms) |
| Plate.js | prose-50kw | warm_steady | not reproduced (first 61.2 ms; second 43.9 ms) |
| SuperDoc | prose-50kw | warm_steady | not reproduced (first 370.5 ms; second 275.1 ms); first: 3 of 10 launches failed: unverified: 3 |
| WordCraft | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-5kw | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | 44.0 ms; 0% sub-frame launches; p90 55.1 ms; n = 10 of 10 |
| Folio | prose-5kw | process_cold_fs_warm | 49.9 ms; 0% sub-frame launches; p90 59.3 ms; n = 10 of 10 |
| GenOffice | prose-5kw | process_cold_fs_warm | 22.4 ms; 0% sub-frame launches; range 17.7 to 30.4 ms; n = 9 of 10; 1 of 10 launches failed: crash: 1 |
| Plate.js | prose-5kw | process_cold_fs_warm | 24.6 ms; 0% sub-frame launches; p90 27.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | not reproduced (first 176.1 ms; second 199.9 ms) |
| WordCraft | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-5kw | warm_steady | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | 46.2 ms; 0% sub-frame launches; p90 59.5 ms; n = 10 of 10 |
| Folio | prose-5kw | warm_steady | 48.0 ms; 0% sub-frame launches; p90 62.2 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 21.9 ms; 0% sub-frame launches; range 19.2 to 28.7 ms; n = 9 of 10; 1 of 10 launches failed: crash: 1 |
| Plate.js | prose-5kw | warm_steady | 23.8 ms; 10% sub-frame launches; p90 30.6 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | 175.2 ms; 0% sub-frame launches; p90 203.4 ms; n = 10 of 10 |
| WordCraft | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C07 — cursor and selection

| Editor | Workload | C07 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | 27.1 ms; 0% sub-frame launches; p90 28.5 ms; n = 10 of 10 |
| Docxodus | complex-corpus | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | 22.2 ms; 0% sub-frame launches; p90 23.9 ms; n = 10 of 10 |
| Folio | complex-corpus | 76.5 ms; 0% sub-frame launches; p90 79.3 ms; n = 10 of 10 |
| GenOffice | complex-corpus | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| Plate.js | complex-corpus | 44.1 ms; 0% sub-frame launches; p90 46.0 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 61.6 ms; 0% sub-frame launches; p90 64.8 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10); second: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10) |
| canvas-editor + plugin | prose-250kw | 386.3 ms; 0% sub-frame launches; p90 416.0 ms; n = 10 of 10 |
| Docen | prose-250kw | 1789.9 ms; 0% sub-frame launches; p90 1929.9 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 41.8 ms; 0% sub-frame launches; p90 42.8 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 19.4 ms; 0% sub-frame launches; p90 23.0 ms; n = 10 of 10 |
| Folio | prose-250kw | 1869.5 ms; 0% sub-frame launches; p90 2031.6 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 39.4 ms; 0% sub-frame launches; p90 50.9 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 374.0 ms; 0% sub-frame launches; p90 409.1 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | 343.7 ms; 0% sub-frame launches; p90 361.7 ms; n = 10 of 10 |
| WordCraft | prose-250kw | not reproduced (first 169.9 ms; second 194.3 ms) |
| canvas-editor + plugin | prose-500w | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| Docen | prose-500w | 27.5 ms; 0% sub-frame launches; p90 29.4 ms; n = 10 of 10 |
| Docxodus | prose-500w | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-500w | 28.7 ms; 0% sub-frame launches; p90 29.1 ms; n = 10 of 10 |
| Folio | prose-500w | 63.9 ms; 0% sub-frame launches; p90 64.1 ms; n = 10 of 10 |
| GenOffice | prose-500w | < 1 frame (16.7 ms); 50% sub-frame launches; p90 19.3 ms; n = 10 of 10 |
| Plate.js | prose-500w | 29.8 ms; 0% sub-frame launches; p90 32.1 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 60.1 ms; 0% sub-frame launches; p90 60.9 ms; n = 10 of 10 |
| WordCraft | prose-500w | 191.7 ms; 0% sub-frame launches; p90 216.9 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | 61.0 ms; 0% sub-frame launches; p90 77.2 ms; n = 10 of 10 |
| Docen | prose-50kw | 92.6 ms; 0% sub-frame launches; p90 105.8 ms; n = 10 of 10 |
| Docxodus | prose-50kw | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-50kw | 26.3 ms; 0% sub-frame launches; p90 28.0 ms; n = 10 of 10 |
| Folio | prose-50kw | 395.7 ms; 0% sub-frame launches; p90 443.6 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 20.3 ms; 20% sub-frame launches; p90 23.1 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 92.3 ms; 0% sub-frame launches; p90 93.4 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 244.6 ms; 0% sub-frame launches; p90 250.0 ms; n = 10 of 10 |
| WordCraft | prose-50kw | 170.9 ms; 0% sub-frame launches; p90 189.4 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | 27.7 ms; 20% sub-frame launches; p90 28.8 ms; n = 10 of 10 |
| Docen | prose-5kw | 27.4 ms; 0% sub-frame launches; p90 29.3 ms; n = 10 of 10 |
| Docxodus | prose-5kw | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-5kw | 28.4 ms; 0% sub-frame launches; p90 29.1 ms; n = 10 of 10 |
| Folio | prose-5kw | 77.8 ms; 0% sub-frame launches; p90 79.7 ms; n = 10 of 10 |
| GenOffice | prose-5kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 21.0 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 29.9 ms; 0% sub-frame launches; p90 38.5 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 76.4 ms; 0% sub-frame launches; p90 78.2 ms; n = 10 of 10 |
| WordCraft | prose-5kw | 175.6 ms; 0% sub-frame launches; p90 179.9 ms; n = 10 of 10 |

### C08 — clipboard and bulk editing

| Editor | Workload | C08 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Docxodus | complex-corpus | < 1 frame (16.7 ms); 60% sub-frame launches; p90 20.0 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 71.0 ms; 0% sub-frame launches; p90 79.5 ms; n = 10 of 10 |
| Folio | complex-corpus | 62.9 ms; 0% sub-frame launches; p90 66.2 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 30.6 ms; 0% sub-frame launches; p90 36.0 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 32.5 ms; 0% sub-frame launches; p90 36.8 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 230.7 ms; 0% sub-frame launches; p90 246.3 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10); second: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10) |
| canvas-editor + plugin | prose-250kw | first: not enough samples (n = 2 of 10; reasons crash: 1; paint_witness_unavailable: 7); second: not enough samples (n = 2 of 10; reasons paint_witness_unavailable: 8) |
| Docen | prose-250kw | 9378.3 ms; 0% sub-frame launches; p90 10115.5 ms; n = 10 of 10 |
| Docxodus | prose-250kw | < 1 frame (16.7 ms); 50% sub-frame launches; p90 21.6 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 107.4 ms; 0% sub-frame launches; p90 111.5 ms; n = 10 of 10 |
| Folio | prose-250kw | 425.1 ms; 0% sub-frame launches; p90 459.3 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 2849.8 ms; 0% sub-frame launches; p90 4277.0 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 429.2 ms; 0% sub-frame launches; p90 477.6 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| WordCraft | prose-250kw | 245.3 ms; 0% sub-frame launches; p90 259.2 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | 93.2 ms; 0% sub-frame launches; p90 103.4 ms; n = 10 of 10 |
| Docen | prose-500w | 30.9 ms; 0% sub-frame launches; p90 41.8 ms; n = 10 of 10 |
| Docxodus | prose-500w | < 1 frame (16.7 ms); 80% sub-frame launches; p90 20.6 ms; n = 10 of 10 |
| eigenpal | prose-500w | 51.5 ms; 0% sub-frame launches; p90 59.3 ms; n = 10 of 10 |
| Folio | prose-500w | 51.7 ms; 0% sub-frame launches; p90 62.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | 21.7 ms; 10% sub-frame launches; p90 28.0 ms; n = 10 of 10 |
| Plate.js | prose-500w | 43.4 ms; 0% sub-frame launches; p90 49.5 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 120.9 ms; 0% sub-frame launches; p90 131.9 ms; n = 10 of 10 |
| WordCraft | prose-500w | 135.7 ms; 0% sub-frame launches; p90 138.9 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | first: not enough samples (n = 2 of 10; reasons unverified: 8); second: not enough samples (n = 4 of 10; reasons unverified: 6) |
| Docen | prose-50kw | 582.8 ms; 0% sub-frame launches; p90 632.2 ms; n = 10 of 10 |
| Docxodus | prose-50kw | < 1 frame (16.7 ms); 50% sub-frame launches; p90 26.4 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 109.4 ms; 0% sub-frame launches; p90 128.2 ms; n = 10 of 10 |
| Folio | prose-50kw | 135.4 ms; 0% sub-frame launches; p90 153.9 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 171.9 ms; 0% sub-frame launches; p90 186.6 ms; n = 10 of 10 |
| Plate.js | prose-50kw | not reproduced (first 151.9 ms; second 128.9 ms) |
| SuperDoc | prose-50kw | 982.5 ms; 0% sub-frame launches; p90 1083.9 ms; n = 10 of 10 |
| WordCraft | prose-50kw | 157.3 ms; 0% sub-frame launches; p90 174.9 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | 361.5 ms; 0% sub-frame launches; p90 380.0 ms; n = 10 of 10 |
| Docen | prose-5kw | 63.2 ms; 0% sub-frame launches; p90 69.1 ms; n = 10 of 10 |
| Docxodus | prose-5kw | 19.7 ms; 0% sub-frame launches; p90 21.7 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 59.1 ms; 0% sub-frame launches; p90 62.3 ms; n = 10 of 10 |
| Folio | prose-5kw | 102.4 ms; 0% sub-frame launches; p90 113.7 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 20.7 ms; 0% sub-frame launches; p90 26.1 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 48.4 ms; 0% sub-frame launches; p90 51.3 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 331.8 ms; 0% sub-frame launches; p90 345.8 ms; n = 10 of 10 |
| WordCraft | prose-5kw | 123.1 ms; 0% sub-frame launches; p90 135.7 ms; n = 10 of 10 |

### C09 — undo and redo

| Editor | Workload | C09 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Docxodus | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| eigenpal | complex-corpus | 32.9 ms; 0% sub-frame launches; p90 35.6 ms; n = 10 of 10 |
| Folio | complex-corpus | 79.9 ms; 0% sub-frame launches; p90 85.2 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 21.5 ms; 20% sub-frame launches; p90 32.1 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 39.4 ms; 0% sub-frame launches; p90 47.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 180.8 ms; 0% sub-frame launches; p90 204.6 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10); second: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10) |
| canvas-editor + plugin | prose-250kw | 65.9 ms; 22% sub-frame launches; range 10.9 to 116.9 ms; n = 9 of 10; 1 of 10 launches failed: crash: 1 |
| Docen | prose-250kw | 9014.1 ms; 0% sub-frame launches; p90 9409.7 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 16630.8 ms; 0% sub-frame launches; p90 17137.5 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 45.2 ms; 0% sub-frame launches; p90 50.0 ms; n = 10 of 10 |
| Folio | prose-250kw | 168.5 ms; 0% sub-frame launches; p90 293.2 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 2736.9 ms; 0% sub-frame launches; p90 3073.9 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 155.8 ms; 0% sub-frame launches; p90 177.5 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | 270.0 ms; 0% sub-frame launches; p90 281.0 ms; n = 10 of 10 |
| WordCraft | prose-250kw | 251.1 ms; 0% sub-frame launches; p90 282.1 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | 58.4 ms; 0% sub-frame launches; p90 64.7 ms; n = 10 of 10 |
| Docen | prose-500w | 26.2 ms; 0% sub-frame launches; p90 31.2 ms; n = 10 of 10 |
| Docxodus | prose-500w | 69.2 ms; 0% sub-frame launches; p90 74.7 ms; n = 10 of 10 |
| eigenpal | prose-500w | 24.9 ms; 0% sub-frame launches; p90 32.3 ms; n = 10 of 10 |
| Folio | prose-500w | 51.4 ms; 0% sub-frame launches; p90 60.1 ms; n = 10 of 10 |
| GenOffice | prose-500w | 18.6 ms; 20% sub-frame launches; p90 22.7 ms; n = 10 of 10 |
| Plate.js | prose-500w | 23.2 ms; 30% sub-frame launches; p90 24.9 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 67.0 ms; 0% sub-frame launches; p90 71.1 ms; n = 10 of 10 |
| WordCraft | prose-500w | 134.8 ms; 0% sub-frame launches; p90 149.9 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | not reproduced (first 183.1 ms; second 155.7 ms) |
| Docen | prose-50kw | 472.3 ms; 0% sub-frame launches; p90 506.1 ms; n = 10 of 10 |
| Docxodus | prose-50kw | 3176.3 ms; 0% sub-frame launches; p90 3392.9 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 32.8 ms; 0% sub-frame launches; p90 34.2 ms; n = 10 of 10 |
| Folio | prose-50kw | 147.7 ms; 0% sub-frame launches; p90 156.6 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 161.5 ms; 0% sub-frame launches; p90 174.1 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 45.6 ms; 0% sub-frame launches; p90 55.3 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 233.7 ms; 0% sub-frame launches; p90 261.0 ms; n = 10 of 10 |
| WordCraft | prose-50kw | 153.3 ms; 0% sub-frame launches; p90 166.8 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | 25.3 ms; 30% sub-frame launches; p90 38.1 ms; n = 10 of 10 |
| Docen | prose-5kw | 50.9 ms; 0% sub-frame launches; p90 64.2 ms; n = 10 of 10 |
| Docxodus | prose-5kw | 324.1 ms; 0% sub-frame launches; p90 343.1 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 23.9 ms; 0% sub-frame launches; p90 29.7 ms; n = 10 of 10 |
| Folio | prose-5kw | 48.5 ms; 0% sub-frame launches; p90 54.4 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 18.6 ms; 20% sub-frame launches; p90 24.3 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 22.6 ms; 20% sub-frame launches; p90 31.1 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 125.7 ms; 0% sub-frame launches; p90 133.2 ms; n = 10 of 10 |
| WordCraft | prose-5kw | 132.5 ms; 0% sub-frame launches; p90 137.0 ms; n = 10 of 10 |

### C10 — scrolling

| Editor | Workload | C10 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) |
| Docen | complex-corpus | 18.5 ms; 50% sub-frame launches; p90 23.4 ms; n = 10 of 10 |
| Docxodus | complex-corpus | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 32.7 ms; 0% sub-frame launches; p90 40.9 ms; n = 10 of 10 |
| Folio | complex-corpus | < 1 frame (16.7 ms); 80% sub-frame launches; p90 20.4 ms; n = 10 of 10 |
| GenOffice | complex-corpus | < 1 frame (16.7 ms); 70% sub-frame launches; p90 18.0 ms; n = 10 of 10 |
| Plate.js | complex-corpus | < 1 frame (16.7 ms); 70% sub-frame launches; p90 17.6 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 20.5 ms; 20% sub-frame launches; p90 23.6 ms; n = 10 of 10 |
| WordCraft | complex-corpus | not reproduced (first 129.9 ms; second 149.6 ms) |
| canvas-editor + plugin | prose-250kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 22.5 ms; n = 10 of 10 |
| Docen | prose-250kw | 24.0 ms; 0% sub-frame launches; p90 28.5 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 62.4 ms; 0% sub-frame launches; p90 72.0 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 28.7 ms; 0% sub-frame launches; p90 34.5 ms; n = 10 of 10 |
| Folio | prose-250kw | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| GenOffice | prose-250kw | 63.0 ms; 0% sub-frame launches; p90 67.3 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 60.7 ms; 0% sub-frame launches; p90 66.7 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | 51.6 ms; 0% sub-frame launches; p90 58.7 ms; n = 10 of 10 |
| WordCraft | prose-250kw | 153.3 ms; 20% sub-frame launches; p90 190.2 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | < 1 frame (16.7 ms); 50% sub-frame launches; p90 18.5 ms; n = 10 of 10 |
| Docen | prose-500w | < 1 frame (16.7 ms); 70% sub-frame launches; p90 19.4 ms; n = 10 of 10 |
| Docxodus | prose-500w | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-500w | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.1 ms; n = 10 of 10 |
| Folio | prose-500w | < 1 frame (16.7 ms); 70% sub-frame launches; p90 20.2 ms; n = 10 of 10 |
| GenOffice | prose-500w | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| Plate.js | prose-500w | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| SuperDoc | prose-500w | < 1 frame (16.7 ms); 60% sub-frame launches; p90 26.5 ms; n = 10 of 10 |
| WordCraft | prose-500w | not reproduced (first 130.2 ms; second 194.5 ms); second: 1 of 10 launches failed: paint_witness_unavailable: 1 |
| canvas-editor + plugin | prose-50kw | < 1 frame (16.7 ms); 70% sub-frame launches; p90 22.3 ms; n = 10 of 10 |
| Docen | prose-50kw | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.3 ms; n = 10 of 10 |
| Docxodus | prose-50kw | < 1 frame (16.7 ms); 70% sub-frame launches; p90 20.7 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 32.0 ms; 0% sub-frame launches; p90 34.1 ms; n = 10 of 10 |
| Folio | prose-50kw | < 1 frame (16.7 ms); 50% sub-frame launches; p90 20.4 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 21.1 ms; 20% sub-frame launches; p90 27.4 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 19.0 ms; 20% sub-frame launches; p90 28.3 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 25.4 ms; 10% sub-frame launches; p90 29.4 ms; n = 10 of 10 |
| WordCraft | prose-50kw | not reproduced (first 130.7 ms; second < 1 frame (16.7 ms)) |
| canvas-editor + plugin | prose-5kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 19.9 ms; n = 10 of 10 |
| Docen | prose-5kw | < 1 frame (16.7 ms); 60% sub-frame launches; p90 30.7 ms; n = 10 of 10 |
| Docxodus | prose-5kw | < 1 frame (16.7 ms); 70% sub-frame launches; p90 17.3 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 26.0 ms; 0% sub-frame launches; p90 35.1 ms; n = 10 of 10 |
| Folio | prose-5kw | < 1 frame (16.7 ms); 80% sub-frame launches; p90 18.1 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 16.7 ms; 50% sub-frame launches; p90 20.2 ms; n = 10 of 10 |
| Plate.js | prose-5kw | < 1 frame (16.7 ms); 70% sub-frame launches; p90 17.7 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 21.7 ms; 0% sub-frame launches; p90 26.6 ms; n = 10 of 10 |
| WordCraft | prose-5kw | 154.0 ms; 20% sub-frame launches; p90 181.9 ms; n = 10 of 10 |

### C11 — initial layout

| Editor | Workload | C11 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Docen | complex-corpus | 1194.1 ms; 0% sub-frame launches; p90 1312.3 ms; n = 10 of 10 |
| Docxodus | complex-corpus | 3159.3 ms; 0% sub-frame launches; p90 3358.7 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 782.3 ms; 0% sub-frame launches; p90 853.9 ms; n = 10 of 10 |
| Folio | complex-corpus | 932.8 ms; 0% sub-frame launches; p90 1051.4 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 1051.0 ms; 0% sub-frame launches; p90 1085.6 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 910.5 ms; 0% sub-frame launches; p90 952.3 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 2752.1 ms; 0% sub-frame launches; p90 2877.1 ms; n = 10 of 10 |
| WordCraft | complex-corpus | 1391.4 ms; 0% sub-frame launches; p90 1463.6 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | 65698.0 ms; 0% sub-frame launches; p90 66493.3 ms; n = 10 of 10 |
| Docen | prose-250kw | 8616.8 ms; 0% sub-frame launches; p90 9820.5 ms; n = 10 of 10 |
| Docxodus | prose-250kw | 47249.2 ms; 0% sub-frame launches; p90 49098.6 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 2509.7 ms; 0% sub-frame launches; p90 2735.2 ms; n = 10 of 10 |
| Folio | prose-250kw | 4786.1 ms; 0% sub-frame launches; p90 4924.2 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 2093.3 ms; 0% sub-frame launches; p90 2192.1 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 19708.4 ms; 0% sub-frame launches; p90 21041.7 ms; n = 10 of 10; second: 1 of 10 launches failed: cpu_throttled: 1 |
| SuperDoc | prose-250kw | 16417.1 ms; 0% sub-frame launches; p90 17324.5 ms; n = 10 of 10 |
| WordCraft | prose-250kw | 2993.5 ms; 0% sub-frame launches; p90 3128.0 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500kw | 296906.5 ms; 0% sub-frame launches; p90 321937.8 ms; n = 10 of 10 |
| Docen | prose-500kw | not reproduced (first 22101.5 ms; second 26436.5 ms) |
| Docxodus | prose-500kw | 102371.8 ms; 0% sub-frame launches; p90 105635.2 ms; n = 10 of 10 |
| eigenpal | prose-500kw | 3992.8 ms; 0% sub-frame launches; p90 4110.0 ms; n = 10 of 10 |
| Folio | prose-500kw | 8284.5 ms; 0% sub-frame launches; p90 8477.1 ms; n = 10 of 10 |
| GenOffice | prose-500kw | 3226.0 ms; 0% sub-frame launches; p90 3795.1 ms; n = 10 of 10; second: 1 of 10 launches failed: paint_witness_unavailable: 1 |
| Plate.js | prose-500kw | 38457.7 ms; 0% sub-frame launches; p90 40120.4 ms; n = 10 of 10 |
| SuperDoc | prose-500kw | 29982.8 ms; 0% sub-frame launches; p90 31401.1 ms; n = 10 of 10 |
| WordCraft | prose-500kw | 4669.3 ms; 0% sub-frame launches; p90 4959.4 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | 335.3 ms; 0% sub-frame launches; p90 354.3 ms; n = 10 of 10 |
| Docen | prose-500w | 1069.0 ms; 0% sub-frame launches; p90 1089.3 ms; n = 10 of 10 |
| Docxodus | prose-500w | 2375.7 ms; 0% sub-frame launches; p90 2418.3 ms; n = 10 of 10 |
| eigenpal | prose-500w | 535.1 ms; 0% sub-frame launches; p90 553.9 ms; n = 10 of 10 |
| Folio | prose-500w | 768.8 ms; 0% sub-frame launches; p90 803.8 ms; n = 10 of 10 |
| GenOffice | prose-500w | 675.9 ms; 0% sub-frame launches; p90 724.5 ms; n = 10 of 10 |
| Plate.js | prose-500w | 735.7 ms; 0% sub-frame launches; p90 751.9 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 2327.6 ms; 0% sub-frame launches; p90 2387.1 ms; n = 10 of 10 |
| WordCraft | prose-500w | 1253.0 ms; 0% sub-frame launches; p90 1271.8 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | 8392.7 ms; 0% sub-frame launches; p90 8536.7 ms; n = 10 of 10 |
| Docen | prose-50kw | 2367.7 ms; 0% sub-frame launches; p90 2499.1 ms; n = 10 of 10 |
| Docxodus | prose-50kw | 11242.1 ms; 0% sub-frame launches; p90 11737.1 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 1151.1 ms; 0% sub-frame launches; p90 1285.7 ms; n = 10 of 10 |
| Folio | prose-50kw | 1866.6 ms; 0% sub-frame launches; p90 2055.0 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 1137.4 ms; 0% sub-frame launches; p90 1167.5 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 4711.1 ms; 0% sub-frame launches; p90 4860.0 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 5817.5 ms; 0% sub-frame launches; p90 6067.4 ms; n = 10 of 10 |
| WordCraft | prose-50kw | 1703.0 ms; 0% sub-frame launches; p90 1815.2 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | 1051.4 ms; 0% sub-frame launches; p90 1189.3 ms; n = 10 of 10 |
| Docen | prose-5kw | 1312.0 ms; 0% sub-frame launches; p90 1453.3 ms; n = 10 of 10 |
| Docxodus | prose-5kw | 3409.2 ms; 0% sub-frame launches; p90 4093.9 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 710.8 ms; 0% sub-frame launches; p90 799.7 ms; n = 10 of 10 |
| Folio | prose-5kw | 969.1 ms; 0% sub-frame launches; p90 1049.6 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 893.6 ms; 0% sub-frame launches; p90 997.8 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 1209.4 ms; 0% sub-frame launches; p90 1380.1 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 2926.6 ms; 0% sub-frame launches; p90 3376.9 ms; n = 10 of 10 |
| WordCraft | prose-5kw | 1369.0 ms; 0% sub-frame launches; p90 1519.9 ms; n = 10 of 10 |

### C12 — incremental reflow

| Editor | Workload | C12 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | complex-corpus | 48.4 ms; 0% sub-frame launches; p90 48.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 73.3 ms; 0% sub-frame launches; p90 82.1 ms; n = 10 of 10 |
| Folio | complex-corpus | 65.0 ms; 0% sub-frame launches; p90 66.9 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 32.1 ms; 0% sub-frame launches; p90 48.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 65.5 ms; 0% sub-frame launches; p90 65.6 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 373.4 ms; 0% sub-frame launches; p90 400.6 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-250kw | 156.8 ms; 0% sub-frame launches; p90 168.7 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 98.7 ms; 0% sub-frame launches; p90 117.0 ms; n = 10 of 10 |
| Folio | prose-250kw | 2464.2 ms; 0% sub-frame launches; p90 2561.6 ms; n = 10 of 10 |
| GenOffice | prose-250kw | not reproduced (first 2973.4 ms; second 2565.1 ms); first: 2 of 10 launches failed: recorded_move_before_input: 2; second: 1 of 10 launches failed: recorded_move_before_input: 1 |
| Plate.js | prose-250kw | 2248.1 ms; 0% sub-frame launches; p90 2348.1 ms; n = 10 of 10; second: 1 of 10 launches failed: cpu_throttled: 1 |
| SuperDoc | prose-250kw | 1456.8 ms; 0% sub-frame launches; p90 1483.6 ms; n = 10 of 10 |
| WordCraft | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500kw | 256.7 ms; 0% sub-frame launches; range 231.6 to 298.8 ms; n = 8 of 10; 2 of 10 launches failed: recorded_move_before_input: 2; second: 2 of 10 launches failed: recorded_move_before_input: 2 |
| eigenpal | prose-500kw | not reproduced (first 81.7 ms; second 98.5 ms) |
| Folio | prose-500kw | 4870.6 ms; 0% sub-frame launches; p90 4965.4 ms; n = 10 of 10 |
| GenOffice | prose-500kw | not reproduced (first 16029.7 ms; second 12039.7 ms); first: 4 of 10 launches failed: editor_timeout: 4; second: 2 of 10 launches failed: editor_timeout: 2 |
| Plate.js | prose-500kw | 4506.0 ms; 0% sub-frame launches; p90 4830.0 ms; n = 10 of 10 |
| SuperDoc | prose-500kw | not reproduced (first 2098.6 ms; second 1782.0 ms) |
| WordCraft | prose-500kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-500w | 48.8 ms; 0% sub-frame launches; p90 48.9 ms; n = 10 of 10 |
| eigenpal | prose-500w | 48.9 ms; 0% sub-frame launches; p90 48.9 ms; n = 10 of 10 |
| Folio | prose-500w | 48.8 ms; 0% sub-frame launches; p90 65.4 ms; n = 10 of 10 |
| GenOffice | prose-500w | 31.5 ms; 0% sub-frame launches; p90 32.0 ms; n = 10 of 10 |
| Plate.js | prose-500w | 48.7 ms; 0% sub-frame launches; p90 50.6 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 181.6 ms; 0% sub-frame launches; p90 182.1 ms; n = 10 of 10 |
| WordCraft | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-50kw | 64.5 ms; 0% sub-frame launches; p90 67.0 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 90.0 ms; 0% sub-frame launches; p90 98.3 ms; n = 10 of 10 |
| Folio | prose-50kw | 572.9 ms; 0% sub-frame launches; p90 599.7 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 173.6 ms; 0% sub-frame launches; p90 198.3 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 465.3 ms; 0% sub-frame launches; p90 483.4 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 906.0 ms; 0% sub-frame launches; p90 951.3 ms; n = 10 of 10 |
| WordCraft | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| canvas-editor + plugin | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docen | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |
| Docxodus | prose-5kw | 48.1 ms; 0% sub-frame launches; p90 48.7 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 65.4 ms; 0% sub-frame launches; p90 83.7 ms; n = 10 of 10 |
| Folio | prose-5kw | 123.4 ms; 0% sub-frame launches; p90 149.7 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 31.4 ms; 0% sub-frame launches; p90 31.8 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 115.4 ms; 0% sub-frame launches; p90 131.3 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 440.0 ms; 0% sub-frame launches; p90 548.5 ms; n = 10 of 10 |
| WordCraft | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) |

### C13 — global invalidation

not in these runs.

### C14 — large-document scaling

Each C14 size rung is a separate measure, and within a rung each clock is its own measure: `presented_frame` (document damage followed load; the sample ends at the first compositor screencast frame at or after the document became usable) and `usable_no_damage` (no damage followed; the sample ends at the DOM document-surface mark and is never labelled a compositor frame). Rungs and measures are never pooled. The damage window is 500 ms after a settled frame, widened by the clock's measured error; a frame recorded later, while the page kept the harness waiting, is not damage inside it (issue #203). The witness looks at the last 1,200 frames the recorder kept. The campaign's records do not count dropped frames, so where more than 1,200 arrived before the witness looked, a damage frame may be gone and the sample recorded as `usable_no_damage`; the figure is still the time the text appeared (issue #221). The two measures must not be read as the same thing: a `usable_no_damage` sample is the time the text appeared in the page, not the time the document was painted (C11 times the painted frame).

| Editor | Workload | Measure | C14 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | complex-corpus | presented_frame | 1729.7 ms; 0% sub-frame launches; p90 1812.7 ms; n = 10 of 10 |
| Folio | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) |
| SuperDoc | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | complex-corpus | presented_frame | 4739.3 ms; 0% sub-frame launches; p90 4852.1 ms; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | complex-corpus | usable_no_damage | 1168.8 ms; 0% sub-frame launches; p90 1280.0 ms; n = 10 of 10 |
| Docxodus | complex-corpus | usable_no_damage | 3072.1 ms; 0% sub-frame launches; p90 3288.2 ms; n = 10 of 10 |
| eigenpal | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | complex-corpus | usable_no_damage | 880.0 ms; 0% sub-frame launches; p90 993.1 ms; n = 10 of 10 |
| GenOffice | complex-corpus | usable_no_damage | 987.6 ms; 0% sub-frame launches; p90 1058.0 ms; n = 10 of 10 |
| Plate.js | complex-corpus | usable_no_damage | 879.5 ms; 0% sub-frame launches; p90 935.0 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | usable_no_damage | 2714.2 ms; 0% sub-frame launches; p90 3118.3 ms; n = 10 of 10 |
| WordCraft | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-250kw | presented_frame | 7066.0 ms; 0% sub-frame launches; p90 7858.8 ms; n = 10 of 10 |
| Folio | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons cpu_throttled: 1); second: not enough samples (n = 0 of 10; reasons none counted) |
| SuperDoc | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-250kw | presented_frame | 5642.9 ms; 0% sub-frame launches; p90 6318.6 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | usable_no_damage | 64270.6 ms; 0% sub-frame launches; p90 66537.1 ms; n = 10 of 10 |
| Docen | prose-250kw | usable_no_damage | not reproduced (first 8777.8 ms; second 7662.6 ms) |
| Docxodus | prose-250kw | usable_no_damage | 45683.0 ms; 0% sub-frame launches; p90 48348.4 ms; n = 10 of 10 |
| eigenpal | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-250kw | usable_no_damage | 4607.7 ms; 0% sub-frame launches; p90 4984.5 ms; n = 10 of 10 |
| GenOffice | prose-250kw | usable_no_damage | 1989.5 ms; 0% sub-frame launches; p90 2147.2 ms; n = 10 of 10 |
| Plate.js | prose-250kw | usable_no_damage | 18349.9 ms; 0% sub-frame launches; range 17977.3 to 20259.8 ms; n = 9 of 10; 1 of 10 launches failed: cpu_throttled: 1 |
| SuperDoc | prose-250kw | usable_no_damage | 15720.4 ms; 0% sub-frame launches; p90 16966.7 ms; n = 10 of 10 |
| WordCraft | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docen | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-500kw | presented_frame | 13100.4 ms; 0% sub-frame launches; p90 13715.1 ms; n = 10 of 10 |
| Folio | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| SuperDoc | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-500kw | presented_frame | 7450.6 ms; 0% sub-frame launches; p90 7957.7 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500kw | usable_no_damage | 278069.6 ms; 0% sub-frame launches; p90 285536.9 ms; n = 10 of 10 |
| Docen | prose-500kw | usable_no_damage | 22252.6 ms; 0% sub-frame launches; p90 28188.2 ms; n = 10 of 10 |
| Docxodus | prose-500kw | usable_no_damage | 99356.5 ms; 0% sub-frame launches; p90 101763.7 ms; n = 10 of 10 |
| eigenpal | prose-500kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-500kw | usable_no_damage | 8194.5 ms; 0% sub-frame launches; p90 8350.4 ms; n = 10 of 10 |
| GenOffice | prose-500kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) |
| Plate.js | prose-500kw | usable_no_damage | 38348.7 ms; 0% sub-frame launches; p90 39007.2 ms; n = 10 of 10 |
| SuperDoc | prose-500kw | usable_no_damage | 29601.3 ms; 0% sub-frame launches; p90 30098.6 ms; n = 10 of 10 |
| WordCraft | prose-500kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-500w | presented_frame | 1730.2 ms; 0% sub-frame launches; p90 1831.3 ms; n = 10 of 10 |
| Folio | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) |
| SuperDoc | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-500w | presented_frame | 4699.3 ms; 0% sub-frame launches; p90 4807.0 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | usable_no_damage | 335.8 ms; 0% sub-frame launches; p90 374.3 ms; n = 10 of 10 |
| Docen | prose-500w | usable_no_damage | 1121.4 ms; 0% sub-frame launches; p90 1326.9 ms; n = 10 of 10 |
| Docxodus | prose-500w | usable_no_damage | 2409.6 ms; 0% sub-frame launches; p90 2838.1 ms; n = 10 of 10 |
| eigenpal | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-500w | usable_no_damage | 796.8 ms; 0% sub-frame launches; p90 882.4 ms; n = 10 of 10 |
| GenOffice | prose-500w | usable_no_damage | 685.1 ms; 0% sub-frame launches; p90 754.2 ms; n = 10 of 10 |
| Plate.js | prose-500w | usable_no_damage | 742.9 ms; 0% sub-frame launches; p90 819.1 ms; n = 10 of 10 |
| SuperDoc | prose-500w | usable_no_damage | 2355.4 ms; 0% sub-frame launches; p90 2514.4 ms; n = 10 of 10 |
| WordCraft | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-50kw | presented_frame | 2394.4 ms; 0% sub-frame launches; p90 3187.6 ms; n = 10 of 10 |
| Folio | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) |
| SuperDoc | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-50kw | presented_frame | 4420.9 ms; 0% sub-frame launches; p90 4921.5 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | usable_no_damage | 7971.1 ms; 0% sub-frame launches; p90 8406.2 ms; n = 10 of 10 |
| Docen | prose-50kw | usable_no_damage | 2273.2 ms; 0% sub-frame launches; p90 2508.7 ms; n = 10 of 10 |
| Docxodus | prose-50kw | usable_no_damage | 10307.8 ms; 0% sub-frame launches; p90 11209.4 ms; n = 10 of 10 |
| eigenpal | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-50kw | usable_no_damage | 1752.2 ms; 0% sub-frame launches; p90 1860.9 ms; n = 10 of 10 |
| GenOffice | prose-50kw | usable_no_damage | 1030.8 ms; 0% sub-frame launches; p90 1157.2 ms; n = 10 of 10 |
| Plate.js | prose-50kw | usable_no_damage | 4452.7 ms; 0% sub-frame launches; p90 4808.8 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | usable_no_damage | 5623.8 ms; 0% sub-frame launches; p90 5938.3 ms; n = 10 of 10 |
| WordCraft | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) |
| Docen | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-5kw | presented_frame | 1935.8 ms; 0% sub-frame launches; p90 2036.6 ms; n = 10 of 10 |
| Folio | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) |
| SuperDoc | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | prose-5kw | presented_frame | 4333.3 ms; 0% sub-frame launches; p90 4891.1 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | usable_no_damage | 1001.4 ms; 0% sub-frame launches; p90 1112.2 ms; n = 10 of 10 |
| Docen | prose-5kw | usable_no_damage | 1311.8 ms; 0% sub-frame launches; p90 1419.3 ms; n = 10 of 10 |
| Docxodus | prose-5kw | usable_no_damage | 3295.5 ms; 0% sub-frame launches; p90 3621.9 ms; n = 10 of 10 |
| eigenpal | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | prose-5kw | usable_no_damage | 928.0 ms; 0% sub-frame launches; p90 1009.7 ms; n = 10 of 10 |
| GenOffice | prose-5kw | usable_no_damage | 911.5 ms; 0% sub-frame launches; p90 996.8 ms; n = 10 of 10 |
| Plate.js | prose-5kw | usable_no_damage | 1165.8 ms; 0% sub-frame launches; p90 1290.4 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | usable_no_damage | 2860.0 ms; 0% sub-frame launches; p90 3015.1 ms; n = 10 of 10 |
| WordCraft | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |

### C15 — search and replace

Each C15 step is a separate measure; steps are never pooled.

| Editor | Workload | Measure | C15 |
|---|---|---|---|
| canvas-editor + plugin | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docen | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docxodus | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| eigenpal | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Folio | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| GenOffice | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Plate.js | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| SuperDoc | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| WordCraft | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| canvas-editor + plugin | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docen | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docxodus | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| eigenpal | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Folio | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| GenOffice | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Plate.js | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| SuperDoc | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| WordCraft | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| canvas-editor + plugin | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docen | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docxodus | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| eigenpal | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Folio | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| GenOffice | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Plate.js | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| SuperDoc | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| WordCraft | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| canvas-editor + plugin | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docen | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Docxodus | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| eigenpal | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Folio | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| GenOffice | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| Plate.js | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| SuperDoc | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |
| WordCraft | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) |

### C17 — memory by phase

Memory is the resident set size summed over the browser's process tree, in MiB; it counts a page shared by two processes once for each. The phases are: ready, read once the editor's ready signal (see C03) has been raised and the settle delay the harness gives that editor has passed; after a fixed burst of edits, once the harness has verified them in the document; and quiescent, which is a fixed wait, 2 seconds after the burst, with no test that the page is idle.

A ready reading is printed only where the harness checked the length of the mounted text against the document. In this campaign's records it checked the opening text only, or nothing, for Docxodus, Folio, GenOffice, SuperDoc and WordCraft, so at their ready reading the document is not known to be loaded, and those cells read "unverified": an editor can raise its ready signal before a long document is in memory. Their later phases are read after the burst was typed and are printed.

canvas-editor has no figure for the complex document, which it fails to open in every lane, or for 250,000 words, where its page crashed or the burst did not finish in the time allowed.

| Editor | Workload | Measure | C17 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | complex-corpus | after_edit_burst | 781.3 MiB; p90 806.0 MiB; n = 10 of 10 |
| Docxodus | complex-corpus | after_edit_burst | 715.3 MiB; p90 717.6 MiB; n = 10 of 10 |
| eigenpal | complex-corpus | after_edit_burst | 642.5 MiB; p90 650.3 MiB; n = 10 of 10 |
| Folio | complex-corpus | after_edit_burst | 595.9 MiB; p90 598.2 MiB; n = 10 of 10 |
| GenOffice | complex-corpus | after_edit_burst | 629.1 MiB; p90 633.5 MiB; n = 10 of 10 |
| Plate.js | complex-corpus | after_edit_burst | 629.2 MiB; p90 631.1 MiB; n = 10 of 10 |
| SuperDoc | complex-corpus | after_edit_burst | 689.3 MiB; p90 693.3 MiB; n = 10 of 10 |
| WordCraft | complex-corpus | after_edit_burst | 1137.6 MiB; p90 1157.2 MiB; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | complex-corpus | quiescent | 782.6 MiB; p90 806.8 MiB; n = 10 of 10 |
| Docxodus | complex-corpus | quiescent | 715.5 MiB; p90 717.8 MiB; n = 10 of 10 |
| eigenpal | complex-corpus | quiescent | 645.8 MiB; p90 650.9 MiB; n = 10 of 10 |
| Folio | complex-corpus | quiescent | 597.1 MiB; p90 599.1 MiB; n = 10 of 10 |
| GenOffice | complex-corpus | quiescent | 638.8 MiB; p90 643.2 MiB; n = 10 of 10 |
| Plate.js | complex-corpus | quiescent | 629.3 MiB; p90 631.1 MiB; n = 10 of 10 |
| SuperDoc | complex-corpus | quiescent | 696.0 MiB; p90 700.5 MiB; n = 10 of 10 |
| WordCraft | complex-corpus | quiescent | 1137.8 MiB; p90 1155.8 MiB; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | complex-corpus | ready | 701.9 MiB; p90 703.1 MiB; n = 10 of 10 |
| Docxodus | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| eigenpal | complex-corpus | ready | 626.2 MiB; p90 628.6 MiB; n = 10 of 10 |
| Folio | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | complex-corpus | ready | 527.3 MiB; p90 529.7 MiB; n = 10 of 10 |
| SuperDoc | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| WordCraft | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-250kw | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | prose-250kw | after_edit_burst | 7544.8 MiB; p90 8603.7 MiB; n = 10 of 10 |
| Docxodus | prose-250kw | after_edit_burst | 1917.1 MiB; p90 1934.3 MiB; n = 10 of 10 |
| eigenpal | prose-250kw | after_edit_burst | 996.1 MiB; p90 1009.7 MiB; n = 10 of 10 |
| Folio | prose-250kw | after_edit_burst | 2117.8 MiB; p90 2123.9 MiB; n = 10 of 10 |
| GenOffice | prose-250kw | after_edit_burst | 2021.6 MiB; p90 2141.5 MiB; n = 10 of 10 |
| Plate.js | prose-250kw | after_edit_burst | 2053.7 MiB; p90 2072.3 MiB; n = 10 of 10 |
| SuperDoc | prose-250kw | after_edit_burst | 1359.7 MiB; p90 1421.2 MiB; n = 10 of 10 |
| WordCraft | prose-250kw | after_edit_burst | 1336.3 MiB; p90 1341.7 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | prose-250kw | quiescent | 7746.8 MiB; p90 8808.2 MiB; n = 10 of 10 |
| Docxodus | prose-250kw | quiescent | 1914.5 MiB; p90 1920.4 MiB; n = 10 of 10 |
| eigenpal | prose-250kw | quiescent | 996.2 MiB; p90 1009.9 MiB; n = 10 of 10 |
| Folio | prose-250kw | quiescent | 1938.1 MiB; p90 1948.9 MiB; n = 10 of 10 |
| GenOffice | prose-250kw | quiescent | 2211.7 MiB; p90 2302.1 MiB; n = 10 of 10 |
| Plate.js | prose-250kw | quiescent | 2053.7 MiB; p90 2072.4 MiB; n = 10 of 10 |
| SuperDoc | prose-250kw | quiescent | 1360.4 MiB; p90 1421.8 MiB; n = 10 of 10 |
| WordCraft | prose-250kw | quiescent | 1336.5 MiB; p90 1341.9 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) |
| Docen | prose-250kw | ready | 4145.4 MiB; p90 4173.3 MiB; n = 10 of 10 |
| Docxodus | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| eigenpal | prose-250kw | ready | 890.8 MiB; p90 892.4 MiB; n = 10 of 10 |
| Folio | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | prose-250kw | ready | 1907.0 MiB; p90 1959.3 MiB; n = 10 of 10 |
| SuperDoc | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| WordCraft | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-500w | after_edit_burst | 858.5 MiB; p90 908.1 MiB; n = 10 of 10 |
| Docen | prose-500w | after_edit_burst | 698.5 MiB; p90 707.3 MiB; n = 10 of 10 |
| Docxodus | prose-500w | after_edit_burst | 695.2 MiB; p90 698.8 MiB; n = 10 of 10 |
| eigenpal | prose-500w | after_edit_burst | 663.0 MiB; p90 675.2 MiB; n = 10 of 10 |
| Folio | prose-500w | after_edit_burst | 563.3 MiB; p90 567.9 MiB; n = 10 of 10 |
| GenOffice | prose-500w | after_edit_burst | 583.7 MiB; p90 586.6 MiB; n = 10 of 10 |
| Plate.js | prose-500w | after_edit_burst | 620.3 MiB; p90 637.2 MiB; n = 10 of 10 |
| SuperDoc | prose-500w | after_edit_burst | 656.0 MiB; p90 659.6 MiB; n = 10 of 10 |
| WordCraft | prose-500w | after_edit_burst | 1143.1 MiB; p90 1157.7 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | quiescent | 858.4 MiB; p90 908.7 MiB; n = 10 of 10 |
| Docen | prose-500w | quiescent | 699.3 MiB; p90 708.1 MiB; n = 10 of 10 |
| Docxodus | prose-500w | quiescent | 695.3 MiB; p90 699.0 MiB; n = 10 of 10 |
| eigenpal | prose-500w | quiescent | 660.5 MiB; p90 674.8 MiB; n = 10 of 10 |
| Folio | prose-500w | quiescent | 564.4 MiB; p90 568.9 MiB; n = 10 of 10 |
| GenOffice | prose-500w | quiescent | 584.8 MiB; p90 587.2 MiB; n = 10 of 10 |
| Plate.js | prose-500w | quiescent | 620.3 MiB; p90 637.2 MiB; n = 10 of 10 |
| SuperDoc | prose-500w | quiescent | 659.8 MiB; p90 661.0 MiB; n = 10 of 10 |
| WordCraft | prose-500w | quiescent | 1142.7 MiB; p90 1157.7 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | ready | 530.2 MiB; p90 534.8 MiB; n = 10 of 10 |
| Docen | prose-500w | ready | 655.8 MiB; p90 663.1 MiB; n = 10 of 10 |
| Docxodus | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| eigenpal | prose-500w | ready | 608.4 MiB; p90 610.8 MiB; n = 10 of 10 |
| Folio | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | prose-500w | ready | 508.7 MiB; p90 510.0 MiB; n = 10 of 10 |
| SuperDoc | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| WordCraft | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-50kw | after_edit_burst | 6948.9 MiB; range 6833.8 to 10689.3 MiB; n = 8 of 10; 2 of 10 launches failed: editor_timeout: 2; second: 1 of 10 launches failed: editor_timeout: 1 |
| Docen | prose-50kw | after_edit_burst | 1936.7 MiB; p90 1951.5 MiB; n = 10 of 10 |
| Docxodus | prose-50kw | after_edit_burst | 989.1 MiB; p90 1022.7 MiB; n = 10 of 10 |
| eigenpal | prose-50kw | after_edit_burst | 758.8 MiB; p90 764.1 MiB; n = 10 of 10 |
| Folio | prose-50kw | after_edit_burst | 870.8 MiB; p90 900.1 MiB; n = 10 of 10 |
| GenOffice | prose-50kw | after_edit_burst | 964.3 MiB; p90 972.0 MiB; n = 10 of 10 |
| Plate.js | prose-50kw | after_edit_burst | 908.0 MiB; p90 910.2 MiB; n = 10 of 10 |
| SuperDoc | prose-50kw | after_edit_burst | 899.1 MiB; p90 906.8 MiB; n = 10 of 10 |
| WordCraft | prose-50kw | after_edit_burst | 1173.7 MiB; p90 1195.5 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | quiescent | 6916.1 MiB; range 6789.1 to 10640.4 MiB; n = 8 of 10; 2 of 10 launches failed: editor_timeout: 2; second: 1 of 10 launches failed: editor_timeout: 1 |
| Docen | prose-50kw | quiescent | 1948.4 MiB; p90 1971.3 MiB; n = 10 of 10 |
| Docxodus | prose-50kw | quiescent | 989.1 MiB; p90 1022.7 MiB; n = 10 of 10 |
| eigenpal | prose-50kw | quiescent | 758.9 MiB; p90 763.7 MiB; n = 10 of 10 |
| Folio | prose-50kw | quiescent | 876.9 MiB; p90 906.2 MiB; n = 10 of 10 |
| GenOffice | prose-50kw | quiescent | 968.6 MiB; p90 974.5 MiB; n = 10 of 10 |
| Plate.js | prose-50kw | quiescent | 908.0 MiB; p90 910.2 MiB; n = 10 of 10 |
| SuperDoc | prose-50kw | quiescent | 910.5 MiB; p90 917.7 MiB; n = 10 of 10 |
| WordCraft | prose-50kw | quiescent | 1173.6 MiB; p90 1193.1 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | ready | 1941.1 MiB; range 1683.8 to 2051.9 MiB; n = 8 of 10; 2 of 10 launches failed: editor_timeout: 2; second: 1 of 10 launches failed: editor_timeout: 1 |
| Docen | prose-50kw | ready | 1400.1 MiB; p90 1403.1 MiB; n = 10 of 10 |
| Docxodus | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| eigenpal | prose-50kw | ready | 691.8 MiB; p90 694.2 MiB; n = 10 of 10 |
| Folio | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | prose-50kw | ready | 827.9 MiB; p90 830.7 MiB; n = 10 of 10 |
| SuperDoc | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| WordCraft | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| canvas-editor + plugin | prose-5kw | after_edit_burst | 1770.9 MiB; p90 2311.8 MiB; n = 10 of 10 |
| Docen | prose-5kw | after_edit_burst | 949.9 MiB; p90 964.7 MiB; n = 10 of 10 |
| Docxodus | prose-5kw | after_edit_burst | 732.5 MiB; p90 734.4 MiB; n = 10 of 10 |
| eigenpal | prose-5kw | after_edit_burst | 681.2 MiB; p90 700.4 MiB; n = 10 of 10 |
| Folio | prose-5kw | after_edit_burst | 594.5 MiB; p90 607.1 MiB; n = 10 of 10 |
| GenOffice | prose-5kw | after_edit_burst | 647.9 MiB; p90 659.7 MiB; n = 10 of 10 |
| Plate.js | prose-5kw | after_edit_burst | 674.3 MiB; p90 678.0 MiB; n = 10 of 10 |
| SuperDoc | prose-5kw | after_edit_burst | 731.0 MiB; p90 735.7 MiB; n = 10 of 10 |
| WordCraft | prose-5kw | after_edit_burst | 1145.8 MiB; p90 1162.1 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | quiescent | 1766.8 MiB; p90 2306.0 MiB; n = 10 of 10 |
| Docen | prose-5kw | quiescent | 945.3 MiB; p90 948.7 MiB; n = 10 of 10 |
| Docxodus | prose-5kw | quiescent | 732.6 MiB; p90 734.6 MiB; n = 10 of 10 |
| eigenpal | prose-5kw | quiescent | 679.0 MiB; p90 696.6 MiB; n = 10 of 10 |
| Folio | prose-5kw | quiescent | 602.9 MiB; p90 615.8 MiB; n = 10 of 10 |
| GenOffice | prose-5kw | quiescent | 648.7 MiB; p90 659.7 MiB; n = 10 of 10 |
| Plate.js | prose-5kw | quiescent | 674.4 MiB; p90 678.1 MiB; n = 10 of 10 |
| SuperDoc | prose-5kw | quiescent | 771.5 MiB; p90 774.7 MiB; n = 10 of 10 |
| WordCraft | prose-5kw | quiescent | 1145.9 MiB; p90 1162.1 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | ready | 710.0 MiB; p90 713.5 MiB; n = 10 of 10 |
| Docen | prose-5kw | ready | 749.0 MiB; p90 750.9 MiB; n = 10 of 10 |
| Docxodus | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| eigenpal | prose-5kw | ready | 636.7 MiB; p90 638.4 MiB; n = 10 of 10 |
| Folio | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| GenOffice | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| Plate.js | prose-5kw | ready | 561.3 MiB; p90 564.5 MiB; n = 10 of 10 |
| SuperDoc | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |
| WordCraft | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) |

### C19 — browser memory after the page is closed (not published)

C19 was meant to show memory an editor leaves behind. The harness read the browser's process tree 1 second and 5 seconds after closing the editor's page, and took no reading of an empty browser to subtract. What it read is therefore the browser itself, about the same for every editor and document size, and it cannot be attributed to an editor. No table is printed. In these runs the seed medians of the 43 editor and document cells that reproduced lay between 318.1 MiB and 362.5 MiB. The readings are in the dataset.

### B8 — resources while opening and editing

**B8 — resources while opening and editing.** One fresh browser per launch opens the document, waits until the editor is idle, types sixteen characters into a body line on the first screen, and waits again. CPU is the processor time of the whole browser process tree: to open (from navigation until idle, including work an editor does after it reports ready), during the edit (the keystrokes plus half a second), and while settling afterwards. The memory column is the highest reading of that tree's resident memory: it is read when the load and the edit start and end and every half second while the page settles, so a higher moment in the middle of a long load or edit is not seen; a page shared by two processes counts once for each. An edit counts only when it is verified in the document: the text of the block at the caret, read from the page or from the editor's model, gained exactly the typed text; WordCraft, which puts no document text in the page, is verified by its own modified flag. An editor still working when a 30-second cap ends never went idle, even in one launch: the CPU columns that wait would end are not printed, because they would time the cap, and a note gives what it used up to its ready signal, how far its memory readings ran and, where every kept launch recorded its processes, how the capped wait divides between the browser's GPU process (the one that draws; on this host it draws in software) and the page's own process. The complex document is loaded without its read-only protection, which the editors honour.

Each cell shows the first seed's median and the second seed's median. A figure is printed as a result only when the two agree within 10 percent (20 ms for CPU); a cell that does not agree says so and gives both medians and the lowest and highest launch, so that what was read is not hidden. The CPU counters advance in steps of 10 ms, so a cell of a few tens of milliseconds is at the counter's resolution. The host has no graphics processor: what an editor draws is drawn by the processor and counts as CPU.

### 500 words

| Editor | CPU to open | CPU of the edit | CPU settling after the edit | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| canvas-editor + plugin | 485 ms / 490 ms | 1.33 s / 1.30 s | 65 ms / 45 ms | 617.8 MiB / 616.5 MiB | n = 10, 10 |
| Docen | 1.66 s / 1.63 s | 385 ms / 380 ms | 30 ms / 15 ms | 659.4 MiB / 659.1 MiB | n = 10, 10 |
| Docxodus | 4.30 s / 4.29 s | 40 ms / 35 ms | 0 ms / 0 ms | 742.9 MiB / 743.6 MiB | n = 10, 10 |
| eigenpal | 1.47 s / 1.43 s | not reproduced (first 145 ms; second 115 ms; launches 100 ms to 230 ms) | 95 ms / 75 ms | 609.5 MiB / 610.2 MiB | n = 10, 10 |
| Folio | 2.17 s / 2.25 s | 245 ms / 240 ms | 45 ms / 30 ms | 543.3 MiB / 541.5 MiB | n = 10, 10 |
| GenOffice | 1.27 s / 1.26 s | 165 ms / 185 ms | 10 ms / 10 ms | 551.4 MiB / 550.0 MiB | n = 10, 10 |
| Plate.js | 1.02 s / 1.00 s | 480 ms / 485 ms | 15 ms / 15 ms | 530.5 MiB / 530.9 MiB | n = 10, 10 |
| SuperDoc | 2.90 s / 2.89 s | 335 ms / 315 ms | 65 ms / 60 ms | 625.2 MiB / 625.4 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 928.7 MiB / 961.7 MiB | n = 10, 10 |

Not published or flagged:

- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal it used 6.51 s / 6.62 s of processor time; in the capped wait that followed, 75.17 s / 76.25 s. Of the capped wait, the browser's GPU process used 70.94 s / 73.50 s and the page's own process 4.17 s / 3.71 s (not reproduced); the page had 162 / 167 long tasks, 13.25 s / 13.48 s in all. Its memory readings ran from 887.4 MiB to 982.2 MiB across the kept launches.

### 5,000 words

| Editor | CPU to open | CPU of the edit | CPU settling after the edit | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| canvas-editor + plugin | 1.25 s / 1.25 s | 7.29 s / 7.33 s | 50 ms / 40 ms | 926.3 MiB / 931.8 MiB | n = 10, 10 |
| Docen | 2.12 s / 2.08 s | 945 ms / 890 ms | 45 ms / 30 ms | 765.5 MiB / 757.2 MiB | n = 10, 10 |
| Docxodus | 6.16 s / 6.11 s | 30 ms / 30 ms | 10 ms / 0 ms | 781.7 MiB / 785.0 MiB | n = 10, 10 |
| eigenpal | 2.05 s / 2.00 s | 120 ms / 120 ms | 90 ms / 70 ms | 637.4 MiB / 636.5 MiB | n = 10, 10 |
| Folio | 2.46 s / 2.53 s | 360 ms / 355 ms | 40 ms / 30 ms | 571.9 MiB / 570.4 MiB | n = 10, 10 |
| GenOffice | 1.70 s / 1.67 s | 350 ms / 350 ms | 20 ms / 10 ms | 572.8 MiB / 572.3 MiB | n = 10, 10 |
| Plate.js | 1.89 s / 1.90 s | 595 ms / 610 ms | 10 ms / 15 ms | 559.2 MiB / 559.1 MiB | n = 10, 10 |
| SuperDoc | 3.85 s / 3.76 s | 780 ms / 800 ms | 40 ms / 30 ms | 725.5 MiB / 725.3 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 927.4 MiB / 963.2 MiB | n = 10, 10 |

Not published or flagged:

- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal it used 6.41 s / 6.43 s of processor time; in the capped wait that followed, 76.61 s / 76.52 s. Of the capped wait, the browser's GPU process used 72.45 s / 73.11 s and the page's own process 4.02 s / 3.85 s; the page had 167 / 166 long tasks, 13.32 s / 13.41 s in all. Its memory readings ran from 884.3 MiB to 968.5 MiB across the kept launches.

### 50,000 words

| Editor | CPU to open | CPU of the edit | CPU settling after the edit | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| canvas-editor + plugin | 7.20 s / 6.92 s | 67.17 s / 65.00 s | 60 ms / 45 ms | not reproduced (first 3772.6 MiB; second 4528.6 MiB; launches 3427.5 MiB to 5137.1 MiB) | n = 10, 10 |
| Docen | 5.07 s / 4.87 s | 10.68 s / 10.24 s | not reproduced (first 200 ms; second 50 ms; launches 30 ms to 250 ms) | 1595.3 MiB / 1595.5 MiB | n = 10, 10 |
| Docxodus | 19.64 s / 19.00 s | 40 ms / 40 ms | 5 ms / 5 ms | 1060.3 MiB / 1061.7 MiB | n = 10, 10 |
| eigenpal | 3.98 s / 3.83 s | 180 ms / 160 ms | 40 ms / 40 ms | 691.9 MiB / 692.0 MiB | n = 10, 10 |
| Folio | 3.88 s / 3.69 s | 1.98 s / 1.82 s | not reproduced (first 55 ms; second 30 ms; launches 20 ms to 70 ms) | 720.9 MiB / 716.2 MiB | n = 10, 10 |
| GenOffice | 4.70 s / 4.50 s | 3.37 s / 3.21 s | 20 ms / 20 ms | 833.7 MiB / 827.9 MiB | n = 10, 10 |
| Plate.js | 6.91 s / 6.66 s | 1.64 s / 1.56 s | 20 ms / 5 ms | 820.1 MiB / 821.3 MiB | n = 10, 10 |
| SuperDoc | 8.71 s / 8.20 s | 1.21 s / 1.18 s | not reproduced (first 85 ms; second 50 ms; launches 40 ms to 130 ms) | 889.4 MiB / 888.0 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 931.3 MiB / 919.7 MiB | n = 10, 10 |

Not published or flagged:

- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal it used 6.24 s / 6.17 s of processor time; in the capped wait that followed, 75.34 s / 76.23 s. Of the capped wait, the browser's GPU process used 71.89 s / 73.33 s and the page's own process 4.33 s / 3.88 s (not reproduced); the page had 160 / 164 long tasks, 13.24 s / 13.37 s in all. Its memory readings ran from 904.7 MiB to 945.8 MiB across the kept launches.

### 250,000 words

| Editor | CPU to open | CPU of the edit | CPU settling after the edit | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| canvas-editor + plugin | 53.88 s / 54.72 s | 503.49 s / 507.64 s | 60 ms / 40 ms | 9253.8 MiB / 9221.4 MiB | n = 10, 10 |
| Docen | 20.66 s / 21.16 s | 160.65 s / 167.09 s | not reproduced (first 1.38 s; second 70 ms; launches 30 ms to 2.31 s) | not reproduced (first 6956.0 MiB; second 5754.9 MiB; launches 5092.8 MiB to 8062.7 MiB) | n = 10, 10 |
| Docxodus | 106.25 s / 108.61 s | 60 ms / 50 ms | 0 ms / 0 ms | 2039.6 MiB / 2035.1 MiB | n = 10, 10 |
| eigenpal | 9.60 s / 9.76 s | 230 ms / 225 ms | not reproduced (first 35 ms; second 10 ms; launches 0 ms to 80 ms) | 890.1 MiB / 889.1 MiB | n = 10, 10 |
| Folio | 7.63 s / 7.64 s | 9.02 s / 9.52 s | 55 ms / 60 ms | 1273.4 MiB / 1274.6 MiB | n = 10, 10 |
| GenOffice | 24.93 s / 24.80 s | 51.87 s / 54.55 s | not reproduced (first 2.00 s; second 1.73 s; launches 1.59 s to 2.10 s) | 1815.7 MiB / 1733.5 MiB | n = 10, 10 |
| Plate.js | 28.06 s / 28.32 s | 2.19 s / 2.31 s | 30 ms / 20 ms | 1838.7 MiB / 1811.7 MiB | n = 10, 7 |
| SuperDoc | 20.61 s / 20.68 s | not reproduced (first 1.34 s; second 1.67 s; launches 960 ms to 1.77 s) | 80 ms / 60 ms | 1220.7 MiB / 1231.9 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 1073.5 MiB / 1008.8 MiB | n = 10, 10 |

Not published or flagged:

- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal its processor time did not reproduce between the seeds; in the capped wait that followed it used 66.44 s / 68.93 s. Of the capped wait, the browser's GPU process used 62.22 s / 64.61 s and the page's own process 4.67 s / 4.45 s; the page had 141 / 144 long tasks, 12.42 s / 12.38 s in all. Its memory readings ran from 984.7 MiB to 1114.7 MiB across the kept launches.

### Complex document

| Editor | CPU to open | CPU of the edit | CPU settling after the edit | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| Docen | 1.83 s / 1.98 s | 690 ms / 745 ms | 40 ms / 35 ms | 703.1 MiB / 698.9 MiB | n = 10, 10 |
| Docxodus | 5.55 s / 5.72 s | 30 ms / 30 ms | 10 ms / 10 ms | 763.9 MiB / 766.6 MiB | n = 10, 10 |
| eigenpal | 1.88 s / 2.00 s | 105 ms / 120 ms | not reproduced (first 75 ms; second 30 ms; launches 0 ms to 90 ms) | 629.8 MiB / 630.5 MiB | n = 10, 10 |
| Folio | 2.45 s / 2.64 s | not reproduced (first 460 ms; second 520 ms; launches 430 ms to 640 ms) | 40 ms / 45 ms | 556.6 MiB / 556.6 MiB | n = 10, 10 |
| GenOffice | 1.79 s / 1.86 s | not reproduced (first 330 ms; second 380 ms; launches 300 ms to 450 ms) | 20 ms / 10 ms | 596.2 MiB / 597.1 MiB | n = 10, 10 |
| Plate.js | 1.21 s / 1.29 s | not reproduced (first 420 ms; second 470 ms; launches 390 ms to 550 ms) | 10 ms / 15 ms | 525.9 MiB / 529.4 MiB | n = 10, 10 |
| SuperDoc | 3.54 s / 3.42 s | 460 ms / 480 ms | 65 ms / 55 ms | 662.6 MiB / 658.2 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 902.9 MiB / 964.3 MiB | n = 10, 10 |

Not published or flagged:

- canvas-editor + plugin: first seed: 0 of 10 launches kept (editor_load_failed 10); TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:33203/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:33203; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:33591/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:33591; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:33871/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:33871; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:35259/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:35259; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:39261/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:39261; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:40981/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:40981; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:42967/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:42967; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:43905/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:43905; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:44751/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:44751; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:45541/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:45541; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:47947/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:47947; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:49509/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:49509; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:49717/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:49717; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:50287/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:50287; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:52025/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:52025; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:53355/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:53355; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:53659/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:53659; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:56581/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:56581; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:59035/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:59035; TypeError: Cannot read properties of undefined (reading 'width')
    at pa.computeRowColInfo (http://127.0.0.1:59713/assets/index-L94yjsVH.js:58:70981)
    at sr.computeRowList (http://127.0.0.1:59713.
- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal it used 6.47 s / 6.57 s of processor time; in the capped wait that followed, 66.16 s / 69.94 s. Of the capped wait, the browser's GPU process used 61.91 s / 66.64 s and the page's own process 4.04 s / 3.94 s; the page had 133 / 138 long tasks, 12.51 s / 12.61 s in all. Its memory readings ran from 885.7 MiB to 970.2 MiB across the kept launches.

The settling window is not a fixed length: it ends at the first half-second poll at which two seconds have passed without a long task, and the polls themselves cost processor time. Across the 39 cells with a settling figure, the first seed's median is the higher in 27 and the lower in 4. A difference of a few tens of milliseconds in that column cannot be told apart from the window and the 10 ms counter.

### B9 — typing marathon

Throughput sessions publish chars/s and resources. Latency sessions publish load and key-to-paint with witness counts; their instrumented throughput and resources are withheld.

canvas-editor + plugin — latency: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 30,939, 30,748; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 29,447, 29,128 Latency-session throughput and resources are instrumented; figures withheld.

canvas-editor + plugin — throughput: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 29,470, 29,907; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 30,276, 29,993

Docen — latency: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 81,225, 81,225; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 32,652, 33,292 Latency-session throughput and resources are instrumented; figures withheld.

Docen — throughput: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 35,689, 34,263; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 38,838, 38,915

Docxodus — latency: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 81,225, 81,225; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 81,225, 81,225 Latency-session throughput and resources are instrumented; figures withheld.

Docxodus — throughput; first n = 6 of 6; second n = 6 of 6. One or more measures did not reproduce, so no figure is printed.

eigenpal — latency; first n = 6 of 6; second n = 6 of 6. Latency-session throughput and resources are instrumented; figures withheld.

| Measure | First seed | Second seed |
|---|---|---|
| key_to_paint.median_ms | 26.592 ms; range 25.6 to 28.6 ms (n = 6) | 25.5015 ms; range 24.2 to 26.6 ms (n = 6) |
| key_to_paint.p90_ms | 34.723 ms; range 33.0 to 37.5 ms (n = 6) | 33.166 ms; range 32.2 to 35.0 ms (n = 6) |
| load_ms | 607.344 ms; range 528.3 to 653.4 ms (n = 6) | 568.264 ms; range 551.8 to 585.8 ms (n = 6) |

first: accepted 4866; refused 0 key witnesses.

second: accepted 4866; refused 0 key witnesses.

eigenpal — throughput; first n = 6 of 6; second n = 6 of 6. One or more measures did not reproduce, so no figure is printed.

Folio — latency: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 0, 0; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 0, 0 Latency-session throughput and resources are instrumented; figures withheld.

Folio — throughput: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 0, 0; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 0, 0

GenOffice — latency; first n = 6 of 6; second n = 6 of 6. Latency-session throughput and resources are instrumented; figures withheld.

| Measure | First seed | Second seed |
|---|---|---|
| key_to_paint.median_ms | 32.996 ms; range 32.1 to 33.7 ms (n = 6) | 36.345 ms; range 34.4 to 40.6 ms (n = 6) |
| key_to_paint.p90_ms | 53.274 ms; range 52.4 to 54.6 ms (n = 6) | 57.491 ms; range 56.8 to 66.7 ms (n = 6) |
| load_ms | 726.86 ms; range 718.2 to 753.9 ms (n = 6) | 790.561 ms; range 753.7 to 977.0 ms (n = 6) |

first: accepted 4857; refused 9 key witnesses.

second: accepted 4844; refused 22 key witnesses.

GenOffice — throughput; first n = 6 of 6; second n = 6 of 6. One or more measures did not reproduce, so no figure is printed.

Plate.js — latency; first n = 6 of 6; second n = 6 of 6. Latency-session throughput and resources are instrumented; figures withheld. One or more measures did not reproduce, so no figure is printed.

Plate.js — throughput; first n = 6 of 6; second n = 6 of 6. One or more measures did not reproduce, so no figure is printed.

SuperDoc — latency: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 81,225, 81,225; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 81,225, 81,225 Latency-session throughput and resources are instrumented; figures withheld.

SuperDoc — throughput; first n = 6 of 6; second n = 6 of 6. One or more measures did not reproduce, so no figure is printed.

WordCraft — latency: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 18,886, 18,876; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 20,505, 20,090 Latency-session throughput and resources are instrumented; figures withheld.

WordCraft — throughput: first: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 20,685, 20,814; second: not enough sessions or run blocked (n = 0 of 6; insufficient_typing_sessions); characters typed in the refused sessions that recorded progress: 17,765, 17,586

## Not measured in the browser run

- **Apryse:** Apryse WebViewer needs a licence key, and the key is never placed on the measuring machines.
- **docs.plus:** docs.plus runs only as an application with its own application servers, which the browser run does not start.
- **Fidus Writer:** Fidus Writer runs only as an application with its own application server, which the browser run does not start.
- **LibreOffice (baseline):** LibreOffice is the conversion baseline of the headless report, not a browser editor.
- **office-open:** office-open is a library with no editing surface to paint, so no browser criterion applies.

## Not reproduced

| Editor | Criterion | Workload | Measure | First seed / reason | Second seed, median |
|---|---|---|---|---|---|
| canvas-editor + plugin | C03 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| canvas-editor + plugin | C03 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| GenOffice | C03 | complex-corpus | warm_steady | 1082.5 ms | 883.5 ms |
| Docen | C03 | prose-250kw | process_cold_fs_warm | 9218.0 ms | 10338.0 ms |
| WordCraft | C03 | prose-250kw | process_cold_fs_warm | 3188.5 ms | 3626.5 ms |
| WordCraft | C03 | prose-500w | process_cold_fs_warm | 1568.5 ms | 2006.0 ms |
| WordCraft | C03 | prose-500w | warm_steady | 1003.5 ms | 1143.5 ms |
| canvas-editor + plugin | C03 | prose-50kw | process_cold_fs_warm | 6478.5 ms | 5217.5 ms |
| Docen | C03 | prose-50kw | process_cold_fs_warm | 3378.0 ms | 2551.0 ms |
| Docxodus | C03 | prose-50kw | process_cold_fs_warm | 13686.5 ms | 10022.5 ms |
| eigenpal | C03 | prose-50kw | process_cold_fs_warm | 2716.0 ms | 1818.0 ms |
| Folio | C03 | prose-50kw | process_cold_fs_warm | 2335.5 ms | 1669.0 ms |
| GenOffice | C03 | prose-50kw | process_cold_fs_warm | 1774.5 ms | 1441.0 ms |
| Plate.js | C03 | prose-50kw | process_cold_fs_warm | 6324.0 ms | 4222.0 ms |
| SuperDoc | C03 | prose-50kw | process_cold_fs_warm | 1116.5 ms | 988.5 ms |
| WordCraft | C03 | prose-50kw | process_cold_fs_warm | 2159.0 ms | 2471.5 ms |
| canvas-editor + plugin | C03 | prose-50kw | warm_steady | 6818.0 ms | 4463.0 ms |
| Docen | C03 | prose-50kw | warm_steady | 3088.5 ms | 2218.0 ms |
| Docxodus | C03 | prose-50kw | warm_steady | 12095.0 ms | 9142.5 ms |
| eigenpal | C03 | prose-50kw | warm_steady | 2220.5 ms | 1535.0 ms |
| Folio | C03 | prose-50kw | warm_steady | 2072.5 ms | 1309.0 ms |
| GenOffice | C03 | prose-50kw | warm_steady | 1386.5 ms | 1237.0 ms |
| Plate.js | C03 | prose-50kw | warm_steady | 5563.5 ms | 3694.5 ms |
| SuperDoc | C03 | prose-50kw | warm_steady | 941.5 ms | 388.5 ms |
| WordCraft | C03 | prose-50kw | warm_steady | 1356.0 ms | 1539.5 ms |
| Docen | C03 | prose-5kw | process_cold_fs_warm | 1432.5 ms | 1597.0 ms |
| Folio | C03 | prose-5kw | process_cold_fs_warm | 938.0 ms | 1058.0 ms |
| WordCraft | C03 | prose-5kw | process_cold_fs_warm | 1588.5 ms | 1991.5 ms |
| eigenpal | C03 | prose-5kw | warm_steady | 796.5 ms | 904.5 ms |
| WordCraft | C03 | prose-5kw | warm_steady | 932.0 ms | 1142.5 ms |
| canvas-editor + plugin | C04 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C04 | complex-corpus | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docxodus | C04 | complex-corpus | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| eigenpal | C04 | complex-corpus | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Folio | C04 | complex-corpus | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| GenOffice | C04 | complex-corpus | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Plate.js | C04 | complex-corpus | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| SuperDoc | C04 | complex-corpus | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| canvas-editor + plugin | C04 | prose-250kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docen | C04 | prose-250kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docxodus | C04 | prose-250kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| eigenpal | C04 | prose-250kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Folio | C04 | prose-250kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| GenOffice | C04 | prose-250kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Plate.js | C04 | prose-250kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| SuperDoc | C04 | prose-250kw | — | first: not enough samples (n = 4 of 10; reasons not_applicable: 6) | — |
| canvas-editor + plugin | C04 | prose-500w | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docen | C04 | prose-500w | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docxodus | C04 | prose-500w | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| eigenpal | C04 | prose-500w | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Folio | C04 | prose-500w | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| GenOffice | C04 | prose-500w | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Plate.js | C04 | prose-500w | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| SuperDoc | C04 | prose-500w | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| WordCraft | C04 | prose-500w | — | 664.9 ms | 886.9 ms |
| canvas-editor + plugin | C04 | prose-50kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docen | C04 | prose-50kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docxodus | C04 | prose-50kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| eigenpal | C04 | prose-50kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Folio | C04 | prose-50kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| GenOffice | C04 | prose-50kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Plate.js | C04 | prose-50kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| SuperDoc | C04 | prose-50kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| WordCraft | C04 | prose-50kw | — | second: not enough samples (n = 4 of 10; reasons not_applicable: 6) | — |
| canvas-editor + plugin | C04 | prose-5kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docen | C04 | prose-5kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Docxodus | C04 | prose-5kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| eigenpal | C04 | prose-5kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Folio | C04 | prose-5kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| GenOffice | C04 | prose-5kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| Plate.js | C04 | prose-5kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| SuperDoc | C04 | prose-5kw | — | first seed: 0 of 10 launches kept (not_applicable 10) | — |
| WordCraft | C04 | prose-5kw | — | first: not enough samples (n = 4 of 10; reasons not_applicable: 6); second: not enough samples (n = 2 of 10; reasons not_applicable: 8) | — |
| canvas-editor + plugin | C05 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| Docen | C05 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C05 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| Docen | C05 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C05 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| GenOffice | C05 | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 1 of 10; reasons unverified: 9) | — |
| Plate.js | C05 | prose-250kw | process_cold_fs_warm | 175.2 ms | 205.5 ms |
| WordCraft | C05 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Folio | C05 | prose-250kw | warm_steady | 427.2 ms | 483.5 ms |
| GenOffice | C05 | prose-250kw | warm_steady | second: not enough samples (n = 1 of 10; reasons unverified: 9) | — |
| Plate.js | C05 | prose-250kw | warm_steady | 129.7 ms | 161.8 ms |
| WordCraft | C05 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C05 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C05 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| eigenpal | C05 | prose-50kw | process_cold_fs_warm | 97.6 ms | 65.5 ms |
| Folio | C05 | prose-50kw | process_cold_fs_warm | 215.3 ms | 134.0 ms |
| GenOffice | C05 | prose-50kw | process_cold_fs_warm | 193.6 ms | 143.4 ms |
| Plate.js | C05 | prose-50kw | process_cold_fs_warm | 98.0 ms | 67.9 ms |
| SuperDoc | C05 | prose-50kw | process_cold_fs_warm | 644.0 ms | 450.2 ms |
| WordCraft | C05 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| eigenpal | C05 | prose-50kw | warm_steady | 77.3 ms | 56.2 ms |
| Folio | C05 | prose-50kw | warm_steady | 182.8 ms | 121.5 ms |
| GenOffice | C05 | prose-50kw | warm_steady | 207.3 ms | 139.5 ms |
| SuperDoc | C05 | prose-50kw | warm_steady | 614.5 ms | 431.5 ms |
| WordCraft | C05 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C05 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C05 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C05 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| SuperDoc | C05 | prose-5kw | warm_steady | 286.2 ms | 318.5 ms |
| WordCraft | C05 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| Docen | C06 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C06 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| Docen | C06 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C06 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Folio | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C06 | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Folio | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C06 | prose-250kw | warm_steady | second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| SuperDoc | C06 | prose-250kw | warm_steady | 303.3 ms | 337.5 ms |
| WordCraft | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C06 | prose-500w | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C06 | prose-500w | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| eigenpal | C06 | prose-50kw | process_cold_fs_warm | 66.5 ms | 44.0 ms |
| Folio | C06 | prose-50kw | process_cold_fs_warm | 171.4 ms | 117.5 ms |
| GenOffice | C06 | prose-50kw | process_cold_fs_warm | 176.3 ms | 134.7 ms |
| Plate.js | C06 | prose-50kw | process_cold_fs_warm | 59.2 ms | 39.2 ms |
| SuperDoc | C06 | prose-50kw | process_cold_fs_warm | 369.9 ms | 278.9 ms |
| WordCraft | C06 | prose-50kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Folio | C06 | prose-50kw | warm_steady | 163.5 ms | 107.9 ms |
| GenOffice | C06 | prose-50kw | warm_steady | 203.2 ms | 143.2 ms |
| Plate.js | C06 | prose-50kw | warm_steady | 61.2 ms | 43.9 ms |
| SuperDoc | C06 | prose-50kw | warm_steady | 370.5 ms | 275.1 ms |
| WordCraft | C06 | prose-50kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| SuperDoc | C06 | prose-5kw | process_cold_fs_warm | 176.1 ms | 199.9 ms |
| WordCraft | C06 | prose-5kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C06 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C06 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C06 | prose-5kw | warm_steady | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C07 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| WordCraft | C07 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10); second: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10) | — |
| WordCraft | C07 | prose-250kw | — | 169.9 ms | 194.3 ms |
| canvas-editor + plugin | C08 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C08 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C08 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10); second: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10) | — |
| canvas-editor + plugin | C08 | prose-250kw | — | first: not enough samples (n = 2 of 10; reasons crash: 1; paint_witness_unavailable: 7); second: not enough samples (n = 2 of 10; reasons paint_witness_unavailable: 8) | — |
| SuperDoc | C08 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| canvas-editor + plugin | C08 | prose-50kw | — | first: not enough samples (n = 2 of 10; reasons unverified: 8); second: not enough samples (n = 4 of 10; reasons unverified: 6) | — |
| Plate.js | C08 | prose-50kw | — | 151.9 ms | 128.9 ms |
| canvas-editor + plugin | C09 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C09 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docxodus | C09 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C09 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10); second: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10) | — |
| canvas-editor + plugin | C09 | prose-50kw | — | 183.1 ms | 155.7 ms |
| canvas-editor + plugin | C10 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) | — |
| WordCraft | C10 | complex-corpus | — | 129.9 ms | 149.6 ms |
| WordCraft | C10 | prose-500w | — | 130.2 ms | 194.5 ms |
| WordCraft | C10 | prose-50kw | — | 130.7 ms | < 1 frame (16.7 ms) |
| canvas-editor + plugin | C11 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docen | C11 | prose-500kw | — | 22101.5 ms | 26436.5 ms |
| canvas-editor + plugin | C12 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C12 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C12 | complex-corpus | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| GenOffice | C12 | prose-250kw | — | 2973.4 ms | 2565.1 ms |
| WordCraft | C12 | prose-250kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-500kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-500kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| eigenpal | C12 | prose-500kw | — | 81.7 ms | 98.5 ms |
| GenOffice | C12 | prose-500kw | — | 16029.7 ms | 12039.7 ms |
| SuperDoc | C12 | prose-500kw | — | 2098.6 ms | 1782.0 ms |
| WordCraft | C12 | prose-500kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C12 | prose-500w | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C12 | prose-50kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C12 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| Docen | C12 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| WordCraft | C12 | prose-5kw | — | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) | — |
| canvas-editor + plugin | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| SuperDoc | C14 | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| eigenpal | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons cpu_throttled: 1); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| SuperDoc | C14 | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docen | C14 | prose-250kw | usable_no_damage | 8777.8 ms | 7662.6 ms |
| eigenpal | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | prose-250kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docen | C14 | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| SuperDoc | C14 | prose-500kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | prose-500kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-500kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) | — |
| WordCraft | C14 | prose-500kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| SuperDoc | C14 | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | prose-500w | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| SuperDoc | C14 | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | prose-50kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) | — |
| Docen | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Docxodus | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Folio | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| GenOffice | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| Plate.js | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| SuperDoc | C14 | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| eigenpal | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| WordCraft | C14 | prose-5kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) | — |
| canvas-editor + plugin | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docen | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docxodus | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| eigenpal | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Folio | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| GenOffice | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Plate.js | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| SuperDoc | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| WordCraft | C15 | micro-search | first_match | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| canvas-editor + plugin | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docen | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docxodus | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| eigenpal | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Folio | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| GenOffice | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Plate.js | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| SuperDoc | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| WordCraft | C15 | micro-search | index_quiescence | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| canvas-editor + plugin | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docen | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docxodus | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| eigenpal | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Folio | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| GenOffice | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Plate.js | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| SuperDoc | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| WordCraft | C15 | micro-search | replace_all | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| canvas-editor + plugin | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docen | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Docxodus | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| eigenpal | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Folio | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| GenOffice | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| Plate.js | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| SuperDoc | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| WordCraft | C15 | micro-search | search_complete | first seed unpublishable: duplicate block index in one seed (blocked); second seed unpublishable: duplicate block index in one seed (blocked) | — |
| canvas-editor + plugin | C17 | complex-corpus | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| canvas-editor + plugin | C17 | complex-corpus | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| canvas-editor + plugin | C17 | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| Docxodus | C17 | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Folio | C17 | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C17 | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| SuperDoc | C17 | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C17 | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| canvas-editor + plugin | C17 | prose-250kw | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| canvas-editor + plugin | C17 | prose-250kw | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| canvas-editor + plugin | C17 | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) | — |
| Docxodus | C17 | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Folio | C17 | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C17 | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| SuperDoc | C17 | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C17 | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docxodus | C17 | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Folio | C17 | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C17 | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| SuperDoc | C17 | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C17 | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docxodus | C17 | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Folio | C17 | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C17 | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| SuperDoc | C17 | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C17 | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Docxodus | C17 | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| Folio | C17 | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C17 | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| SuperDoc | C17 | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| WordCraft | C17 | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |

## How to reproduce

See perf/container/README.md.

## DOCX verification

The DOCX twin is a deliverable of the release gate: `build/verify_publication.sh --with-word` opens it in Microsoft Word and fails on any warning or offer to repair the file.
