# Report E2 — Speed in the Browser (2026)



## What this report is

Nine editors that open Word documents in a web browser were each given the same documents, in a real browser, and timed doing what a person does: opening a document, typing, clicking, pasting, undoing and scrolling. This report gives the results in seven small tables, one per action, and says what the figures can and cannot tell you.

It is written to be read from here to the end of the results. The appendices after that hold everything needed to check it: how each time was taken, the machine, the rule a figure had to pass before it was printed, the full tables, what was not measured and why, and how to run it again.

**The editors added to the trial in v0.11.0 are measured by a separate campaign.** BetterOffice, Nutrient, OnlyOffice (CryptPad build), OpenDoc and react-docx are timed in the browser by a campaign of their own, on the same machine type and with the same lanes and documents. That campaign is not yet measured; the section "The editors measured later", after the results, says so and is where its tables go. The results and the appendices are the earlier campaign's, unchanged, for the nine editors it covered. OpenDoc, BetterOffice and OnlyOffice are also timed without a browser in Report E. The measurements on editors.benchmarks.law of how the new tools load on a page use a different method and are not comparable with any table of this report.

## How to read the tables

- **A figure is a typical time.** Each action was repeated many times, across several fresh launches of the browser, and the figure is a typical (middle) result of those repeats. Appendix C gives the exact rule.
- **Lower is quicker, or lighter.** Times are in milliseconds (ms, thousandths of a second) or seconds (s); memory is in MiB and GiB (1 GiB is 1,024 MiB).
- **Read down a column.** Each column is one document size, and every editor in it was given the same document. The editors were measured on separate cloud machines of the same type, each shared with other work, so a small difference between two editors can be the machine and not the editor.
- **"under 17 ms"** means the first picture of the screen that showed the change came less than one redraw after the action. The screen was redrawn 60 times a second, once every 16.7 ms, so times shorter than that cannot be told apart from each other.
- **A range, such as "48 ms to 81 ms",** is printed where the repeated measurements disagreed too much to print one figure; its ends are what they gave. Neither end is the editor's time; read it as "somewhere about here, and not settled".
- **"not measured"** means our tooling did not time the action there. It says nothing about whether the editor does it, or how quickly. **"crashed"** means the editor's page crashed in every launch of that test at that size; it says nothing about the other tests. **"no figure"** means too few launches gave a confirmed result, whether because of the editor or of our tooling. **"does not apply"** is printed only where there was nothing to measure. A dash means the cell was not part of these runs.
- **Every cell that is not a single figure has a line in Appendix J** saying what was measured there and why no single figure is printed.
- **The editors are in alphabetical order.** This report does not rank them.

## What the figures cannot tell you

- **They are not the times you will see on your own computer.** The tests ran on a cloud server with no graphics processor, so everything an editor draws was drawn by the processor. For WordCraft, which redraws its page continuously, that drawing is nearly all of the processor time it used in the half minute after opening a document (table B8 in Appendix E). The figures compare the editors with each other on machines of that kind.
- **The two largest documents are deliberately extreme.** They are stress tests, not ordinary work; the first two columns are the ones to reason from.
- **A range can be the machine, not the editor.** The machines are shared with other work, and some measurements were taken while a machine was much busier than at other times (issue #228; Appendix B gives the load of each run). Appendix B names the jobs in which a quarter or more of the launches began or ended on a busy machine; where one round of a range comes from such a job, the report cannot tell the machine from the editor. A range should not be read as a property of the editor.
- **Typing in three editors was timed from the picture of the screen.** canvas-editor, Docen and WordCraft draw their text on a canvas, where the harness cannot read the outline of a typed character. For them a key press is timed to the first picture of the screen that shows the whole change the key made on the caret's line, once that change has stopped moving, with the caret itself left out. Those times are marked "(by pixels)", and the note under the table gives the smallest such change behind them (issue #245). For the other editors the time ends at the picture in which the typed character's own outline shows ink. The two ways of ending a time were compared on the editors that allow both; Appendix D gives the result.
- **Search and replace was not measured** for any editor, because of a gap in our tooling. This report says nothing about it.
- **The line under each table is for orientation.** It says how many of the editors have a figure in the first and in the last column, and the lowest and highest of those figures. An editor without a figure is not in that spread.
- **Only what is listed is measured.** Whether an editor keeps a document's content and formatting intact is the subject of the other reports of this trial.

## The results

### Opening a document

From the moment the page is asked for the document until the first frame that shows it. The length of the text the editor holds is checked against the document (within 2 percent). For the editors that draw on a canvas, that text is read from the editor and not from the picture (Appendix D); content and formatting are not checked here.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words | 500,000 words |
|---|---|---|---|---|---|
| canvas-editor + plugin | 344 ms | 1.0 s | 8.3 s | 64.8 s | 285 s |
| Docen | 1.1 s | 1.3 s | 2.3 s | 8.2 s | 22.1 s to 26.4 s |
| Docxodus | 2.4 s | 3.3 s | 11.2 s | 46.3 s | 99.9 s |
| eigenpal | 547 ms | 698 ms | 1.1 s | 2.4 s | 3.9 s |
| Folio | 797 ms | 940 ms | 1.8 s | 4.7 s | 8.1 s |
| GenOffice | 689 ms | 890 ms | 1.1 s | 2.1 s | 3.2 s |
| Plate.js | 752 ms | 1.2 s | 4.6 s | 19.1 s | 37.4 s |
| SuperDoc | 2.4 s | 2.8 s | 5.8 s | 15.9 s | 29.2 s |
| WordCraft | 1.3 s | 1.3 s | 1.7 s | 2.9 s | 4.5 s |

At 500 words, 9 of 9 editors have a figure, from 344 ms to 2.4 s; at 500,000 words, 8 of 9, from 3.2 s to 285 s.

### Typing one character

From a key press until the frame in which that character is on screen, in a document that is already open.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | 68 ms (by pixels) | 351 ms (by pixels) | 3.0 s (by pixels) | 16.5 s (by pixels) |
| Docen | 45 ms (by pixels) | 76 ms (by pixels) | 452 ms (by pixels) | 7.3 s (by pixels) |
| Docxodus | under 17 ms | under 17 ms | 16 ms | 28 ms |
| eigenpal | 46 ms | 42 ms | 56 ms | 76 ms |
| Folio | 46 ms | 46 ms | 122 ms | 430 ms |
| GenOffice | 19 ms | 26 ms | 146 ms | no figure |
| Plate.js | 25 ms | 26 ms | 48 ms | 133 ms |
| SuperDoc | 135 ms | 273 ms | 437 ms | 553 ms |
| WordCraft | 128 ms (by pixels) | 135 ms (by pixels) | 157 ms (by pixels) | 238 ms (by pixels) |

At 500 words, 9 of 9 editors have a figure, from under 17 ms to 135 ms; at 250,000 words, 8 of 9, from 28 ms to 16.5 s (by pixels).

A time marked "(by pixels)" ends at the first frame that shows the whole settled change the key press made on the caret's line. The editor draws its text on a canvas, where the harness cannot read a character's outline. Where the editor reports its caret's place, the caret's own columns are left out; where it does not, the change must reach 100 pixels, more than any caret. The smallest such change on any key press behind these times was 29 pixels (issue #245).

### Clicking to place the caret

From a click in the text until the next frame the editor paints.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | under 17 ms | 27 ms | 61 ms | 391 ms |
| Docen | 27 ms | 28 ms | 93 ms | 1.8 s |
| Docxodus | under 17 ms | under 17 ms | under 17 ms | 42 ms |
| eigenpal | 29 ms | 28 ms | 26 ms | 20 ms |
| Folio | 63 ms | 77 ms | 387 ms | 1.9 s |
| GenOffice | under 17 ms | under 17 ms | 19 ms | 40 ms |
| Plate.js | 30 ms | 30 ms | 86 ms | 379 ms |
| SuperDoc | 60 ms | 77 ms | 235 ms | 337 ms |
| WordCraft | 185 ms | 175 ms | 173 ms | 170 ms to 194 ms |

At 500 words, 9 of 9 editors have a figure, from under 17 ms to 185 ms; at 250,000 words, 8 of 9, from 20 ms to 1.9 s.

### Pasting a block of text

From the paste of a 1,500-character block until the first frame in which the page visibly changed.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | 94 ms | 361 ms | no figure | no figure |
| Docen | 32 ms | 63 ms | 558 ms | 9.3 s |
| Docxodus | 16 ms | 19 ms | under 17 ms | under 17 ms |
| eigenpal | 53 ms | 57 ms | 109 ms | 109 ms |
| Folio | 49 ms | 107 ms | 131 ms | 413 ms |
| GenOffice | 22 ms | 24 ms | 170 ms | 2.8 s |
| Plate.js | 44 ms | 47 ms | 129 ms to 152 ms | 433 ms |
| SuperDoc | 118 ms | 332 ms | 966 ms | no figure |
| WordCraft | 131 ms | 129 ms | 154 ms | 248 ms |

At 500 words, 9 of 9 editors have a figure, from 16 ms to 131 ms; at 250,000 words, 7 of 9, from under 17 ms to 9.3 s.

### Undoing

From the undo of one typed character until the first frame that differs.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | 56 ms | 25 ms | 156 ms to 183 ms | 65 ms |
| Docen | 25 ms | 50 ms | 463 ms | 8.8 s |
| Docxodus | 69 ms | 325 ms | 3.1 s | 16.6 s |
| eigenpal | 26 ms | 26 ms | 30 ms | 46 ms |
| Folio | 48 ms | 47 ms | 146 ms | 162 ms |
| GenOffice | 18 ms | 19 ms | 158 ms | 2.6 s |
| Plate.js | 23 ms | 21 ms | 45 ms | 154 ms |
| SuperDoc | 67 ms | 123 ms | 230 ms | 270 ms |
| WordCraft | 133 ms | 129 ms | 150 ms | 245 ms |

At 500 words, 9 of 9 editors have a figure, from 18 ms to 133 ms; at 250,000 words, 9 of 9, from 46 ms to 16.6 s.

### Scrolling

From a scroll of the document until the first frame in which its content has moved.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words |
|---|---|---|---|---|
| canvas-editor + plugin | under 17 ms | 16 ms | under 17 ms | under 17 ms |
| Docen | under 17 ms | 18 ms | under 17 ms | 22 ms |
| Docxodus | under 17 ms | under 17 ms | under 17 ms | 62 ms |
| eigenpal | under 17 ms | 26 ms | 25 ms | 29 ms |
| Folio | 15 ms | under 17 ms | under 17 ms | under 17 ms |
| GenOffice | under 17 ms | 17 ms | 20 ms | 60 ms |
| Plate.js | under 17 ms | under 17 ms | 21 ms | 64 ms |
| SuperDoc | 16 ms | 19 ms | 26 ms | 51 ms |
| WordCraft | 130 ms to 195 ms | 150 ms | under 17 ms to 131 ms | 148 ms |

At 500 words, 8 of 9 editors have a figure, from under 17 ms to 16 ms; at 250,000 words, 9 of 9, from under 17 ms to 148 ms.

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

At 500 words, 9 of 9 editors have a figure, from 567 MiB to 1.1 GiB; at 250,000 words, 8 of 9, from 996 MiB to 7.4 GiB.

## The editors measured later

BetterOffice, Nutrient, OnlyOffice (CryptPad build), OpenDoc and react-docx were added to the trial in v0.11.0, after the campaign above was measured. They are measured by a separate campaign of their own, on the same machine type, with the same lanes, the same layout of jobs and the same two seeds.

Read these tables beside the results above with that in mind. They come from other days and other virtual machines of the same type, so a small difference between one of these figures and one above can be the machine and not the editor. The later campaign is not yet measured, so it has not been compared with the campaign above. The rule a figure had to pass is the one in Appendix C, and each time is taken as Appendices A and D describe, with these differences:

- **Sentence capitalisation off for OnlyOffice and OpenDoc.** Their measured pages switch sentence auto-capitalisation off. With their default, the typed "v." becomes "V.", and the typing check, which compares the whole typed text, fails.
- **Nutrient is a viewer.** Typing, the input lane and the edit burst do not apply to it. Its SDK is loaded from Nutrient's CDN on each cold load, so its load figures include that fetch and are not like-for-like with the editors served from the measuring machine.
- **C07 and the click's own scroll.** C07 now judges the caret against where the clicked line ends up after the scroll the click itself causes. The campaign above had no refusal of that kind, so none of its C07 figures is affected.
- **OnlyOffice's scrolling.** OnlyOffice draws its own scrollbar and has no scroller in the page for the harness to watch, so its C10 (scrolling) is to be measured from canvas pixels. Not yet measured.

This campaign is not yet measured: no table of this section has a figure yet.

not yet measured

### The machine and the runs

Relaxed bounds: Clock skew: 5 ms. Ready/navigation load timeouts: 300 s by default, 600 s on the largest document workload; C14 (large-document scaling) gives each wait of a load (navigation, the editor's ready signal, the page's load event for the canvas editors Docen and WordCraft, the painted document) up to 1000 s. Sparse-witness settle onset floor: 100 ms. CPU throttle tolerance: max(1 ms, 1% of the sample span). Witness anchor lag: max(3 frame intervals, 250 ms). Typing/document content length tolerance: 2% for the prose documents; the complex document (complex-corpus) is accepted at 75% to 125% of the expected length.

not yet measured

not yet measured

### The full tables

#### First visible content (C03)

not yet measured

#### Deferred work (C04)

not yet measured

#### Single-edit responsiveness (C05)

not yet measured

#### Sustained typing (C06)

not yet measured

#### Cursor and selection (C07)

not yet measured

#### Clipboard and bulk editing (C08)

not yet measured

#### Undo and redo (C09)

not yet measured

#### Scrolling (C10)

not yet measured

#### Initial layout (C11)

not yet measured

#### Incremental reflow (C12)

not yet measured

#### Global invalidation (C13)

not yet measured

#### Large-document scaling (C14)

not yet measured

#### Search and replace (C15)

not yet measured

#### Memory by phase (C17)

not yet measured

#### Resources while opening and editing (B8)

not yet measured

#### Typing marathon (B9)

not yet measured

### Cells whose two rounds did not agree

not yet measured

### Every results cell that is not a single figure, and why

One line for every cell of this section's results tables that is not a single figure, with the reasons each launch recorded, as in Appendix J.

not yet measured

## Appendix A — What was measured, and how each time was taken

The seven tables of the results come from seven of the criteria described here: opening a document is C11; typing one character is C05, in an editor that has already been typed in; clicking to place the caret is C07; pasting is C08; undoing is C09; scrolling is C10; memory is C17, read two seconds after a burst of typing. The other criteria are in the full tables of Appendix E only.

A "cell" below is one editor, one criterion, one measure and one document: far more cells than the boxes of the results tables. A "seed" is one of the two rounds in which everything was run (Appendix C).

This report concerns browser-visible first paint, typing, scrolling, and related interactions. 798 of 1061 scheduled editor/criterion/measure cells reproduced between the two seeds. 66 run folders contributed 228 jobs (seed 1: 114 jobs; seed 2: 114 jobs); earliest job start 2026-11-12, latest job end 2026-11-17.

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

## Appendix B — The machine and its limits

Relaxed bounds: Clock skew: 5 ms. Ready/navigation load timeouts: 300 s by default, 600 s on the largest document workload; C14 (large-document scaling) gives each wait of a load (navigation, the editor's ready signal, the page's load event for the canvas editors Docen and WordCraft, the painted document) up to 1000 s. Sparse-witness settle onset floor: 100 ms. CPU throttle tolerance: max(1 ms, 1% of the sample span). Witness anchor lag: max(3 frame intervals, 250 ms). Typing/document content length tolerance: 2% for the prose documents; the complex document (complex-corpus) is accepted at 75% to 125% of the expected length.

Each seed ran on the same hardware class (shared_guarded) on separate virtual machines (Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-2, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft), not on one host. A Space name is a machine name: the editors measured are those in the tables. Spaces e2-apryse, e2-docsplus, e2-fidus are machines named for editors this report does not measure.

Seed 1 — 114 jobs on Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-2, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft: CPU model AMD EPYC 7R13 Processor; CPU quota 8.0; logical CPUs 64; OS linux 6.12.113-138.209.amzn2023.x86_64 (109 jobs), linux 6.12.111-136.204.amzn2023.x86_64 (4 jobs), linux 6.12.115-140.210.amzn2023.x86_64 (1 job); Chromium 156.0.8078.80; renderer ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver); stolen CPU time less than 0.01%; throttle refusals: 0 of 3338 samples refused for cgroup CPU throttling; host load average (1 min) at the start and end of each job: 2.1 to 38.4, median 9.7.

Seed 2 — 114 jobs on Spaces e2-apryse, e2-canvas, e2-docen, e2-docsplus, e2-docxodus, e2-eigenpal, e2-fidus, e2-folio, e2-genoffice, e2-plate, e2-publish, e2-publish-2, e2-publish-3, e2-publish-4, e2-publish-5, e2-publish-6, e2-publish-7, e2-publish-8, e2-superdoc, e2-wordcraft: CPU model AMD EPYC 7R13 Processor; CPU quota 8.0; logical CPUs 64; OS linux 6.12.113-138.209.amzn2023.x86_64 (103 jobs), linux 6.12.111-136.204.amzn2023.x86_64 (10 jobs), linux 6.12.115-140.210.amzn2023.x86_64 (1 job); Chromium 156.0.8078.80; renderer ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver); stolen CPU time less than 0.01%; throttle refusals: 4 of 3338 samples refused for cgroup CPU throttling; host load average (1 min) at the start and end of each job: 1.9 to 31.5, median 8.2.

