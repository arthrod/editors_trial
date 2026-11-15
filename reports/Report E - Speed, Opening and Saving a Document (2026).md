# Report E — Speed: Opening and Saving a Document (2026)

## TL;DR

This report times how long each editor takes to open a DOCX and to save it again, with no browser, as the document grows from 500 to 250,000 words. It was measured on one Linux container on a virtual machine (Amazon EC2 r6a.8xlarge): AMD EPYC 7R13 Processor, all 32 CPUs its kernel reports, 247 GiB RAM, Linux 6.12.113-138.209.amzn2023.x86_64, AC power, on 2026-11-09. Each figure is the median of 30 fresh processes. A second run of 10 processes, in another order, had to agree within 10 percent (or 2.0 ms) before a figure is printed. 211 of 211 figures agreed. A figure whose two runs disagree is printed as "not reproduced" and carries no number; its two medians are listed, as diagnostics only, at the end of the appendix.

It does not time what a person sees in a browser: the first paint, typing, scrolling. The runners for those have defects that would print wrong numbers. They are listed at the end, each with its issue.

Rows are in alphabetical order. A table here is not a ranking. A figure is one editor's time on one document, on this machine, in this mode. The editors do different amounts of work in the same call; the notes under each table say how.

- **canvas-editor + plugin.** Round trip 216 ms at 500 words, 1.3 s at 5,000 words, 13.4 s at 50,000 words. 250,000 words: stopped after repeated failures, last crashed (exit 1); complex.docx: stopped after repeated failures, last crashed (exit 1).
- **Docen.** Round trip 37 ms at 500 words, 69 ms at 5,000 words, 234 ms at 50,000 words, 743 ms at 250,000 words, 109 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 11 times.
- **docs.plus.** Round trip 115 ms at 500 words, 247 ms at 5,000 words, 1.1 s at 50,000 words, 4.1 s at 250,000 words, 160 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 16 times.
- **Docxodus.** Round trip 243 ms at 500 words, 310 ms at 5,000 words, 660 ms at 50,000 words, 2.0 s at 250,000 words, 347 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 6 times.
- **eigenpal.** Round trip 32 ms at 500 words, 61 ms at 5,000 words, 255 ms at 50,000 words, 980 ms at 250,000 words, 72 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 16 times.
- **Fidus Writer.** Round trip 220 ms at 500 words, 304 ms at 5,000 words, 869 ms at 50,000 words, 6.7 s at 250,000 words, 251 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 22 times.
- **Folio.** Round trip 52 ms at 500 words, 104 ms at 5,000 words, 399 ms at 50,000 words, 1.5 s at 250,000 words, 131 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 14 times.
- **GenOffice.** Round trip 197 ms at 500 words, 367 ms at 5,000 words, 1.5 s at 50,000 words, 7.6 s at 250,000 words, 411 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 21 times.
- **office-open.** Round trip 34 ms at 500 words, 60 ms at 5,000 words, 190 ms at 50,000 words, 630 ms at 250,000 words, 103 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 10 times.
- **Plate.js.** Round trip 662 ms at 500 words, 1.3 s at 5,000 words, 6.0 s at 50,000 words, 26.5 s at 250,000 words, 718 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 21 times.
- **SuperDoc.** Round trip 183 ms at 500 words, 324 ms at 5,000 words, 1.4 s at 50,000 words, 4.1 s at 250,000 words, 330 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 13 times.
- **WordCraft.** Round trip 1.7 ms at 500 words, 5.6 ms at 5,000 words, 51 ms at 50,000 words, 271 ms at 250,000 words, 4.6 ms at complex.docx. From 5,000 to 250,000 words (50 times the text) it grew 48 times.

## What was timed

Each sample is one fresh process that runs the editor's own import and export, through the same entry point the fidelity trial uses in Reports A to D. Under `PERF_ONLY=1` the entry points print nothing else and write no evidence files inside the timers.

