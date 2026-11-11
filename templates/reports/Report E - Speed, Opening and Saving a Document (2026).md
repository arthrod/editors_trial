# Report E — Speed: Opening and Saving a Document (2026)

## TL;DR

This report times how long each editor takes to open a DOCX and to save it again, with no browser, as the document grows from 500 to 250,000 words. It was measured on {{perf.e.machine}}: {{perf.e.host}}, on {{perf.e.date}}. Each figure is the median of {{perf.e.n}} fresh processes. A second run of {{perf.e.repro_n}} processes, in another order, had to agree within {{perf.e.rel_tol_pct}} percent (or {{perf.e.abs_tol_ms}} ms) before a figure is printed. {{perf.e.cells_reproduced}} of {{perf.e.cells_checked}} figures agreed. A figure whose two runs disagree is printed as "not reproduced" and carries no number; its two medians are listed, as diagnostics only, at the end of the appendix.

It does not time what a person sees in a browser: the first paint, typing, scrolling. The runners for those have defects that would print wrong numbers. They are listed at the end, each with its issue.

Rows are in alphabetical order. A table here is not a ranking. A figure is one editor's time on one document, on this machine, in this mode. The editors do different amounts of work in the same call; the notes under each table say how.

{{perf.e.summary}}

## What was timed

Each sample is one fresh process that runs the editor's own import and export, through the same entry point the fidelity trial uses in Reports A to D. Under `PERF_ONLY=1` the entry points print nothing else and write no evidence files inside the timers.

- **Load (C02).** From the start of the editor's import call until its document model is ready. Layer: model. Clock: {{perf.e.context.load}}.
- **Save (C16).** Right after load, in the same process, from the start of the editor's export call until the DOCX bytes exist. No edit is made first. Layer: model. Clock: {{perf.e.context.save}}.
- **Round trip.** Load plus save of the same sample. Each editor draws the line between its load and its save in a different place (see the table below), so the round trip is the fairer comparison of the two.
- **Process.** The whole process, from spawn to exit: wall time, CPU time, and peak resident memory. This includes starting the runtime (Node, Bun, Vitest, or a native binary). It is what a command-line conversion costs, not what an editor costs once it is open.

What each editor's timers cover:

{{perf.e.lanes}}

Each repetition runs every editor once, in an order shuffled from a recorded seed, so a slow minute on the machine lands on all editors and not on one. One discarded warm-up per editor and document comes first. Every sample is kept on disk with its command, its environment, its exit status, its output hash and its check.

## Documents

{{perf.e.workloads}}

The prose documents are generated text: 50 words per paragraph, a Heading 1 every 50 paragraphs and a Heading 2 every 10, bold and italic runs, Letter pages. Four paragraphs carry accented, right-to-left, CJK and emoji text. The last paragraph is a sentinel. `complex.docx` is the trial's corpus document from Reports A to D.

Every saved file was checked, with the same text extractor that read the input. It had to open as a DOCX, {{perf.e.check}}. A sample also had to exit cleanly and print each of its timer marks exactly once. A sample that failed any of this is not a time. It is counted as a failure, and its full output is kept.

## Round trip

Median in ms, with the 90th percentile.

{{perf.e.table.roundtrip}}

## Load

Median in ms, with the 90th percentile. Clock: {{perf.e.context.load}}.

{{perf.e.table.load}}

## Save

Median in ms, with the 90th percentile. Clock: {{perf.e.context.save}}.

{{perf.e.table.save}}

What the save figures include, found in the samples:

{{perf.e.save_notes}}

## Process cost at {{perf.e.process_workload}}

Medians. Wall and CPU time in ms; peak resident memory in MiB. CPU time can exceed wall time when an editor uses more than one thread. Peak memory is the largest single process of the editor's process tree, not the sum. CPU time and memory are printed only where no process of the editor outlived its sample, since a process left running is not counted. A process that leaves the editor's process group altogether cannot be seen by this check.

{{perf.e.table.process}}

## LibreOffice

LibreOffice is a baseline, not an editor in this trial. `soffice --convert-to docx` has no separate load and save, so only its whole conversion is timed, with a fresh profile per sample.

{{perf.e.table.libreoffice}}

## Exceptions

Every figure that is not printed, and why.

{{perf.e.exceptions}}

What the canvas-editor failures are, from their logs and from one diagnostic rerun outside the two runs (a diagnosis, not a measurement; it printed no figure in this report):