Editor pins (built-editor tree SHA-256 of every attempt that ran, in every run folder): canvas-editor + plugin: db742f005c4542a8afa75f4801dd40785e1ce298331903d5ac84bce79c3b24a0; Docen: cf72bd0ee7f16b61d2751113a6533b63697cc437fdf1916e6cb8c6307a343204; Docxodus: dc663a3ee106917d5b93f06fa3ceaa2527bc917b7accfe582cf6ef411dc121ce; eigenpal: 94bdb0c2ee05a56bff1734c3b11f6d39805e4965fab5d778300ee288ce0af40e; Folio: 34e784f890d8ae99129f7ef98c0af4ca3225278b3f9f1a6ed93bee23a9b14ab4; GenOffice: 746b793e0ad8f2a0a12ec5ecf1aeddfa79895102244ac1c717bce6fbbe523789; Plate.js: 0b3c24cc2bf9348a9e904d22757449915be9abee764f5d345557f928cad6f32d; SuperDoc: 4ab1fc57f5e418532f50bc84c5380723c5ae52750d5ae2fdab55c3a4cefcfed6; WordCraft: 003a46b20c05597e3e385e745c9ddec19a4f0ecb43d57e596209e02c5623849a.

### Host load, launch by launch

Every launch (one editor, one repetition of a job) records the host's 1-minute load average when it began and when it ended. The harness's own bound for a quiet machine is a third of the host's logical processors. No sample was refused for it: the table below says how many of the launches that carry both readings began or ended above it, and names the jobs in which a quarter or more did. Where the two seeds of a cell disagree and one of them comes from such a job, the load is one possible reason, and the report cannot tell it from the editor. A job that was run again for one editor has five launches, and the table names that editor.

Of the 6,676 launches of these runs, 310 (4.6 percent) began or ended with the load above 21.3.

| Lane | Launches | Above the bound | Share |
|---|---|---|---|
| C10 scroll | 1,000 | 81 | 8.1 percent |
| document | 1,440 | 39 | 2.7 percent |
| input | 900 | 17 | 1.9 percent |
| memory | 940 | 63 | 6.7 percent |
| resources | 900 | 11 | 1.2 percent |
| typing | 216 | 16 | 7.4 percent |
| warm and cold load | 1,280 | 83 | 6.5 percent |

Jobs in which a quarter or more of the launches were above it:

| Lane | Document | Seed | Block | Space | Editors | Launches above | Highest load |
|---|---|---|---|---|---|---|---|
| C10 scroll | 500 words | second | 1 | e2-plate | WordCraft | 2 of 5 | 23.7 |
| C10 scroll | 500 words | second | 2 | e2-plate | WordCraft | 5 of 5 | 27.6 |
| C10 scroll | 5,000 words | first | 1 | e2-docen | every editor | 26 of 45 | 30.6 |
| C10 scroll | 5,000 words | second | 1 | e2-plate | WordCraft | 5 of 5 | 25.7 |
| C10 scroll | 50,000 words | second | 1 | e2-plate | WordCraft | 2 of 5 | 23.7 |
| C10 scroll | 50,000 words | second | 2 | e2-plate | WordCraft | 3 of 5 | 21.5 |
| C10 scroll | 250,000 words | second | 2 | e2-plate | WordCraft | 3 of 5 | 23.2 |
| C10 scroll | complex document | second | 1 | e2-plate | every editor | 13 of 45 | 27.9 |
| C10 scroll | complex document | second | 1 | e2-plate | WordCraft | 4 of 5 | 23.2 |
| C10 scroll | complex document | second | 2 | e2-plate | WordCraft | 5 of 5 | 24.1 |
| document | complex document | second | 1 | e2-superdoc | every editor | 24 of 45 | 49.7 |
| memory | 250,000 words | second | 1 | e2-docen | every editor | 15 of 45 | 38.8 |
| memory | 250,000 words | second | 2 | e2-fidus | every editor | 18 of 45 | 28.4 |
| typing | not recorded | first | not recorded | e2-apryse | Docxodus | 6 of 6 | 46.3 |
| typing | not recorded | first | not recorded | e2-folio | eigenpal | 3 of 6 | 39.9 |
| typing | not recorded | second | not recorded | e2-eigenpal | WordCraft | 4 of 6 | 25.4 |
| typing | not recorded | second | not recorded | e2-superdoc | GenOffice | 2 of 6 | 31.8 |
| warm and cold load | 500 words | first | 1 | e2-docen | every editor | 13 of 45 | 30.4 |
| warm and cold load | 500 words | second | 1 | e2-superdoc | WordCraft | 3 of 5 | 24.7 |
| warm and cold load | 500 words | second | 2 | e2-superdoc | WordCraft | 2 of 5 | 22.0 |
| warm and cold load | 50,000 words | second | 2 | e2-superdoc | WordCraft | 2 of 5 | 23.8 |
| warm and cold load | 250,000 words | first | 2 | e2-superdoc | every editor | 18 of 45 | 29.9 |
| warm and cold load | complex document | second | 2 | e2-docen | Docen, WordCraft, canvas-editor + plugin | 4 of 15 | 25.7 |

Jobs per Space, from each job summary's host-build records: e2-apryse: 7; e2-canvas: 10; e2-docen: 14; e2-docsplus: 10; e2-docxodus: 9; e2-eigenpal: 9; e2-fidus: 11; e2-folio: 10; e2-genoffice: 11; e2-plate: 21; e2-publish: 7; e2-publish-2: 17; e2-publish-3: 6; e2-publish-4: 8; e2-publish-5: 11; e2-publish-6: 8; e2-publish-7: 9; e2-publish-8: 17; e2-superdoc: 21; e2-wordcraft: 12.

Playwright not recorded, Chromium 156.0.8078.80. Renderer: ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver).

## Appendix C — Every measurement was run twice: the rule a figure had to pass

Everything in this report was run twice, in two separate rounds (called seeds below), and a figure is printed only when the two agree. Each round gives one number per cell: the median of its kept launches, where each launch counts as the median of its own samples. The figure in the results above is the midpoint (the average) of the two rounds' numbers. The results print that figure alone; the count of launches, the range and the 90th percentile described below are in the full tables of Appendix E. "under 17 ms" is printed only when both rounds were under one redraw of the screen (16.7 ms, called a frame below); a range is printed for a cell whose two rounds did not agree within 10 percent (or, for times that short, within one frame), and gives the two rounds' numbers.

This is a first pass with fewer samples than planned. Each cell schedules 10 samples per editor per seed and is published when at least 5 samples are kept. The 90th percentile is printed only when at least 10 samples are kept; with 5 to 9 kept, the table prints the median and the range from the smallest kept sample to the largest, because a percentile of a short sample is not a stable figure.

Typing schedules 6 sessions per kind per seed and publishes a cell when at least 5 are kept. With 5 kept sessions and fewer than 6, the table prints the median and the range from the smallest kept session to the largest. A key-to-paint 90th percentile inside one session is over keys, not over sessions.

Each launch contributes the median of its own samples; n counts kept launches. Scheduled counts come from each run's order. Publishability is decided per trial — job summaries delegate it to their trials — and a cell publishes only from trials that are publishable and record the built editor's identity (host_provenance.tree_sha256, else a pinned editor_version); a trial recording neither is refused as pin not recorded, and a reproduction across different built-editor trees is refused. Each of the two seeds must keep at least 5 launches per cell, its launches pooled across the campaign's run folders, and a run-level block — a shakedown run, dirty repos, unavailable CPU accounting or a failed run — refuses the whole run. The medians must agree within 10 percent of the larger median or the larger witnessed frame interval. Samples of frame-witnessed criteria require complete boolean flags checked against a witnessed interval; model-layer clocks such as C04 and byte counts publish without them, and sub-frame medians are buckets; p90 is printed only when at least 10 launches are kept; with 5 to 9 kept, the table prints the median and the range. p90 is over launch medians. C14 rungs and C14 measures (presented_frame, usable_no_damage) and C15 steps are separate measures; a no-damage C14 sample is the DOM document-surface time, never a compositor frame.

228 jobs in 66 run folders — seed 1: 114 jobs; seed 2: 114 jobs. Dates: 2026-11-12 to 2026-11-17.

## Appendix D — Notes on the full tables, and what was measured again