- **Load (C02).** From the start of the editor's import call until its document model is ready. Layer: model. Clock: layer model, boundary model_ready, cache state process_cold_fs_warm (fresh process, file system cache warm).
- **Save (C16).** Right after load, in the same process, from the start of the editor's export call until the DOCX bytes exist. No edit is made first. Layer: model. Clock: layer model, boundary serialization_complete, cache state warm_steady (same process, right after load).
- **Round trip.** Load plus save of the same sample. Each editor draws the line between its load and its save in a different place (see the table below), so the round trip is the fairer comparison of the two.
- **Process.** The whole process, from spawn to exit: wall time, CPU time, and peak resident memory. This includes starting the runtime (Node, Bun, Vitest, or a native binary). It is what a command-line conversion costs, not what an editor costs once it is open.

What each editor's timers cover:

| Editor | Load timer ends at | Save timer covers |
|---|---|---|
| canvas-editor + plugin | executeImportDocx | executeExportDocx (jsdom; canvas and workers mocked) |
| Docen | parseDOCX | generateDOCX |
| docs.plus | importDocx (mammoth) | exportDocx |
| Docxodus | openDocxSession | session.save (WASM initialised before the timer) |
| eigenpal | readOoxmlPackage | writeOoxmlPackage (store lane) |
| Fidus Writer | JSZip.loadAsync + DocxConvert.init | image table + CSL style + generateDocxTemplate + DOCXExporter.init |
| Folio | parseDocx(preloadFonts false) | repackDocx |
| GenOffice | parseDocx + Tiptap setContent | getJSON + pmDocToSavePlan + saveDocx |
| LibreOffice (baseline) | soffice --convert-to docx: whole conversion, no load/save split | — |
| office-open | parseDocument | generateDocument |
| Plate.js | importDocx(lossPolicy allow, 45 plugins) + createEditor | exportDocx |
| SuperDoc | client.open(path) after client.connect() | doc.save(path); both timers include the SDK host reading or writing the file, which the other lanes do outside their timers |
| WordCraft | wordcraft_docx::read | wordcraft_docx::write (native release build) |

Each repetition runs every editor once, in an order shuffled from a recorded seed, so a slow minute on the machine lands on all editors and not on one. One discarded warm-up per editor and document comes first. Every sample is kept on disk with its command, its environment, its exit status, its output hash and its check.

## Documents

| Workload | Words | Paragraphs | File size | Shape |
|---|---|---|---|---|
| 500 words | 500 | 16 | 4 KB | prose |
| 5,000 words | 5,000 | 115 | 17 KB | prose |
| 50,000 words | 50,000 | 1,105 | 144 KB | prose |
| 250,000 words | 250,000 | 5,505 | 709 KB | prose |
| complex.docx | 178 | 56 | 25 KB | corpus |

The prose documents are generated text: 50 words per paragraph, a Heading 1 every 50 paragraphs and a Heading 2 every 10, bold and italic runs, Letter pages. Four paragraphs carry accented, right-to-left, CJK and emoji text. The last paragraph is a sentinel. `complex.docx` is the trial's corpus document from Reports A to D.

Every saved file was checked, with the same text extractor that read the input. It had to open as a DOCX, keep at least 98 percent of the input's words, counted word by word, be at most 2 percent longer, and end with the sentinel (`complex.docx`, which is mostly tables, images and fields: keep 50 percent, at most 1.5 times as long, no sentinel). A sample also had to exit cleanly and print each of its timer marks exactly once. A sample that failed any of this is not a time. It is counted as a failure, and its full output is kept.

## Round trip

