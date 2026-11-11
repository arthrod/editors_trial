# Apryse WebViewer — browser perf host (warm/cold suite)

The round-trip lane for Apryse is `harness/apryse/roundtrip.mjs`. This page is
the *browser* host, so the warm/cold suite (C03 first_usable, C05
presented_frame, C06 input_to_next_paint) can measure WebViewer's DOCX Editor
in its own UI.

## Run

```sh
cd harness/apryse
pnpm exec vite --config vite.perf.config.mjs --port 5213 --strictPort --host 127.0.0.1
```

Page: `http://127.0.0.1:5213/perf.html` — `@pdftron/webviewer@12.2.1` from
`harness/apryse/node_modules`, `enableOfficeEditing: true` (Apryse's office
engine, the same call `index.html` / `main.js` make), document fetched from
`/corpus.docx`.

`/corpus.docx` is served by `vite.perf.config.mjs` from `fixture/complex.docx`
so the page opens by hand; the probe intercepts that route and returns its own
generated fixture instead, so the measured document is the probe's.

## Ready signal

Both flip together; the probe uses `ready_js`, the selector is there for a
person watching the page:

- `window.__aprysePerf.state === 'rendered'`
- `#ready[data-state="rendered"]` (visible badge, bottom right)

`rendered` means all of:

1. `documentLoaded` fired and `getAnnotationsLoadedPromise()` resolved;
2. page 1's bitmap has ink: the strongest ink count over the sized
   `#pageContainer1 canvas` elements is > 0 (a blank or never-painted canvas
   keeps the state at `instance` until the 60 s budget, then `error` with the
   reading in the badge);
3. two animation frames passed after that sample.

Ink is looked for in two passes: a 400×400 corner first (where a document
usually starts), then the whole bitmap at stride 2. The corner alone is not
enough — the perf harness's fixture is a single `w:t` opening with ~100
preserved spaces, so its only ink sits at x≈448 of an 816 px page, outside the
corner; that read as "blank page" and cost a 120 s probe timeout in the
2026-11-08 run. `paint.bbox` and `paint.window` record where the ink was found.

Caveat: this proves page 1 is painted, not that the whole page has finished
painting. `wait_after_ready: "500"` covers the remaining settle; C05/C06 time
a paint after a click, not page completeness.

The pixel loop is deliberately cheap while loading (DOM check every 50 ms, a
400×400 `getImageData` at most every 100 ms, the full-bitmap read at most every
400 ms) because the probe times what it waits for.

## Editable surface

`#pageContainer1` — the first page's text surface (`role="region"`,
`aria-label="Page 1"`, inside `<apryse-webviewer>`'s open shadow root, which
Playwright reaches). Clicking it places the office editor's caret; the next
keystroke is inserted at that position and repaints the page bitmap.
`window.__aprysePerf.focusContent()` is a fallback keyboard entry (the office
editor's own `focusContent()`, the call `roundtrip.mjs` uses) if a driver
cannot click.

### Workaround that makes the click possible

WebViewer 12.2.1 lays an **empty** `.HeaderFooterControlsOverlay` over every
page: `position:absolute; inset:0; width:100%; height:100%; z-index:501`,
`pointer-events:auto`. It is the hit target for every click on the page, so:

- `page.locator('#pageContainer1').click()` times out with
  `<div class="HeaderFooterControlsOverlay"> intercepts pointer events`;
- a real mouse click on it places no caret, `getCursorPosition()` stays `{}`,
  typing changes nothing.

The host sets `pointer-events:none` on that one element with a single style
rule appended to the shadow root (`installOverlayRule()` in `perf-main.js`), so
it costs nothing per frame — a MutationObserver re-applying it on every editor
mutation would run DOM queries exactly where C06 is measured. Nothing else
about the UI or the document is touched. With it, clicking page 1 and typing
one character changed the document model (body text 1225 → 1226 chars) and the
page bitmap (ink 4510 → 30526 pixels) in the smoke run below.

## Smoke

With the server above running:

```sh
cd harness/apryse && node smoke_perf.mjs          # --corpus, --url, --outdir, --wait-after-ready optional
```

It does what the probe does, once: navigate, wait on the `ready_js`
expression (eval'd the same way), wait `wait_after_ready` (500 ms), click
`#pageContainer1`, type `x`, and check that the document and the bitmap
changed. Evidence defaults to `/tmp/perf-run-logs/`: `apryse-perf-smoke.json`
(timings, console log, page errors, before/after) and `apryse-perf-smoke.png`.

Two runs on the final code (this machine, load average ~15 — not a quiet
machine, so the ms values are not publishable): ready 1718 / 1511 ms, edit
116 / 92 ms, body text 1225 → 1226 chars, page bitmap ink 4510 → 30526 and
4510 → 30859 pixels, no console errors. Console warnings only (`running in
demo mode`, `.gz`/`.br` content-encoding, Canvas2D readback).

Clicking *before* the settle was observed once to raise two non-fatal
WebViewer errors (`Invalid start location`, and a `pageerror`
`Cannot read properties of undefined (reading 'length')`) while the edit still
landed; it did not recur in the runs above, and the registry's
`wait_after_ready: "500"` is what keeps the measured path on the clean one.

## Registry entry

For `BROWSER_TARGETS` in `perf/runner/benchmark_warm_cold.py` (`REPO` is
already defined there; the other hosts use `UI / <name>`, this one does not
live under `harness/ui`):

```python
    "apryse": {
        "cwd": REPO / "harness" / "apryse",
        "command": ["pnpm", "exec", "vite", "--config", "vite.perf.config.mjs",
                    "--port", "5213", "--strictPort", "--host", "127.0.0.1"],
        "url": "http://127.0.0.1:5213/perf.html",
        "corpus_route": "/corpus.docx",
        "ready_selector": '#ready[data-state="rendered"]',
        "ready_js": "window.__aprysePerf && window.__aprysePerf.state === 'rendered'",
        "wait_after_ready": "500",
        "edit_selector": "#pageContainer1",
        "driver": "playwright",
        "criteria": {
            "C03": ("first_usable", "browser_visible"),
            "C02b": ("model_ready_browser", "model"),
            "C05": ("presented_frame", "browser_visible"),
            "C06": ("input_to_next_paint", "browser_visible"),
        },
    },
```

One ready signal, so the runner records C02 as `not_run` ("browser harness
exposes one ready signal"), like every other host here.

## Blocker outside this host

`benchmark_warm_cold.py` short-circuits apryse before it ever looks at
`BROWSER_TARGETS`:

```python
if editor_id == "apryse" and not _apryse_key_present():   # line 419
    ... not_run, "apryse: trial key not present in environment"
```

`_apryse_key_present()` reads `APRYSE_LICENSE_KEY`, `PDFTRON_LICENSE_KEY` or
`TRIAL_KEY` from the runner's environment. The trial key lives in the repo
`.env` as `APRYSE_API_KEY`, which that check does not read, so a run needs one
of those names exported (or the check extended — not changed here):

```sh
set -a; . ./.env; set +a
export APRYSE_LICENSE_KEY="$APRYSE_API_KEY"
```

The page itself should not need the key to boot (WebViewer's documented keyless
mode is a watermark), but that was not tested here: the host was only run with
the trial `demo:` key, which logs `running in demo mode` and stamps a
watermark into saved files (the round-trip reports already record this).
