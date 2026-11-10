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

{{perf.e2.host_note}}

Playwright {{perf.e2.playwright}}, Chromium {{perf.e2.chromium}}. Renderer: {{perf.e2.renderer}}.

## The rule

{{perf.e2.rule}}

Primary run `{{perf.e2.run_id}}`, seed {{perf.e2.seed}} ({{perf.e2.date}}). Reproduction run `{{perf.e2.repro_run_id}}`, seed {{perf.e2.repro_seed}} ({{perf.e2.repro_date}}).

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

Each C14 size rung is a separate measure; rungs are never pooled.

{{perf.e2.table.C14}}

### C15 — search and replace

Each C15 step is a separate measure; steps are never pooled.

{{perf.e2.table.C15}}

## Not measured in the browser run

{{perf.e2.not_run}}

## Not reproduced

{{perf.e2.not_reproduced}}

## How to reproduce

{{perf.e2.reproduce}}

## DOCX verification

{{perf.e2.word_verification}}