Median in ms, with the 90th percentile.

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words | complex.docx |
|---|---|---|---|---|---|
| canvas-editor + plugin | 216 (p90 233) | 1,338 (p90 1,395) | 13,392 (p90 13,933) | failed: stopped after repeated failures, last crashed (exit 1) | failed: stopped after repeated failures, last crashed (exit 1) |
| Docen | 37 (p90 38) | 69 (p90 73) | 234 (p90 250) | 743 (p90 789) | 109 (p90 111) |
| docs.plus | 115 (p90 126) | 247 (p90 258) | 1,086 (p90 1,129) | 4,055 (p90 4,312) | 160 (p90 172) |
| Docxodus | 243 (p90 249) | 310 (p90 322) | 660 (p90 699) | 2,002 (p90 2,041) | 347 (p90 375) |
| eigenpal | 32 (p90 32) | 61 (p90 64) | 255 (p90 265) | 980 (p90 1,008) | 72 (p90 77) |
| Fidus Writer | 220 (p90 231) | 304 (p90 321) | 869 (p90 937) | 6,683 (p90 6,820) | 251 (p90 262) |
| Folio | 52 (p90 55) | 104 (p90 108) | 399 (p90 419) | 1,479 (p90 1,517) | 131 (p90 152) |
| GenOffice | 197 (p90 206) | 367 (p90 387) | 1,542 (p90 1,608) | 7,575 (p90 7,728) | 411 (p90 426) |
| office-open | 34 (p90 36) | 60 (p90 63) | 190 (p90 202) | 630 (p90 691) | 103 (p90 105) |
| Plate.js | 662 (p90 704) | 1,288 (p90 1,436) | 6,027 (p90 6,194) | 26,506 (p90 27,827) | 718 (p90 767) |
| SuperDoc | 183 (p90 190) | 324 (p90 330) | 1,379 (p90 1,411) | 4,060 (p90 4,169) | 330 (p90 340) |
| WordCraft | 1.7 (p90 1.7) | 5.6 (p90 5.7) | 51 (p90 52) | 271 (p90 273) | 4.6 (p90 4.6) |

## Load

Median in ms, with the 90th percentile. Clock: layer model, boundary model_ready, cache state process_cold_fs_warm (fresh process, file system cache warm).

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words | complex.docx |
|---|---|---|---|---|---|
| canvas-editor + plugin | 166 (p90 180) | 1,126 (p90 1,178) | 11,720 (p90 12,191) | failed: stopped after repeated failures, last crashed (exit 1) | failed: stopped after repeated failures, last crashed (exit 1) |
| Docen | 18 (p90 19) | 38 (p90 41) | 155 (p90 166) | 476 (p90 494) | 63 (p90 64) |
| docs.plus | 53 (p90 62) | 98 (p90 100) | 323 (p90 340) | 1,097 (p90 1,125) | 72 (p90 79) |
| Docxodus | 210 (p90 216) | 265 (p90 274) | 537 (p90 571) | 1,541 (p90 1,581) | 299 (p90 325) |
| eigenpal | 13 (p90 14) | 29 (p90 31) | 131 (p90 137) | 522 (p90 535) | 30 (p90 32) |
| Fidus Writer | 27 (p90 30) | 66 (p90 71) | 278 (p90 297) | 1,200 (p90 1,276) | 43 (p90 47) |
| Folio | 31 (p90 32) | 60 (p90 62) | 220 (p90 231) | 751 (p90 781) | 74 (p90 83) |
| GenOffice | 190 (p90 199) | 352 (p90 372) | 1,462 (p90 1,515) | 7,189 (p90 7,340) | 348 (p90 359) |
| office-open | 15 (p90 15) | 31 (p90 32) | 121 (p90 130) | 411 (p90 433) | 55 (p90 56) |
| Plate.js | 339 (p90 373) | 601 (p90 653) | 2,462 (p90 2,586) | 9,989 (p90 10,253) | 439 (p90 483) |
| SuperDoc | 175 (p90 182) | 312 (p90 320) | 1,369 (p90 1,403) | 4,047 (p90 4,156) | 322 (p90 332) |
| WordCraft | 0.8 (p90 0.8) | 3.3 (p90 3.4) | 31 (p90 32) | 157 (p90 158) | 2.4 (p90 2.5) |

## Save

Median in ms, with the 90th percentile. Clock: layer model, boundary serialization_complete, cache state warm_steady (same process, right after load).

