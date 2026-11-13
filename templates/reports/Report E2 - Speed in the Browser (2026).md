# Report E2 — Speed in the Browser (2026)

{{perf.e2.status}}

This report concerns browser-visible first paint, typing, scrolling, and related interactions. {{perf.e2.intro}}

## What is measured

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

## The host and its limits

{{perf.e2.relaxed_bounds}}

{{perf.e2.host_note}}

{{perf.e2.provenance}}

Playwright {{perf.e2.playwright}}, Chromium {{perf.e2.chromium}}. Renderer: {{perf.e2.renderer}}.

## The rule

{{perf.e2.sample_plan}}

{{perf.e2.typing_sample_plan}}

{{perf.e2.rule}}

{{perf.e2.runs}}

## Read this before the tables

{{perf.e2.reruns}}
- **How an edit is confirmed.** After each timed interval, and outside it, the harness checks that the edit landed once. It counts the typed text near the caret in the page (Plate, Docxodus, SuperDoc, GenOffice, eigenpal, and Folio through its hidden editing layer) or in the editor's model (canvas-editor, Docen). WordCraft paints into one canvas and puts no document text in the page, so these lanes confirm its edit only by the modified mark in its window title; WordCraft's own select-all and copy does give its text, and C14 reads it that way (below).
- **WordCraft.** C03 and C11 read the document's content from the page, where WordCraft puts none, so those lanes cannot check its content, and those cells say so.
- **Docxodus** opens a read-only, paginated view. Lanes that edit switch it to its block editor before the timed interval starts, so its load times are those of the paginated view.
- **The complex document.** It carries Word's document protection. The lanes that edit it open a copy with that protection removed; the lanes that only load it open the original.
- **Typing tolerance.** GenOffice turns autocorrect on by default (Word's defaults except sentence capitalisation). The typing check compares the whole typed text after three folds: typographic quotes, backticks and guillemets count as straight quotes; (c), (r) and (tm), in either case, may become ©, ® and ™; and any run of whitespace (spaces, tabs, non-breaking spaces, line breaks) counts as one space. A typed list marker (`1.`, `a.`, `(i)`) is excused when the editor turned that line into a real list item, or when the editor painted another marker in its place (a renumbered `1.` shown as `2.`, or a line holding only a marker); in this run every excused marker was of the first kind. A missing or extra character still fails.
- **C14's text check.** Each prose document of the C14 ladder ends with lines of combining marks, characters outside the Basic Multilingual Plane, emoji sequences and right-to-left text; C14 checks (I01 to I03) that they survive in the editor's text, read from its first and last 4,000 characters. Folio and SuperDoc mount only the pages near the start of a long document, and WordCraft paints into a canvas, so for these three the page holds only part of the text. After the timed sample, and outside it, the harness asks each of them for the whole document: SuperDoc through its document model, Folio through its editing layer (mounted by a click on the page), and WordCraft through its own select-all and copy. Every other editor's page holds the whole document. C14 waits up to 1,000 seconds for each document to load. The complex document carries no such lines, so the check does not apply to it: its C14 cells are timings whose text is not checked. When the check fails, the harness names the cause: an editor whose text could not be read, or whose readable text is a window shorter than nine tenths of the document and stops before its closing paragraph, is withheld as "not checkable", a limit of the harness rather than a fault of the editor; an editor whose whole document was read and still fails keeps the failure.
- **Criteria that do not apply.** canvas-editor and Docen paint text without glyph geometry the harness can read, so C05 and C06, which time the keystroke's own paint, do not apply to them. C15 (search and replace) applies to no editor in this run: no measured host exposes a find interface the probe can drive. The document lane ran C15 in each of its five jobs per block, so the C15 cells are also refused as a duplicate block index; since no C15 attempt was applicable, no figure is affected.
- **Chrome traces.** In every first-block job, each timed launch was followed by a separate, untimed launch that recorded a Chrome trace for diagnosis; second-block jobs ran without them, and so did most typing sessions. Traces never feed a table.
- **Throttling and steal.** The host note above gives, per seed, the CPU steal and the samples refused for cgroup CPU throttling; a refused sample is never kept.

## Tables

### C03 — first visible content

{{perf.e2.table.C03}}

### C04 — deferred work

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

Each C14 size rung is a separate measure, and within a rung each clock is its own measure: `presented_frame` (document damage followed load; the sample ends at the first compositor screencast frame at or after the document became usable) and `usable_no_damage` (no damage followed; the sample ends at the DOM document-surface mark and is never labelled a compositor frame). Rungs and measures are never pooled.

{{perf.e2.table.C14}}

### C15 — search and replace

Each C15 step is a separate measure; steps are never pooled.

{{perf.e2.table.C15}}

### C17 — memory by phase

{{perf.e2.table.C17}}

### C19 — retained memory

{{perf.e2.table.C19}}

### B8 — resources while opening and editing

{{perf.e2.criterion.B8}}

Each cell shows the first seed's median and the second seed's median. A figure is printed only when the two agree within 10 percent (20 ms for CPU).

{{perf.e2.table.B8}}

### B9 — typing marathon

Throughput sessions publish chars/s and resources. Latency sessions publish load and key-to-paint with witness counts; their instrumented throughput and resources are withheld.

{{perf.e2.table.TYPING}}

## Not measured in the browser run

{{perf.e2.not_run}}

## Not reproduced

{{perf.e2.not_reproduced}}

## How to reproduce

{{perf.e2.reproduce}}

## DOCX verification

{{perf.e2.word_verification}}
