# Report E2 — Speed in the Browser (2026)

This report is not yet measured.

This report concerns browser-visible first paint, typing, scrolling, and related interactions. No browser runs are available; not yet measured.

## What is measured

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

not yet measured

Per-Space provenance not supplied.

Playwright not yet measured, Chromium not yet measured. Renderer: not yet measured.

## The rule

not yet measured

Primary run `not yet measured`, seed — (not yet measured). Reproduction run `not yet measured`, seed — (not yet measured).

## Tables

### C03 — first visible content

not yet measured

### C04 — deferred work

not yet measured

### C05 — single-edit responsiveness

not yet measured

### C06 — sustained typing

not yet measured

### C07 — cursor and selection

not yet measured

### C08 — clipboard and bulk editing

not yet measured

### C09 — undo and redo

not yet measured

### C10 — scrolling

not yet measured

### C11 — initial layout

not yet measured

### C12 — incremental reflow

not yet measured

### C13 — global invalidation

not yet measured

### C14 — large-document scaling

Each C14 size rung is a separate measure, and within a rung each clock is its own measure: `presented_frame` (document damage followed load; the sample ends at the first compositor screencast frame at or after the document became usable) and `usable_no_damage` (no damage followed; the sample ends at the DOM document-surface mark and is never labelled a compositor frame). Rungs and measures are never pooled.

not yet measured

### C15 — search and replace

Each C15 step is a separate measure; steps are never pooled.

not yet measured

### C17 — memory by phase

not yet measured

### C19 — retained memory

not yet measured

### B8 — resources while opening and editing

**B8 — resources while opening and editing.** One fresh browser per launch opens the document, waits until the editor is idle, types sixteen characters into a body line on the first screen, and waits again. CPU is the processor time of the whole browser process tree: to open (from navigation until idle, including work an editor does after it reports ready), during the edit (the keystrokes plus half a second), and while settling afterwards. Peak memory is the resident memory of that tree. An edit counts only when it is verified in the document: the text of the block at the caret, read from the page or from the editor's model, gained exactly the typed text; WordCraft, which exposes no text, is verified by its own modified flag. An editor that never goes idle is measured over a 30-second cap and flagged. The complex document is loaded without its read-only protection, which the editors honour.

Each cell shows the first seed's median and the second seed's median. A figure is printed only when the two agree within 10 percent (20 ms for CPU).

not yet measured

### B9 — typing marathon

Each kind schedules 12 sessions per editor per seed and requires at least 10 kept. Throughput sessions publish chars/s and resources. Latency sessions publish load and key-to-paint with witness counts; their instrumented throughput and resources are withheld.

not in these runs.

## Not measured in the browser run

- none

## Not reproduced

not yet measured

## How to reproduce

See perf/container/README.md.

## DOCX verification

Word verification not recorded for this generated twin.