| Editor | 500 words | 5,000 words | 50,000 words | 250,000 words | complex.docx |
|---|---|---|---|---|---|
| canvas-editor + plugin | 49 (p90 59) | 210 (p90 220) | 1,682 (p90 1,759) | failed: stopped after repeated failures, last crashed (exit 1) | failed: stopped after repeated failures, last crashed (exit 1) |
| Docen | 19 (p90 19) | 31 (p90 32) | 78 (p90 86) | 264 (p90 294) | 46 (p90 47) |
| docs.plus | 61 (p90 67) | 151 (p90 156) | 763 (p90 795) | 2,958 (p90 3,214) | 87 (p90 94) |
| Docxodus | 32 (p90 33) | 45 (p90 47) | 122 (p90 125) | 459 (p90 466) | 48 (p90 50) |
| eigenpal | 18 (p90 19) | 32 (p90 33) | 123 (p90 128) | 459 (p90 473) | 42 (p90 44) |
| Fidus Writer | 193 (p90 201) | 238 (p90 251) | 583 (p90 658) | 5,454 (p90 5,577) | 207 (p90 215) |
| Folio | 22 (p90 23) | 44 (p90 46) | 179 (p90 186) | 722 (p90 748) | 57 (p90 69) |
| GenOffice | 6.6 (p90 6.9) | 15 (p90 16) | 81 (p90 90) | 384 (p90 414) | 63 (p90 67) |
| office-open | 20 (p90 20) | 29 (p90 30) | 68 (p90 71) | 219 (p90 259) | 48 (p90 49) |
| Plate.js | 316 (p90 342) | 695 (p90 749) | 3,542 (p90 3,719) | 16,476 (p90 17,745) | 278 (p90 297) |
| SuperDoc | 7.8 (p90 9.4) | 9.8 (p90 13) | 8.8 (p90 9.7) | 13 (p90 14) | 8.2 (p90 8.9) |
| WordCraft | 0.9 (p90 0.9) | 2.3 (p90 2.4) | 20 (p90 21) | 114 (p90 115) | 2.1 (p90 2.2) |

What the save figures include, found in the samples:

- **The file is the input.** In both runs, on every sample of the documents named, this editor wrote back the exact bytes it was given: GenOffice on the 500 words, 5,000 words, 50,000 words and 250,000 words documents (it rewrote complex.docx). With nothing edited, it keeps the original package there; its save time on those documents is the time to decide that and hand the bytes back.
- **The save barely grows with the document.** SuperDoc's save took 9.8 ms at 5,000 words and 13 ms at 250,000 words, while its load grew 13 times. Its saved file is not the input: the editor wrote a new file. Where the editor does that work was not traced; the round trip counts load and save together.
- **A host process.** SuperDoc's native host starts before the load timer, in 555 ms (median at 500 words); that start is in the process figures, not in load.

## Process cost at 50,000 words

Medians. Wall and CPU time in ms; peak resident memory in MiB. CPU time can exceed wall time when an editor uses more than one thread. Peak memory is the largest single process of the editor's process tree, not the sum. CPU time and memory are printed only where no process of the editor outlived its sample, since a process left running is not counted. A process that leaves the editor's process group altogether cannot be seen by this check.

| Editor | Whole process, wall (ms) | CPU time (ms) | Peak resident memory (MiB) |
|---|---|---|---|
| canvas-editor + plugin | 16,172 (includes a 500 ms wait in the harness between load and save) | 19,940 | 1,621 |
| Docen | 590 | 977 | 181 |
| docs.plus | 1,452 | 3,453 | 338 |
| Docxodus | 904 | 1,549 | 241 |
| eigenpal | 370 | 968 | 133 |
| Fidus Writer | 1,621 | incomplete (30 of 30 samples left a process running) | incomplete (30 of 30 samples left a process running) |
| Folio | 526 | 1,065 | 161 |
| GenOffice | 2,870 | 3,919 | 319 |
| LibreOffice (baseline) | 1,121 | 1,100 | 235 |
| office-open | 669 | 959 | 176 |
| Plate.js | 6,885 | 12,826 | 1,207 |
| SuperDoc | 2,182 | 3,441 | 403 |
| WordCraft | 55 | 54 | 66 |

## LibreOffice

LibreOffice is a baseline, not an editor in this trial. `soffice --convert-to docx` has no separate load and save, so only its whole conversion is timed, with a fresh profile per sample.

| Workload | Whole conversion, wall (ms) | Second run |
|---|---|---|
| 500 words | 405 | agrees (407) |
| 5,000 words | 481 | agrees (477) |
| 50,000 words | 1,121 | agrees (1,123) |
| 250,000 words | 4,610 | agrees (4,594) |
| complex.docx | 605 | agrees (607) |

## Exceptions

Every figure that is not printed, and why.

