# eigenpal (docx-editor) — browser perf host

No new host app is needed: the repo's own Vite example already accepts a document by URL
query (`?fixture=<name>.docx`) and mounts its own browser benchmark surface
(`?perfE2e=1`). The perf probe fulfils that `/corpus.docx` request itself, so nothing is
copied into `repos/` and no file under `repos/` is modified.

- Editor: `repos/eigenpal-docx-editor` (bun monorepo, Vite 8 + React).
- Install (once): `cd repos/eigenpal-docx-editor && bun install --frozen-lockfile --ignore-scripts`
- Start (registry command, from `examples/vite`):
  `node ../../node_modules/vite/bin/vite.js --port 5218 --strictPort --host 127.0.0.1`
- The repo's own equivalent: `bun run dev:react -- --port 5218 --strictPort --host 127.0.0.1`
- URL measured: `http://127.0.0.1:5218/?perfE2e=1&fixture=corpus.docx&reviewRail=0`

The `?fixture=` value is sanitized to a bare `.docx` basename by `examples/vite/src/main.tsx`
and fetched from `/`; `perf/runner/warm_cold_browser.mjs` intercepts that request and
answers with the workload bytes. Opened in a plain browser (no interception), the URL shows
the harness's "Could not load fixture" alert — that is expected.

`reviewRail=0` mounts the editor without the review rail, so the measured chrome matches the
other bare hosts (plate, canvas, superdoc).

## Selectors

- `ready_selector`: `.docx-page[data-materialized="true"]`
- `ready_js` (the real predicate; mirrors `e2e/edit-browser-bench-harness.ts`):
  the editor instance exists, the shaped font measurer is active, a materialised page is
  visible and laid out, and no progressive-open marker (`[data-docx-opening-preview]`,
  `[data-docx-layout-pending]`) is still pending. `ready()` alone is true as soon as the
  editor instance exists, before pagination finishes, so it is not used on its own.
- `edit_selector`: `.docx-page-content [data-paragraph-id][data-start]` — the painted text
  runs. The pages layer is the contenteditable surface, but `data-start` lives on
  `.layout-run` spans inside `.docx-paragraph-fragment` (which carries only
  `data-paragraph-id`). Clicking the first run places a real caret; typing commits an edit.

## Smoke

```sh
# from the trial repo root, with the server above already listening
node harness/ui/eigenpal-host/smoke.mjs
```

One cold open: navigate, wait for `ready_js`, click `edit_selector`, type `x`, confirm the
document is still rendered. Evidence (screenshot, console, timings, DOM inventory) is
written to `/tmp/perf-run-logs/`; override with `OUT_DIR`.

Evidence from the smoke run of 2026-11-08 (editor `repos/eigenpal-docx-editor` at
`3425d4d`, 2026-11-01):

- `evidence/eigenpal-host-smoke.png` — the rendered page with the typed `x` after `DO` in
  the title (`DOxCX-EDITOR.DEV`) and the caret; toolbar and Editing mode visible.
- `evidence/eigenpal-host-smoke.json` — 30 page shells at ready, 2 materialised, 224 text
  runs, `ready_ms` 5843 from navigation start, `text_delta` 1, `canUndo` true, no
  `data-docx-layout-pending`, empty console errors.
- `evidence/eigenpal-probe-smoke.json` — one pair through the real
  `perf/runner/warm_cold_browser.mjs` with the literal below: cold `first_usable` 4288 ms,
  `presented_frame` 18.5 ms, `single_edit` 108 ms; warm `presented_frame` 24.1 ms. These are
  smoke numbers, not a publication measurement (dev server, single pair).

A plain browser (no probe interception) cannot load `/corpus.docx` from this URL; the perf
probe supplies the bytes.

## BROWSER_TARGETS entry

```python
    "eigenpal": {
        "cwd": REPO / "repos" / "eigenpal-docx-editor" / "examples" / "vite",
        "command": ["node", "../../node_modules/vite/bin/vite.js", "--port", "5218", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5218/?perfE2e=1&fixture=corpus.docx&reviewRail=0",
        "corpus_route": "/corpus.docx",
        "ready_selector": '.docx-page[data-materialized="true"]',
        "ready_js": "window.__DOCX_EDITOR_E2E__?.ready() === true && window.__DOCX_EDITOR_E2E__?.fontMeasurer() === 'shaped' && (() => { const p = document.querySelector('.docx-page[data-materialized=\"true\"]'); if (!p) return false; const r = p.getBoundingClientRect(); return getComputedStyle(p).visibility === 'visible' && r.width > 0 && r.height > 0 && !document.querySelector('[data-docx-opening-preview], [data-docx-layout-pending]'); })()",
        "edit_selector": ".docx-page-content [data-paragraph-id][data-start]",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
```

C02b (`model_ready_browser`) is omitted on purpose: the host exposes one readiness global, so
`first_usable_ms` and `model_ready_browser_ms` are the same number. The runner detects that
(`single_ready_signal`) and, if `C02b` were listed, would write a `not_run` C02 row with
reason "browser harness exposes one ready signal". Add `"C02b": ("model_ready_browser", "model")`
if per-editor parity with plate/canvas in the report matters more than avoiding that row.

C10 (adversarial scroll) works on the same target: the page has one scrollable element
(`.docx-editor ... __viewport`, scrollHeight 32416, clientHeight 812, `overflow-y: auto`),
which is what `perf/runner/adversarial_c10_scroll.mjs` picks.
