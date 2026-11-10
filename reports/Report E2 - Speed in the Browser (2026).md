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

Each C14 size rung is a separate measure; rungs are never pooled.

not yet measured

### C15 — search and replace

Each C15 step is a separate measure; steps are never pooled.

not yet measured

## Not measured in the browser run

- none

## Not reproduced

not yet measured

## How to reproduce

See perf/container/README.md.

## DOCX verification

Word verification not recorded for this generated twin.