- canvas-editor + plugin, 250,000 words, load: failed, stopped after repeated failures, last crashed (exit 1); last error: `Error: Worker exited unexpectedly`.
- canvas-editor + plugin, 250,000 words, save: failed, stopped after repeated failures, last crashed (exit 1); last error: `Error: Worker exited unexpectedly`.
- canvas-editor + plugin, 250,000 words, round trip: failed, stopped after repeated failures, last crashed (exit 1); last error: `Error: Worker exited unexpectedly`.
- canvas-editor + plugin, complex.docx, load: failed, stopped after repeated failures, last crashed (exit 1); last error: `TypeError: Cannot read properties of undefined (reading 'width') at canvas-editor/src/editor/core/draw/particle/table/TableParticle.ts:724`.
- canvas-editor + plugin, complex.docx, save: failed, stopped after repeated failures, last crashed (exit 1); last error: `TypeError: Cannot read properties of undefined (reading 'width') at canvas-editor/src/editor/core/draw/particle/table/TableParticle.ts:724`.
- canvas-editor + plugin, complex.docx, round trip: failed, stopped after repeated failures, last crashed (exit 1); last error: `TypeError: Cannot read properties of undefined (reading 'width') at canvas-editor/src/editor/core/draw/particle/table/TableParticle.ts:724`.

What the canvas-editor failures are, from their logs and from one diagnostic rerun outside the two runs (a diagnosis, not a measurement; it printed no figure in this report):