- **Re-run jobs.** 32 first-pass jobs were measured again after three harness defects were fixed (issues #173, #174 and #175). The lane round below replaced those re-run jobs in turn. `perf/container/e2_publication.json` names every run and every replaced job. In a second round, 4 C14 jobs of the re-run were measured again after the C14 correctness check was fixed (issue #181). In a third round, those 4 C14 jobs were measured again after C14 was given the editor's own whole-document read and a 1,000-second load timeout (issues #183 and #184). Then single editors' cells of those lanes were measured again alone, each after a change in how the harness measured that editor: canvas-editor (issues #185, #202); Plate.js (issue #190); Docen (issues #193, #202); WordCraft (issues #196, #197); GenOffice (issue #203). The lane round replaced those cells. Then Docen's and canvas-editor's cells of the 4 prose-250kw memory jobs (C17 and C19) were measured again after the memory pair's deadline was found to cover one load where the pair runs two loads and a 120-character burst (issue #194). Those runs measured Docen and canvas-editor alone, under the same job indices and seeds; the tables read them for Docen and canvas-editor, and the other editors of those jobs stay as measured. Then WordCraft's cells of the 20 warm and cold load jobs (C03, with C05 and C06 of the same jobs) were measured again after its opening check was found never to read WordCraft's text, although the harness reads the whole document through WordCraft's own select all and copy; every C03 attempt had been refused as unverifiable (issue #196). Those runs measured WordCraft alone, under the same job indices and seeds; the tables read them for WordCraft, and the other editors of those jobs stay as measured. Then WordCraft's cells of the 20 C10 scroll jobs were measured again after C10 was found never to scroll WordCraft's document: the host's scroll overlay, built for this probe, was never selected, so every attempt found no scroll container (issue #198). Those runs measured WordCraft alone, under the same job indices and seeds; the tables read them for WordCraft, and the other editors of those jobs stay as measured. In a late round, the 4 C10 jobs on the complex document were measured again for every editor after C10 was found to load that document with its document protection, which GenOffice and eigenpal honour by opening it read-only, so C10 never started for them; it now loads the unprotected copy the editing criteria load (issue #192). The tables read the 4 late-round jobs in their place. In a lane round, every job of the document lane (32 jobs) and of the input lane (20 jobs) was measured again for every editor, interleaved as in the campaign, after two harness defects that touched every editor were fixed. The document probe's own scan for the opening headings grew with the square of the page and ran inside the timed load: in the Chrome traces of the replaced jobs it took about 19 minutes of a 250,000-word Plate.js load whose own scripts ran about 21 seconds (issue #206). C08 took the frame in which an editor redrew its own caret for the pasted text, and WordCraft's C09 did the same for an undo: a caret changes 16 to 58 pixels, a painted paste 677 or more, and the criteria now wait for a frame that changes at least 100 (issue #207). For those lanes the tables read the 52 lane-round jobs only; every earlier measurement of them is replaced. In a host round, 4 jobs of the warm and cold load lane were measured again for every editor (issue #228): when they first ran, the host's load was above the bound the harness holds a quiet machine to for most of their launches (the issue gives the readings); the harness measures the same way, and it now waits for a quiet host before a job and before a launch. The tables read those 4 jobs; every earlier measurement of them is replaced, a single editor's own round included, and the other jobs of the lane stay as measured. In a witness round, canvas-editor's, Docen's and WordCraft's cells of the 20 jobs of the warm and cold load lane were measured again (issue #245): the harness could not time a key press in an editor that draws its text on a canvas, where no character outline can be read, and it now reads the settled picture of the edit. Those runs measured those editors alone, under the same job indices and seeds; the tables read them for those editors, every earlier measurement of those cells is replaced, a host round's included, and the other editors of those jobs stay as measured. 2 editor-round jobs were stopped part-way when their work moved to another Space; each was measured whole there, and the tables never read the stopped parts.
- **How an edit is confirmed.** After each timed interval, and outside it, the harness checks that the edit landed once. It counts the typed text near the caret in the page (Plate, Docxodus, SuperDoc, GenOffice, eigenpal, and Folio through its hidden editing layer) or in the editor's model (canvas-editor, Docen). WordCraft paints into one canvas and puts no document text in the page, so C04 and C07 confirm its edit by the modified mark in its window title. C05 and C06 confirm it by a count of its whole text, taken through WordCraft's own select-all and copy once the document has opened and again after the keys of a launch: the count must rise by exactly the number of keys pressed. C08 and C09 confirm it through the same select-all and copy: a read before the timed interval and one after it, both outside it.
- **WordCraft.** WordCraft puts no document text in the page, so the harness reads its text through WordCraft's own select-all and copy (issue #196), after the timed interval and outside it. C03 and C11 check its content that way. Where timed work follows in the same page (the input lane's opening check before C04 and C07, and C14's frame witness, which reads the whole text itself afterwards), that read is skipped. In the warm and cold lane it is kept, because C05 and C06 need the count of the text it gives: there the copy runs when the document has opened, before the click that places the caret, and the keys are timed after that click. After that copy, WordCraft's paste inserted its own clipboard as well as the system one: a 1,500-character block grew the document by 5,720 characters. C08 therefore reloads the document after its baseline read and pastes into the fresh page, where the same block grew it by 1,500 (issue #197). WordCraft scrolls a host overlay (`#wc-scroll`) above its canvas, not the page, so C10 scrolls that overlay with the pointer over the canvas and watches the canvas for the moved frame (issue #198). On the complex document, whose first page holds three lines, the harness's scan for the document body takes WordCraft's painted window chrome for text, so C07, C08 and C09 clicked above the page (the title bar, and for C07 also a toolbar button), and their keystrokes never reached the document. Those three cells are withheld as a limit of the harness, `click_points_on_editor_chrome`, and say nothing about WordCraft (issue #200); its prose cells stand. Its C03 and C10 cells come from jobs that ran WordCraft alone, with the same seeds and blocks; its cells of the document and input lanes come from the last round, which measured every editor again.
- **canvas-editor's load.** canvas-editor paints every page into a canvas and puts no text in the page, so C11 and C14 time it to the first frame in which its canvas shows ink. It paints its empty page's margin marks at once, before the document is imported, so that frame alone came before the document. Its first measurement stopped there: about 130 ms at every size, while the import of the 250,000-word document took 51 seconds (issue #185). canvas-editor reports the import finished one or two frames before it paints the document, and at some sizes it clears the page first. The usable frame is now the first one in which canvas-editor reports the document imported and its first page shows ink that differs from its empty page. Its C11, C12, C14 and C15 cells are measured that way.
- **Docxodus** opens a read-only, paginated view. Lanes that edit switch it to its block editor before the timed interval starts, so its load times are those of the paginated view.
- **The complex document.** It carries Word's document protection. The lanes that edit it, and C10, which scrolls it, open a copy with that protection removed; the lanes that only load it open the original. GenOffice and eigenpal honour the protection by opening the document read-only.
- **The 500,000-word document.** It was added after the campaign (issue #188), for the criteria that only load a document: C11, C12 and C15 in the document lane, and a rung of C14. Each wait of its load may last 1,000 seconds. The lanes that edit, type, scroll or measure memory stop at 250,000 words. Its eight jobs (160 to 167) ran after the campaign's own, and were measured again in the last round with every other job of the document lane.
- **The harness's own work inside a load (issue #206).** To check what an editor shows, the harness reads the document's text from the page while the load is timed. Its search for the document's opening headings grew with the square of the page: on a long document whose paragraphs and headings sit side by side in the page, it ran for many minutes inside the timed interval of C11 and C14, and the first tables gave that time to the editor. The search now grows with the page, and the tick that stamps the usable moment no longer builds the text at all. Every job of the document lane was measured again, for every editor. What remains is recorded with each load (`probe_scan_ms_at_text`) and is inside the C11 and C14 times. Share of the C11 load that is the harness's own text read, at the document size where it is largest: canvas-editor + plugin 10.5 percent (prose-50kw); eigenpal 1.3 percent (prose-500w); GenOffice 1.3 percent (prose-5kw); Plate.js 3.4 percent (prose-500kw); SuperDoc 1.3 percent (prose-5kw); under 1 percent for Docxodus, Folio. canvas-editor's share is the largest because the harness reads its text from the editor's model; no such read is recorded for Docen and WordCraft. The recorded figure is the text read alone: for canvas-editor the same tick also hashes the first page's canvas, which is not in it, so its share is a lower bound (issue #221).
- **A frame that was only a caret (issue #207).** C08 (paste) and C09 (undo) end at the first frame that differs from the picture before the keystroke. Editors that draw their own caret change a few pixels on their own, and such a frame was taken for the paste: the same cell held samples of a few milliseconds and of several hundred. C08, and WordCraft's C09, now wait for a frame in which at least 100 pixels changed; a pasted block changes tens of thousands. Every job of the input lane was measured again, for every editor. C09 for the other editors undoes one typed character, which changes fewer pixels than that, so it keeps the smaller threshold: read a C09 figure of a few milliseconds with that in mind.
- **Typing tolerance.** GenOffice turns autocorrect on by default (Word's defaults except sentence capitalisation). The typing check compares the whole typed text after three folds: typographic quotes, backticks and guillemets count as straight quotes; (c), (r) and (tm), in either case, may become ©, ® and ™; and any run of whitespace (spaces, tabs, non-breaking spaces, line breaks) counts as one space. A typed list marker (`1.`, `a.`, `(i)`) is excused when the editor turned that line into a real list item, or when the editor painted another marker in its place (a renumbered `1.` shown as `2.`, or a line holding only a marker); in this run every excused marker was of the first kind. A missing or extra character still fails.
- **Waiting for a paint.** Where a criterion times the editor's response to the harness's own change (a keystroke, a paste, a reflow, the document's first frame in C11), the sample ends at the first screencast frame that differs from the picture taken before the change; the input lanes also check that frame for the typed character's own ink. The harness then waits at least the criterion's window for that frame, and longer while the page does not answer it: frames are recorded the whole time and read in order, so a busy editor's late frame is its real response and is kept. An editor whose page stayed idle and painted only after the window is refused instead (`paint_witness_unavailable`). No such refusal occurs in C05, C06 or C12. It occurs in C08 at 250,000 words for SuperDoc, in every launch, and for canvas-editor, in most: within the 2-second window only the caret changed, so the paste has no figure there. It also occurs in one of GenOffice's C11 launches at 500,000 words. C14's damage window is different: it classifies, and a frame outside it does not count (issue #203).
- **C14's text check.** Each prose document of the C14 ladder ends with lines of combining marks, characters outside the Basic Multilingual Plane, emoji sequences and right-to-left text; C14 checks (I01 to I03) that they survive in the editor's text, read from its first and last 4,000 characters. Folio and SuperDoc mount only the pages near the start of a long document, and WordCraft paints into a canvas, so for these three the page holds only part of the text. After the timed sample, and outside it, the harness asks each of them for the whole document: SuperDoc through its document model, Folio through its editing layer (mounted by a click on the page), and WordCraft through its own select-all and copy. For the other editors the text the harness already reads is the whole document: from the page for Plate, Docxodus and GenOffice, and from the editor's model for canvas-editor, Docen and eigenpal. C14 gives each wait of a document's load (navigation, the editor's ready signal, the page's load event for the canvas editors Docen and WordCraft, the painted document) up to 1,000 seconds. The complex document carries no such lines, so the check does not apply to it: its C14 cells are timings whose text is not checked. When the check fails, the harness names the cause: an editor whose text could not be read, or whose readable text is a window shorter than nine tenths of the document and stops before its closing paragraph, is withheld as "not checkable", a limit of the harness rather than a fault of the editor; an editor whose whole document was read and still fails keeps the failure.
- **Criteria our harness could not time.** canvas-editor, Docen and WordCraft paint their text on a canvas, without glyph geometry the harness can read. Their C05 and C06 are timed by the settled-pixel witness (issue #245): the harness records every frame after the key press, takes the picture the caret's line has once it is quiet, masks what blinks and the caret's own columns, and ends the time at the first frame that shows that whole change; it prints a time only when the editor also confirms the edit (canvas-editor and Docen through their document model, WordCraft by a count of the document's text after the keys). A key press whose change is too small to be a character, does not touch the caret, or does not go quiet is refused. canvas-editor's page does not finish opening the complex document in this lane, so it has no typing time there. Before the witness was used, a trial run (traced, and no part of the figures) read it beside the glyph witness on the 6 editors that have glyph geometry: on 368 of 384 key presses the two ended on the same frame. The 16 that differed were all Folio's first key of a burst, where the glyph witness ended 33 to 100 ms later. Frames of that key show the character on screen at the earlier frame and the caret being drawn again, inside the character's outline, at the later one: the glyph witness reads Folio's first key of a burst late, so Folio's burst figure, the middle of three keys, is in effect the larger of its other two (issue #253, not yet corrected). C15 (search and replace) was not measured for any editor in this run, and that is a gap in our harness, not in the editors. The probe drives find only through a find box in the page, and no host was configured with one. Docen and GenOffice open a find box on Ctrl+F in the hosts we measured. SuperDoc, eigenpal, Docxodus and canvas-editor ship a find box that our hosts do not mount. Plate's find is an optional plugin that its default editor leaves out, Folio's playground has no control that opens its find dialog, and WordCraft paints its find dialog on a canvas, where the probe cannot type into it. The document lane also ran C15 in each of its five jobs per block, so the C15 cells are refused as a duplicate block index as well. No C15 attempt ran, so no figure is affected.
- **Chrome traces.** In every first-block job, each timed launch was followed by a separate, untimed launch that recorded a Chrome trace for diagnosis; second-block jobs ran without them, and so did most typing sessions. Traces never feed a table.
- **Throttling and steal.** The host note in Appendix B gives, per seed, the CPU steal and the samples refused for cgroup CPU throttling; a refused sample is never kept. The Spaces are containers with a CPU quota on a host shared with other tenants. The host note also gives, per seed, the range of that host's 1-minute load average read at the start and end of each job. A sample is never refused for host load: a job that ran while the host was busier is slower, and that is one reason a cell's two seeds can differ.

## Appendix E — The full tables

### C03 — first visible content

C03 ends when the editor's page raises its ready signal: the mark each editor's page sets when the editor reports the document loaded. The harness then checks, outside the timed interval, that the document's opening text is there. Each editor decides when it is ready, so C03 is not one event across editors: an editor that mounts only the first pages of a long document can be ready long before the document is laid out. C11 and C14 time the document itself.

| Editor | Workload | Measure | C03 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) Recorded reason: browser_probe: node:internal/modules/run_main:111. |
| Docen | complex-corpus | process_cold_fs_warm | 1392.0 ms; 0% sub-frame launches; p90 1504.6 ms; n = 10 of 10 |
| Docxodus | complex-corpus | process_cold_fs_warm | 2980.0 ms; 0% sub-frame launches; p90 2999.3 ms; n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 903.5 ms; 0% sub-frame launches; p90 937.8 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 889.0 ms; 0% sub-frame launches; p90 904.6 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 1295.5 ms; 0% sub-frame launches; p90 1329.9 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 892.5 ms; 0% sub-frame launches; p90 915.2 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 997.0 ms; 0% sub-frame launches; p90 1028.3 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | 1715.0 ms; 0% sub-frame launches; p90 1830.4 ms; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) Recorded reason: browser_probe: node:internal/modules/run_main:111. |
| Docen | complex-corpus | warm_steady | 1036.0 ms; 0% sub-frame launches; p90 1147.6 ms; n = 10 of 10 |
| Docxodus | complex-corpus | warm_steady | 2496.0 ms; 0% sub-frame launches; p90 2549.6 ms; n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 597.5 ms; 0% sub-frame launches; p90 608.9 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 505.0 ms; 0% sub-frame launches; p90 527.3 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | not reproduced (first 1082.5 ms; second 883.5 ms) |
| Plate.js | complex-corpus | warm_steady | 579.0 ms; 0% sub-frame launches; p90 613.7 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 383.0 ms; 0% sub-frame launches; p90 389.2 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | 943.5 ms; 0% sub-frame launches; p90 1102.8 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | 44949.5 ms; 0% sub-frame launches; p90 47876.0 ms; n = 10 of 10 |
| Docen | prose-250kw | process_cold_fs_warm | 9050.5 ms; 0% sub-frame launches; p90 9668.6 ms; n = 10 of 10 |
| Docxodus | prose-250kw | process_cold_fs_warm | 44168.5 ms; 0% sub-frame launches; p90 47092.3 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 5861.0 ms; 0% sub-frame launches; p90 6465.6 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | 4677.0 ms; 0% sub-frame launches; p90 5024.6 ms; n = 10 of 10 |
| GenOffice | prose-250kw | process_cold_fs_warm | 2699.0 ms; 0% sub-frame launches; p90 2924.6 ms; n = 10 of 10 |
| Plate.js | prose-250kw | process_cold_fs_warm | 18758.0 ms; 0% sub-frame launches; p90 19900.9 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | process_cold_fs_warm | 1000.0 ms; 0% sub-frame launches; p90 1026.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | process_cold_fs_warm | 3016.0 ms; 0% sub-frame launches; p90 3130.9 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | warm_steady | 51224.0 ms; 0% sub-frame launches; p90 55704.9 ms; n = 10 of 10 |
| Docen | prose-250kw | warm_steady | 8412.0 ms; 0% sub-frame launches; p90 8686.5 ms; n = 10 of 10 |
| Docxodus | prose-250kw | warm_steady | 43563.0 ms; 0% sub-frame launches; p90 47171.4 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 5575.0 ms; 0% sub-frame launches; p90 6140.5 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | 4366.0 ms; 0% sub-frame launches; p90 4616.3 ms; n = 10 of 10 |
| GenOffice | prose-250kw | warm_steady | 2443.0 ms; 0% sub-frame launches; p90 2695.4 ms; n = 10 of 10 |
| Plate.js | prose-250kw | warm_steady | 17202.0 ms; 0% sub-frame launches; p90 19075.1 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | warm_steady | 434.5 ms; 0% sub-frame launches; p90 517.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | warm_steady | 2470.0 ms; 0% sub-frame launches; p90 2678.7 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | 215.5 ms; 0% sub-frame launches; p90 221.0 ms; n = 10 of 10 |
| Docen | prose-500w | process_cold_fs_warm | 1102.5 ms; 0% sub-frame launches; p90 1176.2 ms; n = 10 of 10 |
| Docxodus | prose-500w | process_cold_fs_warm | 2445.0 ms; 0% sub-frame launches; p90 2592.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 675.0 ms; 0% sub-frame launches; p90 694.6 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 784.5 ms; 0% sub-frame launches; p90 806.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | 760.0 ms; 0% sub-frame launches; p90 790.7 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 784.0 ms; 0% sub-frame launches; p90 824.2 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 993.5 ms; 0% sub-frame launches; p90 1019.3 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | 1459.5 ms; 0% sub-frame launches; p90 1556.2 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-500w | warm_steady | 150.0 ms; 0% sub-frame launches; p90 157.8 ms; n = 10 of 10 |
| Docen | prose-500w | warm_steady | 851.5 ms; 0% sub-frame launches; p90 874.4 ms; n = 10 of 10 |
| Docxodus | prose-500w | warm_steady | 2116.5 ms; 0% sub-frame launches; p90 2262.9 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 458.5 ms; 0% sub-frame launches; p90 547.5 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 473.5 ms; 0% sub-frame launches; p90 520.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 438.0 ms; 0% sub-frame launches; p90 478.2 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 512.5 ms; 0% sub-frame launches; p90 549.9 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 389.5 ms; 0% sub-frame launches; p90 395.4 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | 867.0 ms; 0% sub-frame launches; p90 936.1 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | 5210.5 ms; 0% sub-frame launches; p90 5431.9 ms; n = 10 of 10 |
| Docen | prose-50kw | process_cold_fs_warm | 2564.0 ms; 0% sub-frame launches; p90 2612.3 ms; n = 10 of 10 |
| Docxodus | prose-50kw | process_cold_fs_warm | 10154.0 ms; 0% sub-frame launches; p90 10388.7 ms; n = 10 of 10 |
| eigenpal | prose-50kw | process_cold_fs_warm | 1870.0 ms; 0% sub-frame launches; p90 1973.5 ms; n = 10 of 10 |
| Folio | prose-50kw | process_cold_fs_warm | 1687.5 ms; 0% sub-frame launches; p90 1737.1 ms; n = 10 of 10 |
| GenOffice | prose-50kw | process_cold_fs_warm | 1424.0 ms; 0% sub-frame launches; p90 1476.5 ms; n = 10 of 10 |
| Plate.js | prose-50kw | process_cold_fs_warm | 4269.5 ms; 0% sub-frame launches; p90 4441.6 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | process_cold_fs_warm | 988.0 ms; 0% sub-frame launches; p90 1033.7 ms; n = 10 of 10 |
| WordCraft | prose-50kw | process_cold_fs_warm | 1866.5 ms; 0% sub-frame launches; p90 2388.7 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-50kw | warm_steady | 4533.5 ms; 0% sub-frame launches; p90 5043.7 ms; n = 10 of 10 |
| Docen | prose-50kw | warm_steady | 2408.0 ms; 0% sub-frame launches; p90 2651.9 ms; n = 10 of 10 |
| Docxodus | prose-50kw | warm_steady | 9300.0 ms; 0% sub-frame launches; p90 9849.0 ms; n = 10 of 10 |
| eigenpal | prose-50kw | warm_steady | 1538.0 ms; 0% sub-frame launches; p90 1825.6 ms; n = 10 of 10 |
| Folio | prose-50kw | warm_steady | 1316.0 ms; 0% sub-frame launches; p90 1360.7 ms; n = 10 of 10 |
| GenOffice | prose-50kw | warm_steady | 1199.0 ms; 0% sub-frame launches; p90 1232.6 ms; n = 10 of 10 |
| Plate.js | prose-50kw | warm_steady | 3778.0 ms; 0% sub-frame launches; p90 4450.6 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | warm_steady | 387.0 ms; 0% sub-frame launches; p90 431.2 ms; n = 10 of 10 |
| WordCraft | prose-50kw | warm_steady | 1313.0 ms; 0% sub-frame launches; p90 1384.0 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | 665.0 ms; 0% sub-frame launches; p90 685.5 ms; n = 10 of 10 |
| Docen | prose-5kw | process_cold_fs_warm | 1395.5 ms; 0% sub-frame launches; p90 1563.1 ms; n = 10 of 10 |
| Docxodus | prose-5kw | process_cold_fs_warm | 3399.5 ms; 0% sub-frame launches; p90 3784.8 ms; n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | not reproduced (first 1020.0 ms; second 917.5 ms) |
| Folio | prose-5kw | process_cold_fs_warm | 938.0 ms; 0% sub-frame launches; p90 1144.0 ms; n = 10 of 10 |
| GenOffice | prose-5kw | process_cold_fs_warm | 940.0 ms; 0% sub-frame launches; p90 1391.3 ms; n = 10 of 10 |
| Plate.js | prose-5kw | process_cold_fs_warm | 1199.0 ms; 0% sub-frame launches; p90 1279.5 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | 1035.0 ms; 0% sub-frame launches; p90 1083.8 ms; n = 10 of 10 |
| WordCraft | prose-5kw | process_cold_fs_warm | 1641.5 ms; 0% sub-frame launches; p90 1749.5 ms; n = 10 of 10 |
| canvas-editor + plugin | prose-5kw | warm_steady | 521.0 ms; 0% sub-frame launches; p90 564.2 ms; n = 10 of 10 |
| Docen | prose-5kw | warm_steady | 1082.0 ms; 0% sub-frame launches; p90 1304.9 ms; n = 10 of 10 |
| Docxodus | prose-5kw | warm_steady | 2772.0 ms; 0% sub-frame launches; p90 2904.2 ms; n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | 796.5 ms; 0% sub-frame launches; p90 857.7 ms; n = 10 of 10 |
| Folio | prose-5kw | warm_steady | 602.0 ms; 0% sub-frame launches; p90 633.2 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 655.0 ms; 0% sub-frame launches; p90 722.0 ms; n = 10 of 10 |
| Plate.js | prose-5kw | warm_steady | 823.5 ms; 0% sub-frame launches; p90 837.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | 394.5 ms; 0% sub-frame launches; p90 413.7 ms; n = 10 of 10 |
| WordCraft | prose-5kw | warm_steady | 927.5 ms; 0% sub-frame launches; p90 1076.5 ms; n = 10 of 10 |

### C04 — deferred work

C04 asks whether the editor keeps working after the document is ready. Ready is the moment the harness sees the editor's ready signal: work that blocks the page before then delays that moment, and counts in the load lanes (C11), not here. The clock runs from ready to the last DOM mutation, long task or main-thread gap over 200 ms, ending once 200 ms pass with none of them. A load with none of them has no deferred work: no sample is recorded and the load counts as not applicable. The harness reads the clock for ready after its own readiness wait returns, so work an editor does in the short span between its signal and that reading counts as load, not as deferred work (issue #221). The observer of long tasks also receives the long tasks recorded during load, delivered about 2 ms after ready. Until issue #205 the harness counted them as deferred work, so every editor showed about 2 ms. A long task has ended by the time it is delivered, so one whose delivery time minus its duration falls before ready began before ready. The reader drops those from the records, and the fixed harness, which sees each task's start, no longer counts them. An editor whose loads all had only those tasks reads "no deferred work after ready". WordCraft runs its own long task 250 to 520 ms after ready in most loads, and its figure is the median of those loads.

| Editor | Workload | C04 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docxodus | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| eigenpal | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Folio | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| GenOffice | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Plate.js | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| SuperDoc | complex-corpus | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| WordCraft | complex-corpus | 951.0 ms; range 255.9 to 2577.9 ms; n = 8 of 10; 2 of 10 launches failed: not_applicable: 2; second: 3 of 10 launches failed: not_applicable: 3 |
| canvas-editor + plugin | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docen | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docxodus | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| eigenpal | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Folio | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| GenOffice | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Plate.js | prose-250kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| SuperDoc | prose-250kw | first: not enough samples (n = 4 of 10; reasons not_applicable: 6) Recorded reason: no_deferred_work. |
| WordCraft | prose-250kw | 479.5 ms; range 442.9 to 2549.6 ms; n = 6 of 10; 4 of 10 launches failed: not_applicable: 4; second: 5 of 10 launches failed: not_applicable: 5 |
| canvas-editor + plugin | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docen | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docxodus | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| eigenpal | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Folio | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| GenOffice | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Plate.js | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| SuperDoc | prose-500w | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| WordCraft | prose-500w | not reproduced (first 664.9 ms; second 886.9 ms); first: 2 of 10 launches failed: not_applicable: 2; second: 3 of 10 launches failed: not_applicable: 3 Recorded reason: no_deferred_work. |
| canvas-editor + plugin | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docen | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docxodus | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| eigenpal | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Folio | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| GenOffice | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Plate.js | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| SuperDoc | prose-50kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| WordCraft | prose-50kw | second: not enough samples (n = 4 of 10; reasons not_applicable: 6) Recorded reason: no_deferred_work. |
| canvas-editor + plugin | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docen | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Docxodus | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| eigenpal | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Folio | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| GenOffice | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| Plate.js | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| SuperDoc | prose-5kw | first seed: 0 of 10 launches kept (not_applicable 10) Recorded reason: no_deferred_work. |
| WordCraft | prose-5kw | first: not enough samples (n = 4 of 10; reasons not_applicable: 6); second: not enough samples (n = 2 of 10; reasons not_applicable: 8) Recorded reason: no_deferred_work. |

### C05 — single-edit responsiveness

| Editor | Workload | Measure | C05 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) Recorded reason: browser_probe: node:internal/modules/run_main:111. |
| Docen | complex-corpus | process_cold_fs_warm | 471.8 ms; 0% sub-frame launches; p90 497.9 ms; n = 10 of 10; by pixels, least change on any key press 3467 pixels (#245) |
| Docxodus | complex-corpus | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 37.1 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 59.3 ms; 0% sub-frame launches; p90 63.1 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 28.4 ms; 0% sub-frame launches; p90 38.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 40.7 ms; 0% sub-frame launches; p90 51.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 228.9 ms; 0% sub-frame launches; p90 240.9 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | 128.6 ms; 0% sub-frame launches; p90 153.5 ms; n = 10 of 10; by pixels, least change on any key press 23 pixels (#245) |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) Recorded reason: browser_probe: node:internal/modules/run_main:111. |
| Docen | complex-corpus | warm_steady | 466.4 ms; 0% sub-frame launches; p90 480.2 ms; n = 10 of 10; by pixels, least change on any key press 3467 pixels (#245) |
| Docxodus | complex-corpus | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 42.4 ms; 0% sub-frame launches; p90 48.1 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 51.3 ms; 0% sub-frame launches; p90 56.2 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | 25.8 ms; 20% sub-frame launches; p90 28.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | warm_steady | 24.1 ms; 0% sub-frame launches; p90 32.3 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 219.3 ms; 0% sub-frame launches; p90 222.7 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | 120.6 ms; 0% sub-frame launches; p90 132.4 ms; n = 10 of 10; by pixels, least change on any key press 23 pixels (#245) |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | 15733.6 ms; 0% sub-frame launches; p90 17472.5 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-250kw | process_cold_fs_warm | 6793.8 ms; 0% sub-frame launches; p90 7703.0 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-250kw | process_cold_fs_warm | 32.9 ms; 0% sub-frame launches; p90 36.4 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 85.1 ms; 0% sub-frame launches; p90 95.6 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | 442.7 ms; 0% sub-frame launches; p90 469.5 ms; n = 10 of 10 |
| GenOffice | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 4 of 10; reasons unverified: 6) Recorded reason: expected_edit_not_confirmed. |
| Plate.js | prose-250kw | process_cold_fs_warm | 175.2 ms; 0% sub-frame launches; p90 188.4 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | process_cold_fs_warm | 549.2 ms; 0% sub-frame launches; p90 616.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | process_cold_fs_warm | 264.1 ms; 0% sub-frame launches; p90 345.5 ms; n = 10 of 10; by pixels, least change on any key press 498 pixels (#245) |
| canvas-editor + plugin | prose-250kw | warm_steady | 16482.4 ms; 0% sub-frame launches; p90 17181.8 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-250kw | warm_steady | 7397.4 ms; 0% sub-frame launches; p90 8034.2 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-250kw | warm_steady | 27.6 ms; 0% sub-frame launches; p90 32.8 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 76.7 ms; 0% sub-frame launches; p90 85.4 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | 427.2 ms; 0% sub-frame launches; p90 476.9 ms; n = 10 of 10 |
| GenOffice | prose-250kw | warm_steady | second: not enough samples (n = 4 of 10; reasons unverified: 6) Recorded reason: expected_edit_not_confirmed. |
| Plate.js | prose-250kw | warm_steady | 129.7 ms; 0% sub-frame launches; p90 149.3 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | warm_steady | 557.2 ms; 0% sub-frame launches; p90 602.8 ms; n = 10 of 10 |
| WordCraft | prose-250kw | warm_steady | 234.4 ms; 0% sub-frame launches; p90 245.2 ms; n = 10 of 10; by pixels, least change on any key press 498 pixels (#245) |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | 77.3 ms; 0% sub-frame launches; p90 79.9 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-500w | process_cold_fs_warm | 51.3 ms; 0% sub-frame launches; p90 61.7 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 70% sub-frame launches; p90 17.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 60.1 ms; 0% sub-frame launches; p90 61.2 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 51.3 ms; 0% sub-frame launches; p90 58.8 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | 25.6 ms; 20% sub-frame launches; p90 30.6 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 47.3 ms; 0% sub-frame launches; p90 51.2 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 148.9 ms; 0% sub-frame launches; p90 153.2 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | 142.4 ms; 0% sub-frame launches; p90 165.9 ms; n = 10 of 10; by pixels, least change on any key press 498 pixels (#245) |
| canvas-editor + plugin | prose-500w | warm_steady | 66.9 ms; 0% sub-frame launches; p90 75.5 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-500w | warm_steady | 45.3 ms; 0% sub-frame launches; p90 65.2 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-500w | warm_steady | < 1 frame (16.7 ms); 60% sub-frame launches; p90 19.5 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 46.2 ms; 0% sub-frame launches; p90 50.2 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 45.2 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 17.5 ms; 30% sub-frame launches; p90 26.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 22.9 ms; 0% sub-frame launches; p90 27.1 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 137.4 ms; 0% sub-frame launches; p90 139.7 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | 124.4 ms; 0% sub-frame launches; p90 129.2 ms; n = 10 of 10; by pixels, least change on any key press 498 pixels (#245) |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | 3090.0 ms; 0% sub-frame launches; p90 3245.2 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-50kw | process_cold_fs_warm | 473.0 ms; 0% sub-frame launches; p90 541.5 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-50kw | process_cold_fs_warm | < 1 frame (16.7 ms); 60% sub-frame launches; p90 20.2 ms; n = 10 of 10 |
| eigenpal | prose-50kw | process_cold_fs_warm | 65.1 ms; 0% sub-frame launches; p90 71.5 ms; n = 10 of 10 |
| Folio | prose-50kw | process_cold_fs_warm | 119.2 ms; 0% sub-frame launches; p90 132.1 ms; n = 10 of 10 |
| GenOffice | prose-50kw | process_cold_fs_warm | 148.4 ms; 0% sub-frame launches; p90 162.3 ms; n = 10 of 10 |
| Plate.js | prose-50kw | process_cold_fs_warm | 70.3 ms; 0% sub-frame launches; p90 79.5 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | process_cold_fs_warm | 458.9 ms; 0% sub-frame launches; p90 502.6 ms; n = 10 of 10 |
| WordCraft | prose-50kw | process_cold_fs_warm | not reproduced (first 178.1 ms; second 158.4 ms) |
| canvas-editor + plugin | prose-50kw | warm_steady | 2974.5 ms; 0% sub-frame launches; p90 3020.5 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-50kw | warm_steady | 452.2 ms; 0% sub-frame launches; p90 513.0 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-50kw | warm_steady | 17.5 ms; 30% sub-frame launches; p90 20.0 ms; n = 10 of 10 |
| eigenpal | prose-50kw | warm_steady | 56.5 ms; 0% sub-frame launches; p90 62.6 ms; n = 10 of 10 |
| Folio | prose-50kw | warm_steady | 122.4 ms; 0% sub-frame launches; p90 124.1 ms; n = 10 of 10 |
| GenOffice | prose-50kw | warm_steady | 152.8 ms; 0% sub-frame launches; p90 188.4 ms; n = 10 of 10 |
| Plate.js | prose-50kw | warm_steady | 48.7 ms; 0% sub-frame launches; p90 54.6 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | warm_steady | 441.8 ms; 0% sub-frame launches; p90 461.0 ms; n = 10 of 10 |
| WordCraft | prose-50kw | warm_steady | 159.0 ms; 0% sub-frame launches; p90 179.6 ms; n = 10 of 10; by pixels, least change on any key press 498 pixels (#245) |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | 405.5 ms; 0% sub-frame launches; p90 428.3 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-5kw | process_cold_fs_warm | 94.2 ms; 0% sub-frame launches; p90 96.3 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-5kw | process_cold_fs_warm | < 1 frame (16.7 ms); 70% sub-frame launches; p90 18.9 ms; n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | 72.0 ms; 0% sub-frame launches; p90 79.5 ms; n = 10 of 10 |
| Folio | prose-5kw | process_cold_fs_warm | 56.4 ms; 0% sub-frame launches; p90 73.5 ms; n = 10 of 10 |
| GenOffice | prose-5kw | process_cold_fs_warm | 32.3 ms; 0% sub-frame launches; p90 35.7 ms; n = 10 of 10 |
| Plate.js | prose-5kw | process_cold_fs_warm | 49.0 ms; 0% sub-frame launches; p90 57.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | 301.1 ms; 0% sub-frame launches; p90 335.8 ms; n = 10 of 10 |
| WordCraft | prose-5kw | process_cold_fs_warm | 161.5 ms; 0% sub-frame launches; p90 177.3 ms; n = 10 of 10; by pixels, least change on any key press 498 pixels (#245) |
| canvas-editor + plugin | prose-5kw | warm_steady | 352.5 ms; 0% sub-frame launches; p90 363.2 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-5kw | warm_steady | 76.0 ms; 0% sub-frame launches; p90 93.6 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-5kw | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.1 ms; n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | 45.8 ms; 0% sub-frame launches; p90 52.7 ms; n = 10 of 10 |
| Folio | prose-5kw | warm_steady | 44.7 ms; 0% sub-frame launches; p90 48.0 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 26.7 ms; 10% sub-frame launches; p90 31.2 ms; n = 10 of 10 |
| Plate.js | prose-5kw | warm_steady | 27.1 ms; 0% sub-frame launches; p90 32.1 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | 286.2 ms; 0% sub-frame launches; p90 317.3 ms; n = 10 of 10 |
| WordCraft | prose-5kw | warm_steady | 139.9 ms; 0% sub-frame launches; p90 199.8 ms; n = 10 of 10; by pixels, least change on any key press 498 pixels (#245) |

### C06 — sustained typing

| Editor | Workload | Measure | C06 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) Recorded reason: browser_probe: node:internal/modules/run_main:111. |
| Docen | complex-corpus | process_cold_fs_warm | 53.4 ms; 0% sub-frame launches; p90 61.5 ms; n = 10 of 10; by pixels, least change on any key press 3385 pixels (#245) |
| Docxodus | complex-corpus | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 16.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | process_cold_fs_warm | 39.8 ms; 0% sub-frame launches; p90 42.6 ms; n = 10 of 10 |
| Folio | complex-corpus | process_cold_fs_warm | 54.1 ms; 0% sub-frame launches; p90 66.4 ms; n = 10 of 10 |
| GenOffice | complex-corpus | process_cold_fs_warm | 21.4 ms; 10% sub-frame launches; p90 23.1 ms; n = 10 of 10 |
| Plate.js | complex-corpus | process_cold_fs_warm | 25.1 ms; 0% sub-frame launches; p90 29.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | process_cold_fs_warm | 126.0 ms; 0% sub-frame launches; p90 134.9 ms; n = 10 of 10 |
| WordCraft | complex-corpus | process_cold_fs_warm | 123.0 ms; 0% sub-frame launches; p90 137.0 ms; n = 10 of 10; by pixels, least change on any key press 17 pixels (#245) |
| canvas-editor + plugin | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) Recorded reason: browser_probe: node:internal/modules/run_main:111. |
| Docen | complex-corpus | warm_steady | 57.2 ms; 0% sub-frame launches; p90 60.0 ms; n = 10 of 10; by pixels, least change on any key press 3385 pixels (#245) |
| Docxodus | complex-corpus | warm_steady | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | complex-corpus | warm_steady | 43.1 ms; 0% sub-frame launches; p90 44.9 ms; n = 10 of 10 |
| Folio | complex-corpus | warm_steady | 53.4 ms; 0% sub-frame launches; p90 66.3 ms; n = 10 of 10 |
| GenOffice | complex-corpus | warm_steady | 21.8 ms; 20% sub-frame launches; p90 25.7 ms; n = 10 of 10 |
| Plate.js | complex-corpus | warm_steady | 21.7 ms; 0% sub-frame launches; p90 26.4 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | warm_steady | 121.6 ms; 0% sub-frame launches; p90 132.8 ms; n = 10 of 10 |
| WordCraft | complex-corpus | warm_steady | 118.9 ms; 0% sub-frame launches; p90 124.5 ms; n = 10 of 10; by pixels, least change on any key press 17 pixels (#245) |
| canvas-editor + plugin | prose-250kw | process_cold_fs_warm | 17591.0 ms; 0% sub-frame launches; p90 18034.6 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-250kw | process_cold_fs_warm | 8004.8 ms; 0% sub-frame launches; p90 8342.9 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-250kw | process_cold_fs_warm | 29.0 ms; 0% sub-frame launches; p90 32.2 ms; n = 10 of 10 |
| eigenpal | prose-250kw | process_cold_fs_warm | 59.8 ms; 0% sub-frame launches; p90 68.4 ms; n = 10 of 10 |
| Folio | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: expected_edit_not_confirmed. |
| GenOffice | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 3 of 10; reasons unverified: 7) Recorded reason: expected_edit_not_confirmed. |
| Plate.js | prose-250kw | process_cold_fs_warm | 129.6 ms; 0% sub-frame launches; p90 140.5 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | process_cold_fs_warm | 313.2 ms; 0% sub-frame launches; range 286.1 to 410.3 ms; n = 9 of 10; 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-250kw | process_cold_fs_warm | 236.8 ms; 0% sub-frame launches; p90 253.3 ms; n = 10 of 10; by pixels, least change on any key press 662 pixels (#245) |
| canvas-editor + plugin | prose-250kw | warm_steady | 18363.2 ms; 0% sub-frame launches; p90 18754.1 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-250kw | warm_steady | 7682.0 ms; 0% sub-frame launches; p90 8004.5 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-250kw | warm_steady | 27.6 ms; 0% sub-frame launches; p90 32.8 ms; n = 10 of 10 |
| eigenpal | prose-250kw | warm_steady | 60.7 ms; 0% sub-frame launches; p90 75.1 ms; n = 10 of 10 |
| Folio | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: expected_edit_not_confirmed. |
| GenOffice | prose-250kw | warm_steady | second: not enough samples (n = 3 of 10; reasons unverified: 7) Recorded reason: expected_edit_not_confirmed. |
| Plate.js | prose-250kw | warm_steady | 131.8 ms; 0% sub-frame launches; p90 147.0 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | warm_steady | 303.3 ms; 0% sub-frame launches; range 290.7 to 339.7 ms; n = 9 of 10; 1 of 10 launches failed: unverified: 1 |
| WordCraft | prose-250kw | warm_steady | 226.8 ms; 0% sub-frame launches; p90 252.6 ms; n = 10 of 10; by pixels, least change on any key press 662 pixels (#245) |
| canvas-editor + plugin | prose-500w | process_cold_fs_warm | 66.3 ms; 0% sub-frame launches; p90 80.6 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-500w | process_cold_fs_warm | 46.9 ms; 0% sub-frame launches; p90 64.5 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 16.8 ms; n = 10 of 10 |
| eigenpal | prose-500w | process_cold_fs_warm | 41.8 ms; 0% sub-frame launches; p90 46.8 ms; n = 10 of 10 |
| Folio | prose-500w | process_cold_fs_warm | 44.4 ms; 0% sub-frame launches; p90 52.3 ms; n = 10 of 10 |
| GenOffice | prose-500w | process_cold_fs_warm | < 1 frame (16.7 ms); 60% sub-frame launches; p90 21.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | process_cold_fs_warm | 22.1 ms; 0% sub-frame launches; p90 26.6 ms; n = 10 of 10 |
| SuperDoc | prose-500w | process_cold_fs_warm | 73.4 ms; 0% sub-frame launches; p90 85.4 ms; n = 10 of 10 |
| WordCraft | prose-500w | process_cold_fs_warm | 124.8 ms; 0% sub-frame launches; p90 131.4 ms; n = 10 of 10; by pixels, least change on any key press 662 pixels (#245) |
| canvas-editor + plugin | prose-500w | warm_steady | 62.4 ms; 0% sub-frame launches; p90 65.5 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-500w | warm_steady | 41.2 ms; 0% sub-frame launches; p90 52.6 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-500w | warm_steady | < 1 frame (16.7 ms); 80% sub-frame launches; p90 17.1 ms; n = 10 of 10 |
| eigenpal | prose-500w | warm_steady | 38.6 ms; 0% sub-frame launches; p90 40.0 ms; n = 10 of 10 |
| Folio | prose-500w | warm_steady | 48.7 ms; 0% sub-frame launches; p90 57.0 ms; n = 10 of 10 |
| GenOffice | prose-500w | warm_steady | 17.3 ms; 50% sub-frame launches; p90 21.1 ms; n = 10 of 10 |
| Plate.js | prose-500w | warm_steady | 22.3 ms; 0% sub-frame launches; p90 25.5 ms; n = 10 of 10 |
| SuperDoc | prose-500w | warm_steady | 76.6 ms; 0% sub-frame launches; p90 82.7 ms; n = 10 of 10 |
| WordCraft | prose-500w | warm_steady | 122.6 ms; 0% sub-frame launches; p90 130.1 ms; n = 10 of 10; by pixels, least change on any key press 662 pixels (#245) |
| canvas-editor + plugin | prose-50kw | process_cold_fs_warm | 3076.8 ms; 0% sub-frame launches; p90 3170.8 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-50kw | process_cold_fs_warm | 488.9 ms; 0% sub-frame launches; p90 596.4 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-50kw | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-50kw | process_cold_fs_warm | 54.9 ms; 0% sub-frame launches; p90 56.7 ms; n = 10 of 10 |
| Folio | prose-50kw | process_cold_fs_warm | 117.9 ms; 0% sub-frame launches; p90 121.0 ms; n = 10 of 10 |
| GenOffice | prose-50kw | process_cold_fs_warm | 130.7 ms; 0% sub-frame launches; p90 142.6 ms; n = 10 of 10 |
| Plate.js | prose-50kw | process_cold_fs_warm | 40.6 ms; 0% sub-frame launches; p90 43.6 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | process_cold_fs_warm | 296.5 ms; 0% sub-frame launches; p90 303.3 ms; n = 10 of 10 |
| WordCraft | prose-50kw | process_cold_fs_warm | 155.1 ms; 0% sub-frame launches; p90 167.1 ms; n = 10 of 10; by pixels, least change on any key press 662 pixels (#245) |
| canvas-editor + plugin | prose-50kw | warm_steady | 3032.0 ms; 0% sub-frame launches; p90 3425.1 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docen | prose-50kw | warm_steady | 467.5 ms; 0% sub-frame launches; p90 490.1 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-50kw | warm_steady | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-50kw | warm_steady | 50.3 ms; 0% sub-frame launches; p90 57.6 ms; n = 10 of 10 |
| Folio | prose-50kw | warm_steady | 106.0 ms; 0% sub-frame launches; p90 120.4 ms; n = 10 of 10 |
| GenOffice | prose-50kw | warm_steady | 151.7 ms; 0% sub-frame launches; p90 165.5 ms; n = 10 of 10 |
| Plate.js | prose-50kw | warm_steady | 44.5 ms; 0% sub-frame launches; p90 49.4 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | warm_steady | 276.1 ms; 0% sub-frame launches; p90 288.7 ms; n = 10 of 10 |
| WordCraft | prose-50kw | warm_steady | 145.2 ms; 0% sub-frame launches; p90 156.3 ms; n = 10 of 10; by pixels, least change on any key press 662 pixels (#245) |
| canvas-editor + plugin | prose-5kw | process_cold_fs_warm | 359.1 ms; 0% sub-frame launches; p90 384.8 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245); second: 1 of 10 launches failed: crash: 1 |
| Docen | prose-5kw | process_cold_fs_warm | 82.0 ms; 0% sub-frame launches; p90 90.9 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-5kw | process_cold_fs_warm | < 1 frame (16.7 ms); 90% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-5kw | process_cold_fs_warm | 44.0 ms; 0% sub-frame launches; p90 55.1 ms; n = 10 of 10 |
| Folio | prose-5kw | process_cold_fs_warm | 49.9 ms; 0% sub-frame launches; p90 59.3 ms; n = 10 of 10 |
| GenOffice | prose-5kw | process_cold_fs_warm | 22.4 ms; 0% sub-frame launches; range 17.7 to 30.4 ms; n = 9 of 10; 1 of 10 launches failed: crash: 1 |
| Plate.js | prose-5kw | process_cold_fs_warm | 24.6 ms; 0% sub-frame launches; p90 27.9 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | process_cold_fs_warm | 176.1 ms; 0% sub-frame launches; p90 189.0 ms; n = 10 of 10 |
| WordCraft | prose-5kw | process_cold_fs_warm | 127.9 ms; 0% sub-frame launches; p90 137.9 ms; n = 10 of 10; by pixels, least change on any key press 662 pixels (#245) |
| canvas-editor + plugin | prose-5kw | warm_steady | 373.0 ms; 0% sub-frame launches; p90 410.7 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245); second: 1 of 10 launches failed: crash: 1 |
| Docen | prose-5kw | warm_steady | 79.1 ms; 0% sub-frame launches; p90 87.0 ms; n = 10 of 10; by pixels, least change on any key press 29 pixels (#245) |
| Docxodus | prose-5kw | warm_steady | < 1 frame (16.7 ms); 100% sub-frame launches; p90 < 1 frame (16.7 ms); n = 10 of 10 |
| eigenpal | prose-5kw | warm_steady | 46.2 ms; 0% sub-frame launches; p90 59.5 ms; n = 10 of 10 |
| Folio | prose-5kw | warm_steady | 48.0 ms; 0% sub-frame launches; p90 62.2 ms; n = 10 of 10 |
| GenOffice | prose-5kw | warm_steady | 21.9 ms; 0% sub-frame launches; range 19.2 to 28.7 ms; n = 9 of 10; 1 of 10 launches failed: crash: 1 |
| Plate.js | prose-5kw | warm_steady | 23.8 ms; 10% sub-frame launches; p90 30.6 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | warm_steady | 175.2 ms; 0% sub-frame launches; p90 203.4 ms; n = 10 of 10 |
| WordCraft | prose-5kw | warm_steady | 122.3 ms; 0% sub-frame launches; p90 128.9 ms; n = 10 of 10; by pixels, least change on any key press 662 pixels (#245) |

### C07 — cursor and selection

| Editor | Workload | C07 |
|---|---|---|
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
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
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: correctness: probe_not_restored. |
| Docxodus | complex-corpus | < 1 frame (16.7 ms); 60% sub-frame launches; p90 20.0 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 71.0 ms; 0% sub-frame launches; p90 79.5 ms; n = 10 of 10 |
| Folio | complex-corpus | 62.9 ms; 0% sub-frame launches; p90 66.2 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 30.6 ms; 0% sub-frame launches; p90 36.0 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 32.5 ms; 0% sub-frame launches; p90 36.8 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 230.7 ms; 0% sub-frame launches; p90 246.3 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10); second: not enough samples (n = 0 of 10; reasons click_points_on_editor_chrome: 10) |
| canvas-editor + plugin | prose-250kw | first: not enough samples (n = 2 of 10; reasons crash: 1; paint_witness_unavailable: 7); second: not enough samples (n = 2 of 10; reasons paint_witness_unavailable: 8) Recorded reasons: no_painted_frame; page_lost: Error: page.evaluate: Target crashed; page_lost: Error: page.evaluate: Target crashed ; page_lost: Error: keyboard.press: Target crashed. |
| Docen | prose-250kw | 9378.3 ms; 0% sub-frame launches; p90 10115.5 ms; n = 10 of 10 |
| Docxodus | prose-250kw | < 1 frame (16.7 ms); 50% sub-frame launches; p90 21.6 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 107.4 ms; 0% sub-frame launches; p90 111.5 ms; n = 10 of 10 |
| Folio | prose-250kw | 425.1 ms; 0% sub-frame launches; p90 459.3 ms; n = 10 of 10 |
| GenOffice | prose-250kw | 2849.8 ms; 0% sub-frame launches; p90 4277.0 ms; n = 10 of 10 |
| Plate.js | prose-250kw | 429.2 ms; 0% sub-frame launches; p90 477.6 ms; n = 10 of 10 |
| SuperDoc | prose-250kw | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) Recorded reason: no_painted_frame. |
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
| canvas-editor + plugin | prose-50kw | first: not enough samples (n = 2 of 10; reasons unverified: 8); second: not enough samples (n = 4 of 10; reasons unverified: 6) Recorded reason: correctness: fixture_body_mismatch. |
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
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: correctness: probe_not_restored. |
| Docxodus | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: correctness: undo_did_not_restore_document_text. |
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
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10); second: not enough samples (n = 0 of 10; reasons paint_witness_unavailable: 10) Recorded reason: the probe produced no sample. |
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
| WordCraft | prose-500w | not reproduced (first 130.2 ms; second 194.5 ms); second: 1 of 10 launches failed: paint_witness_unavailable: 1 Recorded reason: anchor_lag_above_bound: the anchor frame lag 319.517 ms is above the bound of 250 ms. |
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
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
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
| canvas-editor + plugin | complex-corpus | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (docen-document shadow .canvas-pages > div (page pitch)); the only DOM box is th…. |
| Docxodus | complex-corpus | 48.4 ms; 0% sub-frame launches; p90 48.8 ms; n = 10 of 10 |
| eigenpal | complex-corpus | 73.3 ms; 0% sub-frame launches; p90 82.1 ms; n = 10 of 10 |
| Folio | complex-corpus | 65.0 ms; 0% sub-frame launches; p90 66.9 ms; n = 10 of 10 |
| GenOffice | complex-corpus | 32.1 ms; 0% sub-frame launches; p90 48.3 ms; n = 10 of 10 |
| Plate.js | complex-corpus | 65.5 ms; 0% sub-frame launches; p90 65.6 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | 373.4 ms; 0% sub-frame launches; p90 400.6 ms; n = 10 of 10 |
| WordCraft | complex-corpus | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: wordcraft exposes no document text or block geometry at this pin (one WebGL canvas; correctness is only the modified window-title bullet). |
| canvas-editor + plugin | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (#editor .ce-page-container (host paints into <canvas>)); the only DOM box is th…. |
| Docen | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (docen-document shadow .canvas-pages > div (page pitch)); the only DOM box is th…. |
| Docxodus | prose-250kw | 156.8 ms; 0% sub-frame launches; p90 168.7 ms; n = 10 of 10 |
| eigenpal | prose-250kw | 98.7 ms; 0% sub-frame launches; p90 117.0 ms; n = 10 of 10 |
| Folio | prose-250kw | 2464.2 ms; 0% sub-frame launches; p90 2561.6 ms; n = 10 of 10 |
| GenOffice | prose-250kw | not reproduced (first 2973.4 ms; second 2565.1 ms); first: 2 of 10 launches failed: recorded_move_before_input: 2; second: 1 of 10 launches failed: recorded_move_before_input: 1 Recorded reason: probe refused genoffice: recorded_move_before_input. |
| Plate.js | prose-250kw | 2248.1 ms; 0% sub-frame launches; p90 2348.1 ms; n = 10 of 10; second: 1 of 10 launches failed: cpu_throttled: 1 |
| SuperDoc | prose-250kw | 1456.8 ms; 0% sub-frame launches; p90 1483.6 ms; n = 10 of 10 |
| WordCraft | prose-250kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: wordcraft exposes no document text or block geometry at this pin (one WebGL canvas; correctness is only the modified window-title bullet). |
| canvas-editor + plugin | prose-500kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (#editor .ce-page-container (host paints into <canvas>)); the only DOM box is th…. |
| Docen | prose-500kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (docen-document shadow .canvas-pages > div (page pitch)); the only DOM box is th…. |
| Docxodus | prose-500kw | 256.7 ms; 0% sub-frame launches; range 231.6 to 298.8 ms; n = 8 of 10; 2 of 10 launches failed: recorded_move_before_input: 2; second: 2 of 10 launches failed: recorded_move_before_input: 2 |
| eigenpal | prose-500kw | not reproduced (first 81.7 ms; second 98.5 ms) |
| Folio | prose-500kw | 4870.6 ms; 0% sub-frame launches; p90 4965.4 ms; n = 10 of 10 |
| GenOffice | prose-500kw | not reproduced (first 16029.7 ms; second 12039.7 ms); first: 4 of 10 launches failed: editor_timeout: 4; second: 2 of 10 launches failed: editor_timeout: 2 Recorded reason: probe error for genoffice: locator.boundingBox: Timeout 30000ms exceeded.. |
| Plate.js | prose-500kw | 4506.0 ms; 0% sub-frame launches; p90 4830.0 ms; n = 10 of 10 |
| SuperDoc | prose-500kw | not reproduced (first 2098.6 ms; second 1782.0 ms) |
| WordCraft | prose-500kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: wordcraft exposes no document text or block geometry at this pin (one WebGL canvas; correctness is only the modified window-title bullet). |
| canvas-editor + plugin | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (#editor .ce-page-container (host paints into <canvas>)); the only DOM box is th…. |
| Docen | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (docen-document shadow .canvas-pages > div (page pitch)); the only DOM box is th…. |
| Docxodus | prose-500w | 48.8 ms; 0% sub-frame launches; p90 48.9 ms; n = 10 of 10 |
| eigenpal | prose-500w | 48.9 ms; 0% sub-frame launches; p90 48.9 ms; n = 10 of 10 |
| Folio | prose-500w | 48.8 ms; 0% sub-frame launches; p90 65.4 ms; n = 10 of 10 |
| GenOffice | prose-500w | 31.5 ms; 0% sub-frame launches; p90 32.0 ms; n = 10 of 10 |
| Plate.js | prose-500w | 48.7 ms; 0% sub-frame launches; p90 50.6 ms; n = 10 of 10 |
| SuperDoc | prose-500w | 181.6 ms; 0% sub-frame launches; p90 182.1 ms; n = 10 of 10 |
| WordCraft | prose-500w | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: wordcraft exposes no document text or block geometry at this pin (one WebGL canvas; correctness is only the modified window-title bullet). |
| canvas-editor + plugin | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (#editor .ce-page-container (host paints into <canvas>)); the only DOM box is th…. |
| Docen | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (docen-document shadow .canvas-pages > div (page pitch)); the only DOM box is th…. |
| Docxodus | prose-50kw | 64.5 ms; 0% sub-frame launches; p90 67.0 ms; n = 10 of 10 |
| eigenpal | prose-50kw | 90.0 ms; 0% sub-frame launches; p90 98.3 ms; n = 10 of 10 |
| Folio | prose-50kw | 572.9 ms; 0% sub-frame launches; p90 599.7 ms; n = 10 of 10 |
| GenOffice | prose-50kw | 173.6 ms; 0% sub-frame launches; p90 198.3 ms; n = 10 of 10 |
| Plate.js | prose-50kw | 465.3 ms; 0% sub-frame launches; p90 483.4 ms; n = 10 of 10 |
| SuperDoc | prose-50kw | 906.0 ms; 0% sub-frame launches; p90 951.3 ms; n = 10 of 10 |
| WordCraft | prose-50kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: wordcraft exposes no document text or block geometry at this pin (one WebGL canvas; correctness is only the modified window-title bullet). |
| canvas-editor + plugin | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (#editor .ce-page-container (host paints into <canvas>)); the only DOM box is th…. |
| Docen | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: no paragraph geometry to attribute a C12 y-shift: this host paints whole pages (docen-document shadow .canvas-pages > div (page pitch)); the only DOM box is th…. |
| Docxodus | prose-5kw | 48.1 ms; 0% sub-frame launches; p90 48.7 ms; n = 10 of 10 |
| eigenpal | prose-5kw | 65.4 ms; 0% sub-frame launches; p90 83.7 ms; n = 10 of 10 |
| Folio | prose-5kw | 123.4 ms; 0% sub-frame launches; p90 149.7 ms; n = 10 of 10 |
| GenOffice | prose-5kw | 31.4 ms; 0% sub-frame launches; p90 31.8 ms; n = 10 of 10 |
| Plate.js | prose-5kw | 115.4 ms; 0% sub-frame launches; p90 131.3 ms; n = 10 of 10 |
| SuperDoc | prose-5kw | 440.0 ms; 0% sub-frame launches; p90 548.5 ms; n = 10 of 10 |
| WordCraft | prose-5kw | first: not enough samples (n = 0 of 10; reasons not_applicable: 10); second: not enough samples (n = 0 of 10; reasons not_applicable: 10) Recorded reason: wordcraft exposes no document text or block geometry at this pin (one WebGL canvas; correctness is only the modified window-title bullet). |

### C13 — global invalidation

not in these runs.

### C14 — large-document scaling

Each C14 size rung is a separate measure, and within a rung each clock is its own measure: `presented_frame` (document damage followed load; the sample ends at the first compositor screencast frame at or after the document became usable) and `usable_no_damage` (no damage followed; the sample ends at the DOM document-surface mark and is never labelled a compositor frame). Rungs and measures are never pooled. The damage window is 500 ms after a settled frame, widened by the clock's measured error; a frame recorded later, while the page kept the harness waiting, is not damage inside it (issue #203). The witness looks at the last 1,200 frames the recorder kept. The campaign's records do not count dropped frames, so where more than 1,200 arrived before the witness looked, a damage frame may be gone and the sample recorded as `usable_no_damage`; the figure is still the time the text appeared (issue #221). The two measures must not be read as the same thing: a `usable_no_damage` sample is the time the text appeared in the page, not the time the document was painted (C11 times the painted frame).

| Editor | Workload | Measure | C14 |
|---|---|---|---|
| canvas-editor + plugin | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: rung complex-corpus: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | complex-corpus | presented_frame | 1729.7 ms; 0% sub-frame launches; p90 1812.7 ms; n = 10 of 10 |
| Folio | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) Recorded reason: rung prose-250kw: cpu_throttled. |
| SuperDoc | complex-corpus | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| WordCraft | complex-corpus | presented_frame | 4739.3 ms; 0% sub-frame launches; p90 4852.1 ms; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: rung complex-corpus: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | usable_no_damage | 1168.8 ms; 0% sub-frame launches; p90 1280.0 ms; n = 10 of 10 |
| Docxodus | complex-corpus | usable_no_damage | 3072.1 ms; 0% sub-frame launches; p90 3288.2 ms; n = 10 of 10 |
| eigenpal | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Folio | complex-corpus | usable_no_damage | 880.0 ms; 0% sub-frame launches; p90 993.1 ms; n = 10 of 10 |
| GenOffice | complex-corpus | usable_no_damage | 987.6 ms; 0% sub-frame launches; p90 1058.0 ms; n = 10 of 10 |
| Plate.js | complex-corpus | usable_no_damage | 879.5 ms; 0% sub-frame launches; p90 935.0 ms; n = 10 of 10 |
| SuperDoc | complex-corpus | usable_no_damage | 2714.2 ms; 0% sub-frame launches; p90 3118.3 ms; n = 10 of 10 |
| WordCraft | complex-corpus | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: rung complex-corpus: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-250kw | presented_frame | 7066.0 ms; 0% sub-frame launches; p90 7858.8 ms; n = 10 of 10 |
| Folio | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-250kw | presented_frame | first: not enough samples (n = 0 of 10; reasons cpu_throttled: 1); second: not enough samples (n = 0 of 10; reasons none counted) Recorded reason: rung prose-250kw: cpu_throttled. |
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
| GenOffice | prose-500kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons publishable_not_true: 10); second: not enough samples (n = 0 of 10; reasons publishable_not_true: 10) Recorded reason: interpretation: I01-I03 not checkable: the editor's readable text ends before the document's closing paragraph, where the correctness lines sit. |
| Plate.js | prose-500kw | usable_no_damage | 38348.7 ms; 0% sub-frame launches; p90 39007.2 ms; n = 10 of 10 |
| SuperDoc | prose-500kw | usable_no_damage | 29601.3 ms; 0% sub-frame launches; p90 30098.6 ms; n = 10 of 10 |
| WordCraft | prose-500kw | usable_no_damage | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| canvas-editor + plugin | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: rung complex-corpus: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-500w | presented_frame | 1730.2 ms; 0% sub-frame launches; p90 1831.3 ms; n = 10 of 10 |
| Folio | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-500w | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) Recorded reason: rung prose-250kw: cpu_throttled. |
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
| canvas-editor + plugin | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: rung complex-corpus: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-50kw | presented_frame | 2394.4 ms; 0% sub-frame launches; p90 3187.6 ms; n = 10 of 10 |
| Folio | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-50kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) Recorded reason: rung prose-250kw: cpu_throttled. |
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
| canvas-editor + plugin | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 10); second: not enough samples (n = 0 of 10; reasons crash: 10) Recorded reason: rung complex-corpus: editor_load_failed: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Docxodus | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| eigenpal | prose-5kw | presented_frame | 1935.8 ms; 0% sub-frame launches; p90 2036.6 ms; n = 10 of 10 |
| Folio | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| GenOffice | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons none counted); second: not enough samples (n = 0 of 10; reasons none counted) |
| Plate.js | prose-5kw | presented_frame | first: not enough samples (n = 0 of 10; reasons crash: 1); second: not enough samples (n = 0 of 10; reasons none counted) Recorded reason: rung prose-250kw: cpu_throttled. |
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
| canvas-editor + plugin | complex-corpus | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) Recorded reason: browser memory probe failed: page.waitForFunction: Error: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | after_edit_burst | 781.3 MiB; p90 806.0 MiB; n = 10 of 10 |
| Docxodus | complex-corpus | after_edit_burst | 715.3 MiB; p90 717.6 MiB; n = 10 of 10 |
| eigenpal | complex-corpus | after_edit_burst | 642.5 MiB; p90 650.3 MiB; n = 10 of 10 |
| Folio | complex-corpus | after_edit_burst | 595.9 MiB; p90 598.2 MiB; n = 10 of 10 |
| GenOffice | complex-corpus | after_edit_burst | 629.1 MiB; p90 633.5 MiB; n = 10 of 10 |
| Plate.js | complex-corpus | after_edit_burst | 629.2 MiB; p90 631.1 MiB; n = 10 of 10 |
| SuperDoc | complex-corpus | after_edit_burst | 689.3 MiB; p90 693.3 MiB; n = 10 of 10 |
| WordCraft | complex-corpus | after_edit_burst | 1137.6 MiB; p90 1157.2 MiB; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) Recorded reason: browser memory probe failed: page.waitForFunction: Error: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | quiescent | 782.6 MiB; p90 806.8 MiB; n = 10 of 10 |
| Docxodus | complex-corpus | quiescent | 715.5 MiB; p90 717.8 MiB; n = 10 of 10 |
| eigenpal | complex-corpus | quiescent | 645.8 MiB; p90 650.9 MiB; n = 10 of 10 |
| Folio | complex-corpus | quiescent | 597.1 MiB; p90 599.1 MiB; n = 10 of 10 |
| GenOffice | complex-corpus | quiescent | 638.8 MiB; p90 643.2 MiB; n = 10 of 10 |
| Plate.js | complex-corpus | quiescent | 629.3 MiB; p90 631.1 MiB; n = 10 of 10 |
| SuperDoc | complex-corpus | quiescent | 696.0 MiB; p90 700.5 MiB; n = 10 of 10 |
| WordCraft | complex-corpus | quiescent | 1137.8 MiB; p90 1155.8 MiB; n = 10 of 10 |
| canvas-editor + plugin | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) Recorded reason: browser memory probe failed: page.waitForFunction: Error: TypeError: Cannot read properties of undefined (reading 'width'). |
| Docen | complex-corpus | ready | 701.9 MiB; p90 703.1 MiB; n = 10 of 10 |
| Docxodus | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| eigenpal | complex-corpus | ready | 626.2 MiB; p90 628.6 MiB; n = 10 of 10 |
| Folio | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| GenOffice | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| Plate.js | complex-corpus | ready | 527.3 MiB; p90 529.7 MiB; n = 10 of 10 |
| SuperDoc | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| WordCraft | complex-corpus | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| canvas-editor + plugin | prose-250kw | after_edit_burst | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) Recorded reason: browser memory probe failed: page.waitForTimeout: Page crashed. |
| Docen | prose-250kw | after_edit_burst | 7544.8 MiB; p90 8603.7 MiB; n = 10 of 10 |
| Docxodus | prose-250kw | after_edit_burst | 1917.1 MiB; p90 1934.3 MiB; n = 10 of 10 |
| eigenpal | prose-250kw | after_edit_burst | 996.1 MiB; p90 1009.7 MiB; n = 10 of 10 |
| Folio | prose-250kw | after_edit_burst | 2117.8 MiB; p90 2123.9 MiB; n = 10 of 10 |
| GenOffice | prose-250kw | after_edit_burst | 2021.6 MiB; p90 2141.5 MiB; n = 10 of 10 |
| Plate.js | prose-250kw | after_edit_burst | 2053.7 MiB; p90 2072.3 MiB; n = 10 of 10 |
| SuperDoc | prose-250kw | after_edit_burst | 1359.7 MiB; p90 1421.2 MiB; n = 10 of 10 |
| WordCraft | prose-250kw | after_edit_burst | 1336.3 MiB; p90 1341.7 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | quiescent | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) Recorded reason: browser memory probe failed: page.waitForTimeout: Page crashed. |
| Docen | prose-250kw | quiescent | 7746.8 MiB; p90 8808.2 MiB; n = 10 of 10 |
| Docxodus | prose-250kw | quiescent | 1914.5 MiB; p90 1920.4 MiB; n = 10 of 10 |
| eigenpal | prose-250kw | quiescent | 996.2 MiB; p90 1009.9 MiB; n = 10 of 10 |
| Folio | prose-250kw | quiescent | 1938.1 MiB; p90 1948.9 MiB; n = 10 of 10 |
| GenOffice | prose-250kw | quiescent | 2211.7 MiB; p90 2302.1 MiB; n = 10 of 10 |
| Plate.js | prose-250kw | quiescent | 2053.7 MiB; p90 2072.4 MiB; n = 10 of 10 |
| SuperDoc | prose-250kw | quiescent | 1360.4 MiB; p90 1421.8 MiB; n = 10 of 10 |
| WordCraft | prose-250kw | quiescent | 1336.5 MiB; p90 1341.9 MiB; n = 10 of 10 |
| canvas-editor + plugin | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons editor_crash: 10); second: not enough samples (n = 0 of 10; reasons editor_crash: 10) Recorded reason: browser memory probe failed: page.waitForTimeout: Page crashed. |
| Docen | prose-250kw | ready | 4145.4 MiB; p90 4173.3 MiB; n = 10 of 10 |
| Docxodus | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| eigenpal | prose-250kw | ready | 890.8 MiB; p90 892.4 MiB; n = 10 of 10 |
| Folio | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| GenOffice | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| Plate.js | prose-250kw | ready | 1907.0 MiB; p90 1959.3 MiB; n = 10 of 10 |
| SuperDoc | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| WordCraft | prose-250kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
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
| Docxodus | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| eigenpal | prose-500w | ready | 608.4 MiB; p90 610.8 MiB; n = 10 of 10 |
| Folio | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| GenOffice | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| Plate.js | prose-500w | ready | 508.7 MiB; p90 510.0 MiB; n = 10 of 10 |
| SuperDoc | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| WordCraft | prose-500w | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
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
| Docxodus | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| eigenpal | prose-50kw | ready | 691.8 MiB; p90 694.2 MiB; n = 10 of 10 |
| Folio | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| GenOffice | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| Plate.js | prose-50kw | ready | 827.9 MiB; p90 830.7 MiB; n = 10 of 10 |
| SuperDoc | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| WordCraft | prose-50kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
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
| Docxodus | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| eigenpal | prose-5kw | ready | 636.7 MiB; p90 638.4 MiB; n = 10 of 10 |
| Folio | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| GenOffice | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| Plate.js | prose-5kw | ready | 561.3 MiB; p90 564.5 MiB; n = 10 of 10 |
| SuperDoc | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |
| WordCraft | prose-5kw | ready | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) Recorded reason: document_not_verified_loaded. |

### C19 — browser memory after the page is closed (not published)

C19 was meant to show memory an editor leaves behind. The harness read the browser's process tree 1 second and 5 seconds after closing the editor's page, and took no reading of an empty browser to subtract. What it read is therefore the browser itself, about the same for every editor and document size, and it cannot be attributed to an editor. No table is printed. In these runs the seed medians of the 43 editor and document cells that reproduced lay between 318.1 MiB and 362.5 MiB. The readings are in the dataset.

### B8 — resources while opening and editing

**B8 — resources while opening and editing.** One fresh browser per launch opens the document, waits until the editor is idle, types sixteen characters into a body line on the first screen, and waits again. CPU is the processor time of the whole browser process tree: to open (from navigation until idle, including work an editor does after it reports ready), during the edit (the keystrokes plus half a second), and while settling afterwards, where it is given per second of the readings taken during that wait, because the wait is not a fixed length (the note under the tables says how long they spanned). The memory column is the highest reading of that tree's resident memory: it is read when the load and the edit start and end and every half second while the page settles, so a higher moment in the middle of a long load or edit is not seen; a page shared by two processes counts once for each. An edit counts only when it is verified in the document: the text of the block at the caret, read from the page or from the editor's model, gained exactly the typed text; WordCraft, which puts no document text in the page, is verified by its own modified flag. An editor still working when a 30-second cap ends never went idle, even in one launch: the CPU columns that wait would end are not printed, because they would time the cap, and a note gives what it used up to its ready signal, how far its memory readings ran and, where every kept launch recorded its processes, how the capped wait divides between the browser's GPU process (the one that draws; on this host it draws in software) and the page's own process. The complex document is loaded without its read-only protection, which the editors honour.

Each cell shows the first seed's median and the second seed's median. A figure is printed as a result only when the two agree within 10 percent (20 ms for CPU; for the settling column, which is a rate, those 20 ms over the typical settling wait of the launches counted); a cell that does not agree says so and gives both medians and the lowest and highest launch, so that what was read is not hidden. The CPU counters advance in steps of 10 ms, so a cell of a few tens of milliseconds is at the counter's resolution. The host has no graphics processor: what an editor draws is drawn by the processor and counts as CPU.

### 500 words

| Editor | CPU to open | CPU of the edit | CPU per second while settling | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| canvas-editor + plugin | 485 ms / 490 ms | 1.33 s / 1.30 s | 31 ms/s / 26 ms/s | 617.8 MiB / 616.5 MiB | n = 10, 10 |
| Docen | 1.66 s / 1.63 s | 385 ms / 380 ms | wait too short to measure (10 and 1 of 10 and 10 launches waited a second or more) | 659.4 MiB / 659.1 MiB | n = 10, 10 |
| Docxodus | 4.30 s / 4.29 s | 40 ms / 35 ms | wait too short to measure (0 and 0 of 10 and 10 launches waited a second or more) | 742.9 MiB / 743.6 MiB | n = 10, 10 |
| eigenpal | 1.47 s / 1.43 s | not reproduced (first 145 ms; second 115 ms; launches 100 ms to 230 ms) | 49 ms/s / 43 ms/s | 609.5 MiB / 610.2 MiB | n = 10, 10 |
| Folio | 2.17 s / 2.25 s | 245 ms / 240 ms | 21 ms/s / 18 ms/s | 543.3 MiB / 541.5 MiB | n = 10, 10 |
| GenOffice | 1.27 s / 1.26 s | 165 ms / 185 ms | 5 ms/s / 6 ms/s | 551.4 MiB / 550.0 MiB | n = 10, 10 |
| Plate.js | 1.02 s / 1.00 s | 480 ms / 485 ms | 7 ms/s / 9 ms/s | 530.5 MiB / 530.9 MiB | n = 10, 10 |
| SuperDoc | 2.90 s / 2.89 s | 335 ms / 315 ms | 32 ms/s / 33 ms/s | 625.2 MiB / 625.4 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 928.7 MiB / 961.7 MiB | n = 10, 10 |

Not published or flagged:

- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal it used 6.51 s / 6.62 s of processor time; in the capped wait that followed, 75.17 s / 76.25 s. Of the capped wait, the browser's GPU process used 70.94 s / 73.50 s and the page's own process 4.17 s / 3.71 s (not reproduced); the page had 162 / 167 long tasks, 13.25 s / 13.48 s in all. Its memory readings ran from 887.4 MiB to 982.2 MiB across the kept launches.

### 5,000 words

| Editor | CPU to open | CPU of the edit | CPU per second while settling | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| canvas-editor + plugin | 1.25 s / 1.25 s | 7.29 s / 7.33 s | 25 ms/s / 23 ms/s | 926.3 MiB / 931.8 MiB | n = 10, 10 |
| Docen | 2.12 s / 2.08 s | 945 ms / 890 ms | 21 ms/s / 18 ms/s | 765.5 MiB / 757.2 MiB | n = 10, 10 |
| Docxodus | 6.16 s / 6.11 s | 30 ms / 30 ms | wait too short to measure (4 and 0 of 10 and 10 launches waited a second or more) | 781.7 MiB / 785.0 MiB | n = 10, 10 |
| eigenpal | 2.05 s / 2.00 s | 120 ms / 120 ms | 44 ms/s / 41 ms/s | 637.4 MiB / 636.5 MiB | n = 10, 10 |
| Folio | 2.46 s / 2.53 s | 360 ms / 355 ms | 20 ms/s / 18 ms/s | 571.9 MiB / 570.4 MiB | n = 10, 10 |
| GenOffice | 1.70 s / 1.67 s | 350 ms / 350 ms | 9 ms/s / 6 ms/s | 572.8 MiB / 572.3 MiB | n = 10, 10 |
| Plate.js | 1.89 s / 1.90 s | 595 ms / 610 ms | 5 ms/s / 9 ms/s | 559.2 MiB / 559.1 MiB | n = 10, 10 |
| SuperDoc | 3.85 s / 3.76 s | 780 ms / 800 ms | wait too short to measure (3 and 2 of 10 and 10 launches waited a second or more) | 725.5 MiB / 725.3 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 927.4 MiB / 963.2 MiB | n = 10, 10 |

Not published or flagged:

- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal it used 6.41 s / 6.43 s of processor time; in the capped wait that followed, 76.61 s / 76.52 s. Of the capped wait, the browser's GPU process used 72.45 s / 73.11 s and the page's own process 4.02 s / 3.85 s; the page had 167 / 166 long tasks, 13.32 s / 13.41 s in all. Its memory readings ran from 884.3 MiB to 968.5 MiB across the kept launches.

### 50,000 words

| Editor | CPU to open | CPU of the edit | CPU per second while settling | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| canvas-editor + plugin | 7.20 s / 6.92 s | 67.17 s / 65.00 s | 34 ms/s / 25 ms/s | not reproduced (first 3772.6 MiB; second 4528.6 MiB; launches 3427.5 MiB to 5137.1 MiB) | n = 10, 10 |
| Docen | 5.07 s / 4.87 s | 10.68 s / 10.24 s | not reproduced (first 79 ms/s; second 20 ms/s; launches 16 ms/s to 103 ms/s) | 1595.3 MiB / 1595.5 MiB | n = 10, 10 |
| Docxodus | 19.64 s / 19.00 s | 40 ms / 40 ms | wait too short to measure (0 and 0 of 10 and 10 launches waited a second or more) | 1060.3 MiB / 1061.7 MiB | n = 10, 10 |
| eigenpal | 3.98 s / 3.83 s | 180 ms / 160 ms | wait too short to measure (2 and 2 of 10 and 10 launches waited a second or more) | 691.9 MiB / 692.0 MiB | n = 10, 10 |
| Folio | 3.88 s / 3.69 s | 1.98 s / 1.82 s | 25 ms/s / 18 ms/s | 720.9 MiB / 716.2 MiB | n = 10, 10 |
| GenOffice | 4.70 s / 4.50 s | 3.37 s / 3.21 s | 9 ms/s / 11 ms/s | 833.7 MiB / 827.9 MiB | n = 10, 10 |
| Plate.js | 6.91 s / 6.66 s | 1.64 s / 1.56 s | wait too short to measure (8 and 2 of 10 and 10 launches waited a second or more) | 820.1 MiB / 821.3 MiB | n = 10, 10 |
| SuperDoc | 8.71 s / 8.20 s | 1.21 s / 1.18 s | 39 ms/s / 29 ms/s | 889.4 MiB / 888.0 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 931.3 MiB / 919.7 MiB | n = 10, 10 |

Not published or flagged:

- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal it used 6.24 s / 6.17 s of processor time; in the capped wait that followed, 75.34 s / 76.23 s. Of the capped wait, the browser's GPU process used 71.89 s / 73.33 s and the page's own process 4.33 s / 3.88 s (not reproduced); the page had 160 / 164 long tasks, 13.24 s / 13.37 s in all. Its memory readings ran from 904.7 MiB to 945.8 MiB across the kept launches.

### 250,000 words

| Editor | CPU to open | CPU of the edit | CPU per second while settling | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| canvas-editor + plugin | 53.88 s / 54.72 s | 503.49 s / 507.64 s | 32 ms/s / 29 ms/s | 9253.8 MiB / 9221.4 MiB | n = 10, 10 |
| Docen | 20.66 s / 21.16 s | 160.65 s / 167.09 s | not reproduced (first 638 ms/s; second 31 ms/s; launches 14 ms/s to 938 ms/s) | not reproduced (first 6956.0 MiB; second 5754.9 MiB; launches 5092.8 MiB to 8062.7 MiB) | n = 10, 10 |
| Docxodus | 106.25 s / 108.61 s | 60 ms / 50 ms | wait too short to measure (0 and 0 of 10 and 10 launches waited a second or more) | 2039.6 MiB / 2035.1 MiB | n = 10, 10 |
| eigenpal | 9.60 s / 9.76 s | 230 ms / 225 ms | wait too short to measure (4 and 0 of 10 and 10 launches waited a second or more) | 890.1 MiB / 889.1 MiB | n = 10, 10 |
| Folio | 7.63 s / 7.64 s | 9.02 s / 9.52 s | 29 ms/s / 30 ms/s | 1273.4 MiB / 1274.6 MiB | n = 10, 10 |
| GenOffice | 24.93 s / 24.80 s | 51.87 s / 54.55 s | not reproduced (first 395 ms/s; second 327 ms/s; launches 308 ms/s to 568 ms/s) | 1815.7 MiB / 1733.5 MiB | n = 10, 10 |
| Plate.js | 28.06 s / 28.32 s | 2.19 s / 2.31 s | 15 ms/s / 11 ms/s | 1838.7 MiB / 1811.7 MiB | n = 10, 7 |
| SuperDoc | 20.61 s / 20.68 s | not reproduced (first 1.34 s; second 1.67 s; launches 960 ms to 1.77 s) | not reproduced (first 38 ms/s; second 28 ms/s; launches 24 ms/s to 46 ms/s) | 1220.7 MiB / 1231.9 MiB | n = 10, 10 |
| WordCraft | never idle | never idle | never idle | 1073.5 MiB / 1008.8 MiB | n = 10, 10 |

Not published or flagged:

- WordCraft never went idle: it was still working when the 30-second cap ended, after opening in 10 and 10 of its kept launches and after the edit in 10 and 10. Its three CPU columns are not printed: they would time the cap, not the editor. Up to its ready signal its processor time did not reproduce between the seeds; in the capped wait that followed it used 66.44 s / 68.93 s. Of the capped wait, the browser's GPU process used 62.22 s / 64.61 s and the page's own process 4.67 s / 4.45 s; the page had 141 / 144 long tasks, 12.42 s / 12.38 s in all. Its memory readings ran from 984.7 MiB to 1114.7 MiB across the kept launches.

### Complex document

| Editor | CPU to open | CPU of the edit | CPU per second while settling | Highest memory reading | Kept launches |
|---|---|---|---|---|---|
| Docen | 1.83 s / 1.98 s | 690 ms / 745 ms | 20 ms/s / 23 ms/s | 703.1 MiB / 698.9 MiB | n = 10, 10 |
| Docxodus | 5.55 s / 5.72 s | 30 ms / 30 ms | wait too short to measure (8 and 0 of 10 and 10 launches waited a second or more) | 763.9 MiB / 766.6 MiB | n = 10, 10 |
| eigenpal | 1.88 s / 2.00 s | 105 ms / 120 ms | wait too short to measure (8 and 2 of 10 and 10 launches waited a second or more) | 629.8 MiB / 630.5 MiB | n = 10, 10 |
| Folio | 2.45 s / 2.64 s | not reproduced (first 460 ms; second 520 ms; launches 430 ms to 640 ms) | 20 ms/s / 26 ms/s | 556.6 MiB / 556.6 MiB | n = 10, 10 |
| GenOffice | 1.79 s / 1.86 s | not reproduced (first 330 ms; second 380 ms; launches 300 ms to 450 ms) | 10 ms/s / 6 ms/s | 596.2 MiB / 597.1 MiB | n = 10, 10 |
| Plate.js | 1.21 s / 1.29 s | not reproduced (first 420 ms; second 470 ms; launches 390 ms to 550 ms) | 5 ms/s / 8 ms/s | 525.9 MiB / 529.4 MiB | n = 10, 10 |
| SuperDoc | 3.54 s / 3.42 s | 460 ms / 480 ms | 32 ms/s / 33 ms/s | 662.6 MiB / 658.2 MiB | n = 10, 10 |
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

The settling window is not a fixed length: it ends at the first half-second poll at which two seconds have passed without a long task, so it is short when the page was already quiet and long when it was still working. What is timed is the span from the first to the last reading taken during that wait; in these runs it ran from 0.1 s to 5.6 s. The column therefore gives processor time per second of that span (ms/s; 10 ms/s is one percent of one processor), from the launches whose span was a second or more: a shorter one cannot be read with a counter that advances in steps of 10 ms. With fewer than 5 such launches in a seed, the cell says the wait was too short to measure, and gives no figure even when the other seed had enough. The two quiet seconds can begin before the first of these readings, so a span holds some of that quiet time, not always all of it. The figure is an average over the span, working and quiet time together: it is not the rate at which the editor works, and it still depends on how long the span ran. The polls themselves cost processor time, and that is in every figure. Earlier releases printed the total over the window. Across the 39 cells that had one, the first seed's median was the higher in 27 and the lower in 4. The totals are kept in the facts and are not printed.

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

## Appendix F — Not measured in the browser run

- **Apryse:** Apryse WebViewer needs a licence key, and the key is never placed on the measuring machines.
- **docs.plus:** docs.plus runs only as an application with its own application servers, which the browser run does not start.
- **Fidus Writer:** Fidus Writer runs only as an application with its own application server, which the browser run does not start.
- **LibreOffice (baseline):** LibreOffice is the conversion baseline of the headless report, not a browser editor.
- **office-open:** office-open is a library with no editing surface to paint, so no browser criterion applies.

BetterOffice, Nutrient, OnlyOffice (CryptPad build), OpenDoc and react-docx are not listed here: they are not part of the campaign this appendix describes. A campaign of their own measures them, and the section "The editors measured later" gives its tables and names any of them it has no data for.

## Appendix G — Cells whose two rounds did not agree

| Editor | Criterion | Workload | Measure | First seed / reason | Second seed, median |
|---|---|---|---|---|---|
| canvas-editor + plugin | C03 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| canvas-editor + plugin | C03 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| GenOffice | C03 | complex-corpus | warm_steady | 1082.5 ms | 883.5 ms |
| eigenpal | C03 | prose-5kw | process_cold_fs_warm | 1020.0 ms | 917.5 ms |
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
| canvas-editor + plugin | C05 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| GenOffice | C05 | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 4 of 10; reasons unverified: 6) | — |
| GenOffice | C05 | prose-250kw | warm_steady | second: not enough samples (n = 4 of 10; reasons unverified: 6) | — |
| WordCraft | C05 | prose-50kw | process_cold_fs_warm | 178.1 ms | 158.4 ms |
| canvas-editor + plugin | C06 | complex-corpus | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| canvas-editor + plugin | C06 | complex-corpus | warm_steady | first: not enough samples (n = 0 of 10; reasons not_run: 10); second: not enough samples (n = 0 of 10; reasons not_run: 10) | — |
| Folio | C06 | prose-250kw | process_cold_fs_warm | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C06 | prose-250kw | process_cold_fs_warm | second: not enough samples (n = 3 of 10; reasons unverified: 7) | — |
| Folio | C06 | prose-250kw | warm_steady | first: not enough samples (n = 0 of 10; reasons unverified: 10); second: not enough samples (n = 0 of 10; reasons unverified: 10) | — |
| GenOffice | C06 | prose-250kw | warm_steady | second: not enough samples (n = 3 of 10; reasons unverified: 7) | — |
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

## Appendix H — How to run it again

See perf/container/README.md.

## Appendix I — DOCX verification

The DOCX twin is a deliverable of the release gate: `build/verify_publication.sh --with-word` opens it in Microsoft Word and fails on any warning or offer to repair the file.

## Appendix J — Every results cell that is not a single figure, and why

The results at the top print a single figure only where two rounds of measurement agreed. This appendix has one line for every other cell of those tables that was part of these runs: 11 cells, of which 6 print a range, 0 "not measured", 4 "no figure", 1 "crashed", 0 "varied" (the measurements disagreed and their figures were not kept) and 0 "does not apply". A launch is one fresh start of the browser; a round has ten. A launch is kept when the harness confirmed the action and saw its result on screen, and refused otherwise; a round needs five kept launches. The reasons are the ones each launch recorded.

| Table | Editor | Document | Printed | Why |
|---|---|---|---|---|
| Opening a document | Docen | 500,000 words | 22.1 s to 26.4 s | The first round gave 22.1 s (10 launches) and the second 26.4 s (10 launches). They differ by more than the tolerance: the larger of 10 percent and one redraw of the screen (16.7 ms). |
| Typing one character | GenOffice | 250,000 words | no figure | The first round kept enough launches. Second round: 4 of 10 launches kept; 6 refused: a check of the result failed; also the typed character was not found in the editor afterwards. |
| Clicking to place the caret | WordCraft | 250,000 words | 170 ms to 194 ms | The first round gave 170 ms (10 launches) and the second 194 ms (10 launches). They differ by more than the tolerance: the larger of 10 percent and one redraw of the screen (16.7 ms). |
| Pasting a block of text | canvas-editor + plugin | 50,000 words | no figure | First round: 2 of 10 launches kept; 8 refused. Second round: 4 of 10 launches kept; 6 refused. The reason, both times: a check of the result failed; also the text the editor held did not match the document. |
| Pasting a block of text | canvas-editor + plugin | 250,000 words | no figure | First round: 2 of 10 launches kept; 8 refused: 1, the editor's page crashed; also no redraw of the screen was seen after the action in the time allowed; 7, no redraw of the screen was seen after the action in the time allowed. Second round: 2 of 10 launches kept; 8 refused: no redraw of the screen was seen after the action in the time allowed. |
| Pasting a block of text | Plate.js | 50,000 words | 129 ms to 152 ms | The first round gave 152 ms (10 launches) and the second 129 ms (10 launches). They differ by more than the tolerance: the larger of 10 percent and one redraw of the screen (16.7 ms). |
| Pasting a block of text | SuperDoc | 250,000 words | no figure | First round: 0 of 10 launches kept; 10 refused. Second round: 0 of 10 launches kept; 10 refused. The reason, both times: no redraw of the screen was seen after the action in the time allowed. |
| Undoing | canvas-editor + plugin | 50,000 words | 156 ms to 183 ms | The first round gave 183 ms (10 launches) and the second 156 ms (10 launches). They differ by more than the tolerance: the larger of 10 percent and one redraw of the screen (16.7 ms). |
| Scrolling | WordCraft | 500 words | 130 ms to 195 ms | The first round gave 130 ms (10 launches) and the second 195 ms (9 launches). They differ by more than the tolerance: the larger of 10 percent and one redraw of the screen (16.7 ms). |
| Scrolling | WordCraft | 50,000 words | under 17 ms to 131 ms | The first round gave 131 ms (10 launches) and the second under 17 ms (10 launches). They differ by more than the tolerance: the larger of 10 percent and one redraw of the screen (16.7 ms). |
| Memory with the document open | canvas-editor + plugin | 250,000 words | crashed | First round: 0 of 10 launches kept; 10 refused. Second round: 0 of 10 launches kept; 10 refused. The reason, both times: the editor's page crashed. |