- **250,000 words.** Every one of these samples printed its load time and then died during the save; a sample that fails is not a time, so its load is counted as failed too. In the runs, the editor ran in a Vitest worker thread, so the death showed only as "Worker exited unexpectedly". Rerun once in a separate process instead (Vitest's forks pool) with Node's default heap, the same sample stopped during the save with V8's "JavaScript heap out of memory", its heap full at the default limit. Rerun once in a worker thread, as in the runs, with a larger heap, it loaded and saved, and the saved file passed the same check as every sample in this report. The editor needs more JavaScript heap than Node gives by default to save a document of this size; no lane in this report raises the default for any editor.
- **complex.docx.** The editor's import crashes on a table with vertically merged cells (`w:vMerge`), the crash described in the main report: the importer drops the merged continuation cells, and the layout engine then reads past the end of the table's column list.

Text the check found missing from the saved files (the round trip still kept 98 percent of the words, so the samples count): {{perf.e.correctness_lost}}.

## Not measured in this report

- **Browser criteria.** First usable (C03), single edit and typing (C05, C06), caret (C07), paste (C08), undo (C09), scroll (C10), first page (C11), relayout (C12), scaling in the page (C14), save from the page (C15). An audit of their runners found that they would print wrong numbers: a settle sleep inside the C03 timer ([#104](https://github.com/arthrod/editors_trial/issues/104)), driver wall-clock labelled as paint ([#105](https://github.com/arthrod/editors_trial/issues/105)), a scroll time with no scroll ([#106](https://github.com/arthrod/editors_trial/issues/106)), development servers instead of builds ([#107](https://github.com/arthrod/editors_trial/issues/107)), the shell's first paint as the document's ([#108](https://github.com/arthrod/editors_trial/issues/108)), a frame-witness bug ([#109](https://github.com/arthrod/editors_trial/issues/109)), pooled runs ([#110](https://github.com/arthrod/editors_trial/issues/110)), and input latencies kept without proving the edit ([#113](https://github.com/arthrod/editors_trial/issues/113), [#114](https://github.com/arthrod/editors_trial/issues/114)).
- **Memory over time (C17, C19).** The memory runners sum the wrong processes and stop too early ([#115](https://github.com/arthrod/editors_trial/issues/115)). The peak memory above comes from the headless runner instead.
- **WebAssembly boundary (C24).** Two editors only, and the per-call figures are below the clock ([#117](https://github.com/arthrod/editors_trial/issues/117)).
- **Apryse WebViewer.** It has no headless entry point; it runs only in a browser.
- **Save after an edit.** Every save here follows an unedited load.
- **A cold file system cache.** Every load reads files the warm-up already brought into memory.

## How it was measured

- **Host.** Measured on {{perf.e.machine}}: {{perf.e.host}}. The run refuses to start unless the 1-minute load average is under a third of the CPUs, no other process uses more than a quarter of a core, no trial script is driving Word and no bench batch runs, and the recorded power source is AC. Each sample records its own load and power. {{perf.e.host_note}} {{perf.e.end_check}}
- **Code.** Every checkout must be on its pin with no changed tracked file, and every installed package must be the declared version. Exceptions the run accepted, with its reasons: {{perf.e.dirty_allowed}}. WordCraft's binary is rebuilt from its pinned source before the run.
- **Runs.** Primary run `{{perf.e.run_id}}`: {{perf.e.n}} repetitions, seed {{perf.e.seed}}. Reproduction run `{{perf.e.repro_run_id}}`: {{perf.e.repro_n}} repetitions, seed {{perf.e.repro_seed}}.
- **Publication.** A figure is printed only if the primary run kept every sample of the cell (at least 10, none excluded, at most 10 percent started above the load limit, all on AC power) and the reproduction run's median agrees. The reproduction must be another run, with another seed, of the same documents, versions, timer boundaries and code; the tables builder refuses anything else, and it refuses a summary whose figures its sample files do not give.
- **Runner.** `perf/runner/speed_headless.py`. Tables: `build/perf_e_tables.py`.

Versions, read from disk at the start of the primary run:

{{perf.e.versions}}

## Appendix: full distributions

Round trip in ms, primary run. At this sample count the 99th percentile is close to the maximum.

{{perf.e.appendix}}

## Appendix: figures that did not reproduce (diagnostics, not results)

A median that disagreed between the two runs by more than the tolerance is listed here with both values. These are not results; they show how far apart the runs were.

{{perf.e.not_reproduced}}