- **250,000 words.** Every one of these samples printed its load time and then died during the save; a sample that fails is not a time, so its load is counted as failed too. In the runs, the editor ran in a Vitest worker thread, so the death showed only as "Worker exited unexpectedly". Rerun once in a separate process instead (Vitest's forks pool) with Node's default heap, the same sample stopped during the save with V8's "JavaScript heap out of memory", its heap full at the default limit. Rerun once in a worker thread, as in the runs, with a larger heap, it loaded and saved, and the saved file passed the same check as every sample in this report. The editor needs more JavaScript heap than Node gives by default to save a document of this size; no lane in this report raises the default for any editor.
- **complex.docx.** The editor's import crashes on a table with vertically merged cells (`w:vMerge`), the crash described in the main report: the importer drops the merged continuation cells, and the layout engine then reads past the end of the table's column list.

Text the check found missing from the saved files (the round trip still kept 98 percent of the words, so the samples count): Fidus Writer: emoji, unicode.

## Not measured in this report

- **Browser criteria.** First usable (C03), single edit and typing (C05, C06), caret (C07), paste (C08), undo (C09), scroll (C10), first page (C11), relayout (C12), scaling in the page (C14), save from the page (C15). An audit of their runners found that they would print wrong numbers: a settle sleep inside the C03 timer ([#104](https://github.com/arthrod/editors_trial/issues/104)), driver wall-clock labelled as paint ([#105](https://github.com/arthrod/editors_trial/issues/105)), a scroll time with no scroll ([#106](https://github.com/arthrod/editors_trial/issues/106)), development servers instead of builds ([#107](https://github.com/arthrod/editors_trial/issues/107)), the shell's first paint as the document's ([#108](https://github.com/arthrod/editors_trial/issues/108)), a frame-witness bug ([#109](https://github.com/arthrod/editors_trial/issues/109)), pooled runs ([#110](https://github.com/arthrod/editors_trial/issues/110)), and input latencies kept without proving the edit ([#113](https://github.com/arthrod/editors_trial/issues/113), [#114](https://github.com/arthrod/editors_trial/issues/114)).
- **Memory over time (C17, C19).** The memory runners sum the wrong processes and stop too early ([#115](https://github.com/arthrod/editors_trial/issues/115)). The peak memory above comes from the headless runner instead.
- **WebAssembly boundary (C24).** Two editors only, and the per-call figures are below the clock ([#117](https://github.com/arthrod/editors_trial/issues/117)).
- **Apryse WebViewer.** It has no headless entry point; it runs only in a browser.
- **Save after an edit.** Every save here follows an unedited load.
- **A cold file system cache.** Every load reads files the warm-up already brought into memory.

## How it was measured

- **Host.** Measured on one Linux container on a virtual machine (Amazon EC2 r6a.8xlarge): AMD EPYC 7R13 Processor, all 32 CPUs its kernel reports, 247 GiB RAM, Linux 6.12.113-138.209.amzn2023.x86_64, AC power. The run refuses to start unless the 1-minute load average is under a third of the CPUs, no other process uses more than a quarter of a core, no trial script is driving Word and no bench batch runs, and the recorded power source is AC. Each sample records its own load and power. The container may use all 32 CPUs its kernel reports. The load average counts every process on that kernel, in this container or any other, and was judged against all 32 CPUs; the process check cannot see processes outside the container. The guest's steal counter (CPU time its hypervisor gave to other work while this machine was ready to run) was less than 0.01% during the run and less than 0.01% during the second run; it counts CPU time only, not the guest's own waits for memory or I/O. The container sees no power supply; AC power is inferred from the machine's vendor (Amazon EC2). 
- **Code.** Every checkout must be on its pin with no changed tracked file, and every installed package must be the declared version. Exceptions the run accepted, with its reasons: office-open: 27 deletions under scripts/coverage/: 27 coverage scripts deleted on 2026-11-02 (not by this trial's code); only the pnpm coverage:* scripts use them, not the lane's import path. WordCraft's binary is rebuilt from its pinned source before the run.
- **Runs.** Primary run `2471956e80e7`: 30 repetitions, seed 20261109. Reproduction run `62769027c2c2`: 10 repetitions, seed 20261110.
- **Publication.** A figure is printed only if the primary run kept every sample of the cell (at least 10, none excluded, at most 10 percent started above the load limit, all on AC power) and the reproduction run's median agrees. The reproduction must be another run, with another seed, of the same documents, versions, timer boundaries and code; the tables builder refuses anything else, and it refuses a summary whose figures its sample files do not give.
- **Runner.** `perf/runner/speed_headless.py`. Tables: `build/perf_e_tables.py`.

Versions, read from disk at the start of the primary run:

| Editor | Pin | Checkouts on disk | Packages and binaries |
|---|---|---|---|
| canvas-editor + plugin | 1865c9b06; 0e8a1b36c | canvas-editor 1865c9b06, canvas-editor-plugin 0e8a1b36c | — |
| Docen | 1890b15aa | docen 1890b15aa | — |
| docs.plus | a9b0c69e8 | docsplus/repo-copy a9b0c69e8, docs-plus a9b0c69e8 | — |
| Docxodus | 583a11c7f | docxodus 583a11c7f | docxodus 15.0.0 |
| eigenpal | 3425d4d7a | eigenpal-docx-editor 3425d4d7a | — |
| Fidus Writer | e14cc456a; dc0981db4 | fiduswriter e14cc456a, fiduswriter-document-ts dc0981db4 | — |
| Folio | 958c582cb | folio 958c582cb | — |
| GenOffice | 36a509e8f | genoffice 36a509e8f | — |
| LibreOffice (baseline) | system soffice | — | LibreOffice 26.8.2.2 9dea406ab7695df6325b11b0e19fdca8db4b7276 |
| office-open | 567addfd4 | office-open 567addfd4 | — |
| Plate.js | 60c7f5530 | plate 60c7f5530 | — |
| SuperDoc | 0ee03fd3c; 0.28.0-next.3 | superdoc 0ee03fd3c | @superdoc/sdk 2.26.0-next.16 |
| WordCraft | a88e00525 | wordcraft a88e00525 | wc-harness sha256 a7dc1ee4d264 |

Runtimes: bun 1.4.4, node v26.13.0, python 3.12.3.

## Appendix: full distributions

Round trip in ms, primary run. At this sample count the 99th percentile is close to the maximum.

**500 words, round trip (ms)**

| Editor | n | median | p90 | p95 | p99 | MAD | 95% CI | min | max |
|---|---|---|---|---|---|---|---|---|---|
| canvas-editor + plugin | 30 | 216 | 233 | 236 | 248 | 6.2 | 214 to 220 | 200 | 252 |
| Docen | 30 | 37 | 38 | 39 | 40 | 0.4 | 37 to 38 | 35 | 40 |
| docs.plus | 30 | 115 | 126 | 137 | 144 | 1.9 | 114 to 117 | 111 | 146 |
| Docxodus | 30 | 243 | 249 | 255 | 270 | 2.4 | 241 to 244 | 234 | 275 |
| eigenpal | 30 | 32 | 32 | 33 | 33 | 0.4 | 31 to 32 | 30 | 33 |
| Fidus Writer | 30 | 220 | 231 | 237 | 239 | 4.2 | 216 to 223 | 205 | 239 |
| Folio | 30 | 52 | 55 | 55 | 56 | 0.7 | 52 to 53 | 51 | 56 |
| GenOffice | 30 | 197 | 206 | 211 | 218 | 5.1 | 192 to 199 | 182 | 220 |
| office-open | 30 | 34 | 36 | 37 | 37 | 0.3 | 34 to 35 | 34 | 37 |
| Plate.js | 30 | 662 | 704 | 714 | 731 | 20 | 654 to 674 | 631 | 737 |
| SuperDoc | 30 | 183 | 190 | 192 | 195 | 4.3 | 180 to 185 | 170 | 196 |
| WordCraft | 30 | 1.7 | 1.7 | 1.7 | 1.8 | 0.0 | 1.7 to 1.7 | 1.6 | 1.8 |

**5,000 words, round trip (ms)**

| Editor | n | median | p90 | p95 | p99 | MAD | 95% CI | min | max |
|---|---|---|---|---|---|---|---|---|---|
| canvas-editor + plugin | 30 | 1,338 | 1,395 | 1,423 | 1,458 | 31 | 1,328 to 1,362 | 1,274 | 1,466 |
| Docen | 30 | 69 | 73 | 74 | 74 | 2.2 | 67 to 71 | 65 | 74 |
| docs.plus | 30 | 247 | 258 | 260 | 266 | 4.6 | 246 to 251 | 240 | 268 |
| Docxodus | 30 | 310 | 322 | 325 | 333 | 2.7 | 309 to 312 | 304 | 335 |
| eigenpal | 30 | 61 | 64 | 65 | 66 | 1.2 | 60 to 62 | 59 | 66 |
| Fidus Writer | 30 | 304 | 321 | 323 | 335 | 6.5 | 301 to 308 | 290 | 339 |
| Folio | 30 | 104 | 108 | 109 | 109 | 2.5 | 102 to 105 | 99 | 109 |
| GenOffice | 30 | 367 | 387 | 394 | 400 | 11 | 358 to 370 | 345 | 400 |
| office-open | 30 | 60 | 63 | 64 | 66 | 1.0 | 59 to 61 | 58 | 67 |
| Plate.js | 30 | 1,288 | 1,436 | 1,451 | 1,461 | 27 | 1,277 to 1,343 | 1,215 | 1,463 |
| SuperDoc | 30 | 324 | 330 | 333 | 356 | 5.0 | 319 to 326 | 312 | 364 |
| WordCraft | 30 | 5.6 | 5.7 | 5.8 | 5.8 | 0.1 | 5.5 to 5.6 | 5.4 | 5.8 |

**50,000 words, round trip (ms)**

| Editor | n | median | p90 | p95 | p99 | MAD | 95% CI | min | max |
|---|---|---|---|---|---|---|---|---|---|
| canvas-editor + plugin | 30 | 13,392 | 13,933 | 13,976 | 14,008 | 322 | 13,249 to 13,593 | 12,755 | 14,016 |
| Docen | 30 | 234 | 250 | 250 | 252 | 6.8 | 229 to 243 | 226 | 253 |
| docs.plus | 30 | 1,086 | 1,129 | 1,139 | 1,145 | 20 | 1,070 to 1,098 | 1,013 | 1,146 |
| Docxodus | 30 | 660 | 699 | 703 | 707 | 3.9 | 658 to 663 | 652 | 708 |
| eigenpal | 30 | 255 | 265 | 267 | 279 | 3.7 | 252 to 258 | 247 | 284 |
| Fidus Writer | 30 | 869 | 937 | 939 | 957 | 31 | 850 to 894 | 823 | 964 |
| Folio | 30 | 399 | 419 | 421 | 433 | 4.9 | 396 to 403 | 387 | 438 |
| GenOffice | 30 | 1,542 | 1,608 | 1,629 | 1,693 | 28 | 1,516 to 1,559 | 1,489 | 1,714 |
| office-open | 30 | 190 | 202 | 215 | 223 | 4.1 | 187 to 193 | 179 | 225 |
| Plate.js | 30 | 6,027 | 6,194 | 6,235 | 6,339 | 113 | 5,992 to 6,130 | 5,810 | 6,375 |
| SuperDoc | 30 | 1,379 | 1,411 | 1,422 | 1,431 | 13 | 1,367 to 1,384 | 1,326 | 1,432 |
| WordCraft | 30 | 51 | 52 | 53 | 54 | 1.0 | 50 to 52 | 48 | 54 |

**250,000 words, round trip (ms)**

| Editor | n | median | p90 | p95 | p99 | MAD | 95% CI | min | max |
|---|---|---|---|---|---|---|---|---|---|
| canvas-editor + plugin | stopped after repeated failures, last crashed (exit 1) | | | | | | | | |
| Docen | 30 | 743 | 789 | 803 | 828 | 34 | 712 to 764 | 679 | 836 |
| docs.plus | 30 | 4,055 | 4,312 | 4,353 | 4,367 | 94 | 4,004 to 4,131 | 3,903 | 4,371 |
| Docxodus | 30 | 2,002 | 2,041 | 2,063 | 2,080 | 17 | 1,991 to 2,015 | 1,967 | 2,083 |
| eigenpal | 30 | 980 | 1,008 | 1,010 | 1,011 | 13 | 969 to 986 | 926 | 1,011 |
| Fidus Writer | 30 | 6,683 | 6,820 | 6,893 | 6,976 | 92 | 6,606 to 6,739 | 6,500 | 6,992 |
| Folio | 30 | 1,479 | 1,517 | 1,519 | 1,536 | 24 | 1,467 to 1,502 | 1,433 | 1,542 |
| GenOffice | 30 | 7,575 | 7,728 | 7,743 | 7,973 | 67 | 7,554 to 7,618 | 7,408 | 8,064 |
| office-open | 30 | 630 | 691 | 701 | 728 | 18 | 619 to 663 | 608 | 736 |
| Plate.js | 30 | 26,506 | 27,827 | 28,105 | 29,458 | 463 | 26,313 to 26,852 | 25,771 | 29,947 |
| SuperDoc | 30 | 4,060 | 4,169 | 4,229 | 4,392 | 66 | 4,009 to 4,100 | 3,867 | 4,444 |
| WordCraft | 30 | 271 | 273 | 274 | 275 | 1.6 | 270 to 272 | 266 | 276 |

**complex.docx, round trip (ms)**

| Editor | n | median | p90 | p95 | p99 | MAD | 95% CI | min | max |
|---|---|---|---|---|---|---|---|---|---|
| canvas-editor + plugin | stopped after repeated failures, last crashed (exit 1) | | | | | | | | |
| Docen | 30 | 109 | 111 | 112 | 113 | 1.0 | 109 to 110 | 106 | 114 |
| docs.plus | 30 | 160 | 172 | 173 | 180 | 2.9 | 158 to 162 | 153 | 183 |
| Docxodus | 30 | 347 | 375 | 378 | 382 | 3.4 | 345 to 351 | 340 | 383 |
| eigenpal | 30 | 72 | 77 | 82 | 85 | 1.2 | 71 to 73 | 70 | 86 |
| Fidus Writer | 30 | 251 | 262 | 267 | 275 | 4.4 | 248 to 255 | 242 | 277 |
| Folio | 30 | 131 | 152 | 153 | 154 | 2.0 | 130 to 134 | 128 | 154 |
| GenOffice | 30 | 411 | 426 | 429 | 435 | 4.8 | 409 to 418 | 404 | 438 |
| office-open | 30 | 103 | 105 | 105 | 107 | 0.9 | 102 to 104 | 101 | 108 |
| Plate.js | 30 | 718 | 767 | 781 | 810 | 13 | 713 to 733 | 703 | 819 |
| SuperDoc | 30 | 330 | 340 | 342 | 344 | 6.9 | 325 to 334 | 315 | 344 |
| WordCraft | 30 | 4.6 | 4.6 | 4.6 | 4.7 | 0.0 | 4.5 to 4.6 | 4.5 | 4.7 |

## Appendix: figures that did not reproduce (diagnostics, not results)

A median that disagreed between the two runs by more than the tolerance is listed here with both values. These are not results; they show how far apart the runs were.

Every figure that was measured in both runs reproduced.
